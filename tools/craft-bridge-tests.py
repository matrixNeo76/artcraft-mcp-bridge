#!/usr/bin/env python3
"""Suite delle sei iniezioni di guasto: rende ripetibile la verifica del bridge.

Le prove che hanno portato a questa suite erano tutte a mano, una per una, e sono
vissute in un transcript. Qui diventano eseguibili: ogni caso **rompe qualcosa di
proposito**, chiede il verdetto a `craft-bridge-doctor.py`, `craft-bridge-ident.py`
o `craft-bridge-launch.py`, pretende l'esito giusto e poi rimette a posto.

    guasto iniettato              chi deve accorgersene        esito atteso
    ---------------------------   --------------------------   ----------------------
    shim installato stantio       doctor                       FIX shim installato
    entry di config sbagliata     doctor / config              FIX config
    percorso inesistente          doctor                       FIX percorsi
    eseguibile mancante           doctor                       FIX eseguibili
    build diversa sulla porta     doctor / ident / launcher    FIX + uscita 1
    altra app sulla porta         doctor / ident               FIX + identity mismatch
    credenziale rifiutata         doctor / ident               FIX + auth rifiutata
    porta chiusa                  ident / shim                 unreachable / headless
    installata != pubblicata      feed / doctor                scostamento / nota
    feed assente o illeggibile    feed                         uscita 3 (non un guasto)
    byte pubblicati != installati feed                         FIX byte (archivio manomesso incluso)
    tabella contro registro       shim / doctor / launcher     registro prima, differenza a vista
    finestra PdfCraft assente     traduttore                   l'entry resta valida: headless
    chiamata del traduttore       traduttore                   un processo CLI, esito o guasto

Regole di sicurezza, applicate sempre:

  * la config vera non viene **mai** scritta: i casi che la riguardano usano una
    copia temporanea e `--config`;
  * l'unico file vero che viene toccato e' lo shim **installato** (un byte in piu'),
    e viene riscritto identico dal `--apply` che la suite stessa esegue: la
    perturbazione e' dentro un `try/finally` che lo rimette a posto comunque;
  * le app di prova sono avviate **solo su porte libere** e solo per gli eseguibili
    delle app; se una porta e' occupata il caso si salta (SKIP), non si uccide nulla
    che non abbia avviato la suite;
  * file temporanei, log e token di prova sono rimossi alla fine.

Uso:
    python craft-bridge-tests.py            # tutto (~1-2 min: avvia app vere)
    python craft-bridge-tests.py --static   # solo i casi che non avviano app (~5 s)
    python craft-bridge-tests.py --only build --json
    python craft-bridge-tests.py --static --ci   # su un runner senza app ne' ponte installato

Report:
    ogni esecuzione scrive `reports/craft-bridge-tests.json` (macchina) e
    `reports/craft-bridge-tests.md` (leggibile) nella cartella `reports/` del
    progetto, con esito, durata e impronte
    degli strumenti. Il confronto con l'esecuzione precedente e' **automatico**: il
    json che sta per essere sovrascritto e' la baseline, e le differenze (casi
    cambiati, comparsi o spariti, impronte degli strumenti) finiscono sia a video sia
    nel    markdown, con la durata a parte come contesto. Per confrontare due report
    qualsiasi: `--compare vecchio.json`; `--no-report` non scrive niente,
    `--no-compare` non legge niente. La destinazione si indica con `--report` (o
    `--out`, come gli altri strumenti del progetto).

    **Una baseline per modalita'**: l'esecuzione completa scrive
    `reports/craft-bridge-tests.json`, `--static` scrive `.static.json`, `--ci`
    `.ci.json`, `--only X` `.only-X.json` (combinati: `.static.ci.json`). Non e'
    pignoleria: con un nome solo per tutti, un `--only` sovrascrive in silenzio la
    baseline completa, e da li' in poi il confronto (e la CI) guardano un file che non
    descrive piu' l'insieme. Un `--report` esplicito scrive invece esattamente dove
    dice l'utente.

Cancello (le regressioni fermano un push):
    il confronto non e' solo una lettura: se un caso **peggiora** rispetto alla
    baseline salvata la suite esce con un codice suo (3), cosi' una regressione
    blocca invece di finire in un report che nessuno apre. Gli stati sono ordinati
    `PASS` < `SKIP` < `FAIL`: perdere una prova (PASS -> SKIP) e' un peggioramento
    quanto smentirla (PASS -> FAIL), perche' una prova che non c'e' non e' una prova
    passata; un caso che non viene piu' eseguito e' la stessa perdita vista da un
    altro lato. Un miglioramento (FAIL -> PASS, SKIP -> PASS) e un caso nuovo non lo
    fanno scattare.

    Il cancello si applica solo quando il confronto ha senso: **stesso host** e
    **stessi modi** (`--static`, `--only`, `--ci`) della baseline. Su un'altra
    macchina o in un'altra modalita' la suite lo dichiara e non lo applica: due
    ambienti diversi non si accusano a vicenda. `--no-gate` lo spegne (per guardare
    un report senza che decida), `--no-report` lo spegne perche' non c'e' una
    baseline da leggere.

Esito:
    0  ogni caso passato e nessuna regressione (le SKIP non sono guasti)
    1  almeno un FAIL
    2  errore d'uso
    3  nessun FAIL ma almeno una regressione rispetto alla baseline salvata
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
import re
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
DETACHED = 0x00000008 | 0x00000200          # DETACHED_PROCESS | NEW_PROCESS_GROUP
TIMEOUT = 180.0

# I report generati vivono in `reports/` del progetto, non nella cartella da cui si
# invoca il comando: due esecuzioni fatte da posti diversi restano confrontabili.
DEFAULT_REPORT = HERE.parent / "reports" / "craft-bridge-tests.json"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    if spec is None or spec.loader is None:
        raise SystemExit(f"strumento non caricabile: {HERE / filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DOC = _load("craft_bridge_doctor", "craft-bridge-doctor.py")
IDENT = DOC.IDENT
CONFIG = DOC.CONFIG
FEED = DOC.FEED
SHIM = _load("craft_bridge_mcp", "craft-bridge-mcp.py")
LAUNCH = _load("craft_bridge_launch", "craft-bridge-launch.py")
UI = _load("craft_bridge_ui", "craft-bridge-ui.py")
PILOT = _load("craft_bridge_pilot", "craft-bridge-pilot.py")


# ---------------------------------------------------------------------------------
# Attrezzi
# ---------------------------------------------------------------------------------

class Runner:
    """Avvia gli strumenti come farebbe una persona, e tiene il conto di cosa lasciare pulito."""

    def __init__(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="craft-bridge-tests-"))
        self.pids: list[int] = []

    def cleanup(self) -> None:
        for pid in self.pids:
            kill(pid)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run(self, *cmd: str, timeout: float = TIMEOUT) -> tuple[int, str, str]:
        proc = subprocess.run([sys.executable, *cmd], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
        return proc.returncode, proc.stdout or "", proc.stderr or ""

    def launch(self, exe: Path, port: int, *extra: str) -> int:
        """Avvia un'app staccata, con log in una cartella temporanea."""
        log = self.tmp / f"{exe.stem}-{port}.log"
        with log.open("w", encoding="utf-8", errors="replace") as fh:
            proc = subprocess.Popen([str(exe), "--control", str(port), *extra],
                                    stdin=subprocess.DEVNULL, stdout=fh,
                                    stderr=subprocess.STDOUT, creationflags=DETACHED)
        self.pids.append(proc.pid)
        return proc.pid


def kill(pid: int) -> None:
    subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, text=True)


def port_free(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return False
    except OSError:
        return True


def wait_open(port: int, deadline: float = 25.0) -> bool:
    end = time.time() + deadline
    while time.time() < end:
        if not port_free(port):
            return True
        time.sleep(0.5)
    return False


def configured_ports(table: dict, config_path: Path) -> dict:
    entries = IDENT.shim_entries(config_path)
    return {slug: int((entries.get(slug) or {}).get("port") or table[slug]["port"]) for slug in table}


def temp_config(source: Path, mutate, into: Path) -> Path:
    """Copia della config con una modifica: la config vera non si tocca mai.

    Il file nasce dentro la cartella temporanea della suite (che viene rimossa alla
    fine). Non si usa `mkstemp`: il suo descrittore resta aperto e su Windows il file
    non si puo' piu' cancellare (misurato: `PermissionError: WinError 32`).
    """
    data = json.loads(source.read_text(encoding="utf-8-sig"))
    mutate(data.setdefault("mcpServers", {}))
    out = into / f"mcp-{secrets.token_hex(4)}.json"
    out.write_text(json.dumps(data, indent=4), encoding="utf-8")
    return out


def patch_version(src: Path, dst: Path, new: str) -> None:
    """Seconda build vera: risorsa di versione del PE riscritta a lunghezza invariata."""
    data = bytearray(src.read_bytes())
    old = re.search(rb"\d+\.\d+\.\d+", bytes(data)).group(0).decode("ascii")
    assert len(old) == len(new), f"lunghezze diverse: {old} -> {new}"
    data[:] = data.replace(old.encode("utf-16-le"), new.encode("utf-16-le"))
    data[:] = data.replace(old.encode("ascii"), new.encode("ascii"))
    at = data.find(struct.pack("<I", 0xFEEF04BD))
    assert at > 0, "nessun VS_FIXEDFILEINFO"
    parts = [int(p) for p in new.split(".")] + [0, 0, 0, 0]
    ms, ls = (parts[0] << 16) | parts[1], (parts[2] << 16) | parts[3]
    struct.pack_into("<IIII", data, at + 8, ms, ls, ms, ls)
    dst.write_bytes(bytes(data))


def environment_gap() -> str | None:
    """Perche' su questa macchina non c'e' un ponte da provare (None se c'e').

    Serve a `--ci`: su un runner di CI non ci sono app, ne' config dei connettori, ne'
    copie installate, quindi i casi che parlano del ponte non hanno niente da
    verificare. Con `--ci` quelli vengono **saltati spiegando perche'**, mentre un
    guasto vero (per esempio il ponte installato con un byte in piu') resta un FAIL:
    la modalita' cambia cosa e' un ambiente assente, non cosa e' un guasto.
    """
    if not CONFIG.DEFAULT_CONFIG.is_file():
        return f"config assente ({CONFIG.DEFAULT_CONFIG})"
    for src in (CONFIG.WRAPPER, CONFIG.IDENT):
        target = CONFIG.DEFAULT_INSTALL_DIR / src.name
        if not target.is_file():
            return f"copia installata assente ({target})"
    return None


def case(name: str, kind: str = "e2e", env: bool = False):
    """`env=True`: il caso ha bisogno del ponte installato su questa macchina."""
    def wrap(fn):
        fn.case_name, fn.case_kind, fn.case_env = name, kind, env
        return fn
    return wrap


# ---------------------------------------------------------------------------------
# I casi: stato statico (nessuna app avviata)
# ---------------------------------------------------------------------------------

def first_fix(output: str) -> str:
    """La prima riga `FIX` di un report: un FAIL deve dire *cosa* non andava."""
    for line in output.splitlines():
        if line.strip().startswith("FIX"):
            return line.strip()[4:].strip()[:160]
    return ""


@case("stato pulito", "static", env=True)
def t_clean(run: Runner) -> tuple[str, str]:
    code, out, _ = run.run(str(HERE / "craft-bridge-doctor.py"))
    if code == 0 and "VERDETTO: tutto in ordine" in out:
        return "PASS", "doctor: nessuna azione"
    return "FAIL", f"uscita {code} (attesa 0): {first_fix(out) or 'vedi doctor'}"


@case("shim installato stantio", "static", env=True)
def t_stale_install(run: Runner) -> tuple[str, str]:
    installed = CONFIG.DEFAULT_INSTALL_DIR / "craft-bridge-ident.py"
    if not installed.is_file():
        return "SKIP", f"shim non installato ({installed})"
    original = installed.read_bytes()
    try:
        installed.write_bytes(original + b"\n")        # un byte in piu': hash diverso
        code, out, _ = run.run(str(HERE / "craft-bridge-doctor.py"), "--no-live")
        if code != 1 or "shim installato" not in out or "non e' quello del repo" not in out:
            return "FAIL", f"doctor non ha accusato lo shim stantio (uscita {code})"
        fixed, _, _ = run.run(str(HERE / "craft-bridge-config.py"), "--apply")
        back, out2, _ = run.run(str(HERE / "craft-bridge-doctor.py"), "--no-live")
    finally:
        installed.write_bytes(original)                # comunque: mai lasciarlo perturbato
    if back != 0 or "tutto in ordine" not in out2:
        return "FAIL", f"l'azione consigliata non ha riparato (apply {fixed}, doctor {back})"
    return "PASS", "accusato e riparato dall'azione indicata"


@case("entry di config sbagliata", "static", env=True)
def t_bad_entry(run: Runner) -> tuple[str, str]:
    def mutate(servers):
        args = servers["deckcraft"]["args"]
        args[args.index("--port") + 1] = "7999"
    path = temp_config(CONFIG.DEFAULT_CONFIG, mutate, run.tmp)
    code, out, _ = run.run(str(HERE / "craft-bridge-doctor.py"), "--config", str(path), "--no-live")
    if code != 1 or "FIX" not in out or "deckcraft" not in out:
        return "FAIL", f"doctor non ha accusato l'entry (uscita {code})"
    dry, out2, _ = run.run(str(HERE / "craft-bridge-config.py"), "--config", str(path))
    if "da aggiornare (1)" not in out2:
        return "FAIL", "installer e doctor non concordano sul numero di entry da aggiornare"
    return "PASS", "doctor e installer concordano: 1 entry da aggiornare"


@case("percorso inesistente", "static", env=True)
def t_broken_path(run: Runner) -> tuple[str, str]:
    def mutate(servers):
        servers["cadcraft"]["command"] = r"C:\Python-che-non-esiste\python.exe"
    path = temp_config(CONFIG.DEFAULT_CONFIG, mutate, run.tmp)
    code, out, _ = run.run(str(HERE / "craft-bridge-doctor.py"), "--config", str(path), "--no-live")
    if code != 1 or "FIX  percorsi" not in out or "cadcraft.command" not in out:
        return "FAIL", f"percorso rotto non accusato (uscita {code})"
    return "PASS", "FIX percorsi: cadcraft.command"


@case("eseguibile mancante", "unit")
def t_missing_exe(run: Runner) -> tuple[str, str]:
    table = CONFIG.apps_table()
    broken = {k: dict(v) for k, v in table.items()}
    broken["lightcraft"]["cli"] = str(Path(broken["lightcraft"]["cli"]).with_suffix(".exe.spostato"))
    rows = DOC.check_apps(broken)
    detail = " ".join(r["detail"] for r in rows)
    if rows[0]["state"] != "fail" or "lightcraft" not in detail:
        return "FAIL", f"non accusato: {detail}"
    return "PASS", detail.split("mancano:")[-1].strip()


@case("posizione dell'app dal sistema", "unit")
def t_locations(run: Runner) -> tuple[str, str]:
    """La tabella dichiara, il sistema decide: si prova senza toccare il registro."""
    where = run.tmp / "programmi" / "Finto"
    where.mkdir(parents=True)
    (where / "finto.exe").write_bytes(b"app")
    (where / "finto-cli.exe").write_bytes(b"cli accanto all'app")
    declared = run.tmp / "tabella"
    declared.mkdir()
    (declared / "finto-cli.exe").write_bytes(b"cli dichiarata da noi")

    problems = []
    def want(condition: bool, why: str) -> None:
        if not condition:
            problems.append(why)

    cli, source = SHIM.choose_cli(str(where / "finto.exe"), str(declared / "finto-cli.exe"))
    want(cli == str(where / "finto-cli.exe") and source == "registro App Paths",
         f"app registrata con CLI accanto: scelto {cli} ({source})")
    _, source_hive = SHIM.choose_cli(str(where / "finto.exe"), str(declared / "finto-cli.exe"),
                                     "utente")
    want(source_hive == "registro App Paths (utente)",
         f"l'hive non compare nella fonte: {source_hive}")
    want(SHIM.cli_beside(str(where / "finto.exe")) == where / "finto-cli.exe",
         "il nome della CLI accanto all'app non e' derivato come atteso")

    # Anche l'**avvio** usa il percorso del sistema: l'eseguibile registrato, non una
    # stringa ricavata dalla CLI. Con quel campo assente (sistema senza registro) resta
    # la derivazione dalla tabella.
    registered = {"cli": str(where / "finto-cli.exe"), "app_exe": str(where / "finto.exe")}
    want(LAUNCH.app_exe_of(registered) == where / "finto.exe",
         f"l'avvio non usa l'eseguibile registrato: {LAUNCH.app_exe_of(registered)}")
    want(LAUNCH.app_exe_of({"cli": str(where / "finto-cli.exe"), "app_exe": None})
         == where / "finto.exe",
         "senza registro non si ricade sull'eseguibile derivato dalla CLI")

    lonely = run.tmp / "programmi" / "Sola"
    lonely.mkdir()
    (lonely / "sola.exe").write_bytes(b"app senza CLI")
    cli2, source2 = SHIM.choose_cli(str(lonely / "sola.exe"), str(declared / "finto-cli.exe"))
    want(cli2 == str(declared / "finto-cli.exe") and source2 == "tabella",
         f"app registrata senza CLI accanto: scelto {cli2} ({source2})")

    mai = run.tmp / "mai" / "x-cli.exe"
    cli3, source3 = SHIM.choose_cli(None, str(mai))
    want(cli3 == str(mai) and "assente" in source3,
         f"nessuna fonte e percorso inesistente: {cli3} ({source3})")
    # La diagnosi deve **vedere** la divergenza fra sistema e tabella, e dire quale
    # delle due sta usando: senza quel pezzo la differenza resterebbe invisibile.
    declared_cli = str(declared / "finto-cli.exe")
    table = {"finta": {"cli": declared_cli, "declared_cli": declared_cli,
                       "app_exe": str(where / "finto.exe"), "cli_source": "tabella"}}
    rows = DOC.check_locations(table)
    want(rows[0]["state"] == "nota" and "sistema ->" in rows[0]["detail"]
         and "tabella ->" in rows[0]["detail"],
         f"la divergenza non viene mostrata: {rows[0]}")
    want("si usa quella della tabella" in rows[0]["detail"],
         f"il doctor non dice quale percorso sta usando: {rows[0]['detail']}")

    table["finta"].update({"cli": str(where / "finto-cli.exe"),
                           "cli_source": "registro App Paths"})
    rows2 = DOC.check_locations(table)
    want("si usa quella del sistema" in rows2[0]["detail"],
         f"il doctor non riconosce la CLI accanto all'app: {rows2[0]['detail']}")

    if problems:
        return "FAIL", "; ".join(problems)[:200]
    return "PASS", ("registro prima, tabella poi, e l'assenza si dichiara; "
                    "l'avvio prende l'eseguibile registrato")


@case("app registrate dal sistema", "static", env=True)
def t_locations_live(run: Runner) -> tuple[str, str]:
    """Su questa macchina: i percorsi vengono dal registro, e la tabella li conferma."""
    table = SHIM.app_table()
    from_registry = [slug for slug, spec in table.items()
                     if spec["cli_source"].startswith("registro App Paths")]
    if len(from_registry) != len(table):
        rest = sorted(set(table) - set(from_registry))
        return "FAIL", f"dal registro {len(from_registry)} di {len(table)}: {rest}"
    hives = {slug: spec["app_hive"] for slug, spec in table.items()}
    wrong_hive = [slug for slug, hive in hives.items() if hive not in ("utente", "macchina")]
    if wrong_hive:
        return "FAIL", f"hive non riconosciuto per: {wrong_hive}"
    # Il launcher e' installato **per utente** (sta in `%LOCALAPPDATA%`): la sua voce
    # sta in `HKCU` e non in `HKLM`. Se questo caso dice "macchina", l'utente non viene
    # nemmeno consultato e un'installazione per-utente resterebbe invisibile.
    launcher_exe, launcher_hive = SHIM.registered_exe("artcraft-launcher")
    if not launcher_exe or launcher_hive != "utente":
        return "FAIL", (f"il launcher risulta {launcher_hive} invece che utente: "
                         f"HKCU non viene letto ({launcher_exe})")
    rows = DOC.check_locations(table)
    if rows[0]["state"] != "ok" or "registro" not in rows[0]["detail"]:
        return "FAIL", f"doctor non conferma la posizione: {rows[0]}"
    drifted = [slug for slug, spec in table.items() if spec["declared_cli"] != spec["cli"]]
    if drifted:
        return "FAIL", f"tabella e registro divergono su {drifted}"
    # L'avvio deve prendere lo **stesso** percorso che il sistema registra: se lanciasse
    # un eseguibile ricavato dalla CLI, un'app spostata verrebbe avviata da un percorso
    # vecchio anche quando il registro dice dove sta davvero.
    wrong = [slug for slug, spec in table.items()
             if not spec["app_exe"] or LAUNCH.app_exe_of(spec) != Path(spec["app_exe"])]
    if wrong:
        return "FAIL", f"l'avvio non usa l'eseguibile registrato per: {wrong}"
    return "PASS", (f"{len(from_registry)}/{len(table)} percorsi dal registro App Paths, "
                    "hive utente e macchina, tabella confermata, avvio sull'eseguibile "
                    "registrato")


class FakeWindow:
    """Un finto PdfCraft: risponde sul canale come risponde l'app vera.

    Il protocollo e' quello misurato sull'app (autenticazione col token del file di
    controllo, poi `ui.<metodo>`), riprodotto nella parte che serve a provare il
    traduttore: la credenziale, `ui.state` per la scelta del modo, un'eco per gli
    altri metodi, un guasto vero quando si chiede un'etichetta che non esiste.
    Cosi' il traduttore si prova senza app e senza finestra.
    """

    def __init__(self, token: str = "t" * 32) -> None:
        self.token = token
        self.requests: list[dict] = []
        self.refuse_auth = False
        self.srv = socket.socket()
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind(("127.0.0.1", 0))
        self.port = int(self.srv.getsockname()[1])
        self.srv.listen(8)
        self.srv.settimeout(0.2)
        self.stop = threading.Event()
        threading.Thread(target=self._serve, daemon=True).start()

    def control_file(self, path: Path) -> Path:
        path.write_text(json.dumps({"pid": os.getpid(), "port": self.port,
                                    "token": self.token}), encoding="utf-8")
        return path

    def close(self) -> None:
        self.stop.set()
        self.srv.close()

    def sent(self, method: str) -> list[dict]:
        return [r for r in self.requests if r.get("method") == method]

    def _serve(self) -> None:
        while not self.stop.is_set():
            try:
                conn, _ = self.srv.accept()
            except (socket.timeout, OSError):
                continue
            with conn:
                buf = b""
                try:
                    conn.settimeout(5)
                    while True:
                        data = conn.recv(65536)
                        if not data:
                            break
                        buf += data
                        while b"\n" in buf:
                            line, buf = buf.split(b"\n", 1)
                            if line.strip():
                                self._answer(conn, json.loads(line))
                except (OSError, json.JSONDecodeError):
                    pass

    def _answer(self, conn, request: dict) -> None:
        self.requests.append(request)
        rid, method = request.get("id"), request.get("method")
        params = request.get("params") or {}
        if method == "auth":
            reply = ({"id": rid, "error": {"code": -32001, "message": "token rifiutato"}}
                     if self.refuse_auth else {"id": rid, "result": {"ok": True}})
        elif method == "ui.state":
            reply = {"id": rid, "result": {"window": {"width": 1440, "height": 920},
                                           "documents": []}}
        elif method == "ui.screenshot":
            reply = {"id": rid, "result": {
                "png_base64": base64.b64encode(b"PNGfinto").decode(),
                "width": 4, "height": 3}}
        elif method == "ui.commands":
            reply = {"id": rid, "result": {"commands": [{"id": "file.open",
                                                          "label": "Apri"}]}}
        elif method == "ui.click" and params.get("label"):
            reply = {"id": rid, "error": {"code": -32602,
                                           "message": f"no enabled clickable widget "
                                                      f"labelled {params['label']!r}"}}
        else:
            reply = {"id": rid, "result": {"eco": params}}
        conn.sendall((json.dumps(reply) + "\n").encode())


def ui_command(control: Path, *extra: str) -> list[str]:
    """Il comando con cui un client MCP avvierebbe il traduttore."""
    return [sys.executable, str(HERE / "craft-bridge-ui.py"), "--slug", "pdfcraft",
            "--control", str(control), *extra]


def ui_declared_mode(control: Path, *extra: str) -> tuple[int, str, str]:
    """Il modo dichiarato su stderr: stdin chiuso, il server decide e poi esce."""
    proc = subprocess.run(ui_command(control, *extra), input="", capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=120)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def ui_open_session(control: Path, *extra: str):
    """Una sessione MCP vera col traduttore, col client del progetto (pilot)."""
    client = PILOT.McpClient(ui_command(control, *extra))
    init = client.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                     "clientInfo": {"name": "craft-bridge-tests",
                                                    "version": "1"}})
    return client, init


def ui_close_session(client) -> None:
    try:
        client.proc.terminate()
        client.proc.wait(timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        try:
            client.proc.kill()
        except OSError:
            pass


@case("argomenti della chiamata", "unit")
def t_ui_args(run: Runner) -> tuple[str, str]:
    """Un metodo -> una riga di comando. Funzione pura: nessun processo, nessuna rete.

    Il punto delicato e' la tipizzazione: la CLI interpreta ogni `key=value` come
    JSON, quindi `true` diventa un booleano e `"true"` resta una stringa. Se la
    conversione sbagliasse, all'app arriverebbe un parametro di tipo diverso — e il
    metodo farebbe un'altra cosa invece di fallire.
    """
    cli, control = "cli.exe", Path("control.json")
    problems = []

    def want(argv: list[str], tail: list[str], why: str) -> None:
        if argv[-len(tail):] != tail:
            problems.append(f"{why}: {argv[-len(tail):]} invece di {tail}")

    want(UI.method_argv(cli, control, "click", {"x": 100, "y": 250}),
         ["click", "x=100", "y=250"], "numeri")
    want(UI.method_argv(cli, control, "type", {"text": "true"}),
         ["type", 'text="true"'], "stringa che sembra un booleano")
    want(UI.method_argv(cli, control, "type", {"text": "ciao=mondo"}),
         ["type", 'text="ciao=mondo"'], "stringa con un = dentro")
    want(UI.method_argv(cli, control, "drag", {"from": [10, 10], "to": [20, 20]}),
         ["drag", "from=[10, 10]", "to=[20, 20]"], "liste")
    want(UI.method_argv(cli, control, "set", {"key": "theme", "value": None}),
         ["set", "key=\"theme\"", "value=null"], "null")
    want(UI.method_argv(cli, control, "set", {"key": "theme", "value": True}),
         ["set", "key=\"theme\"", "value=true"], "booleano")
    want(UI.method_argv(cli, control, "screenshot", {}, out="x.png"),
         ["screenshot", "--out", "x.png"], "immagine su file")
    argv = UI.method_argv(cli, control, "state", {})
    if argv[:4] != [cli, "ui", "--control", str(control)]:
        problems.append(f"intestazione inattesa: {argv[:4]}")
    if problems:
        return "FAIL", "; ".join(problems)[:220]
    return "PASS", "numeri, stringhe (virgolettate), liste, null e booleani come li vuole la CLI"


@case("sessione del traduttore", "unit")
def t_ui_session(run: Runner) -> tuple[str, str]:
    """Una sessione MCP vera contro un finto PdfCraft: 15 tool, e ogni chiamata un processo.

    La finestra e' finta, la CLI no: la catena che si prova e' traduttore -> `pdfcraft-cli
    ui --control FILE` -> canale, e a parlare col canale deve essere la CLI del fornitore.
    Dove non c'e' (un runner di CI senza le app) il caso si **salta motivando**, invece di
    morire con `server MCP chiuso in anticipo` che non dice niente a nessuno.
    """
    cli, source = UI.resolve_cli("pdfcraft", None)
    if not Path(cli).is_file():
        return "SKIP", (f"la CLI del fornitore non e' installata ({cli}, {source}): "
                        "senza di lei la catena bridged non si puo' provare")
    fake = FakeWindow()
    control = fake.control_file(run.tmp / "control.json")
    client = None
    try:
        client, init = ui_open_session(control)
        problems = []
        info = (init.get("result") or {}).get("serverInfo") or {}
        if info.get("name") != "pdfcraft-ui":
            problems.append(f"serverInfo inatteso: {info}")
        tools = (client.rpc("tools/list").get("result") or {}).get("tools") or []
        names = {t["name"] for t in tools}
        if names != {f"ui_{m}" for m in UI.METHODS}:
            problems.append(f"catalogo inatteso: {sorted(names)[:6]}...")
        read_only = {t["name"] for t in tools if (t.get("annotations") or {}).get("readOnlyHint")}
        if read_only != {"ui_state", "ui_inspect", "ui_commands", "ui_screenshot"}:
            problems.append(f"sola lettura inattesa: {sorted(read_only)}")

        state = client.rpc("tools/call", {"name": "ui_state", "arguments": {}})
        body = (state.get("result") or {})
        if body.get("isError") or "1440" not in json.dumps(body):
            problems.append(f"ui_state non ha riportato la finestra: {body}")

        click = client.rpc("tools/call", {"name": "ui_click",
                                          "arguments": {"x": 10, "y": 20}})
        if (click.get("result") or {}).get("isError"):
            problems.append("ui_click e' fallito su un peer che accetta")
        sent = fake.sent("ui.click")
        if not sent or sent[-1]["params"] != {"x": 10, "y": 20}:
            problems.append(f"parametri arrivati all'app: {sent[-1]['params'] if sent else '-'}")

        client.rpc("tools/call", {"name": "ui_type", "arguments": {"text": "true"}})
        sent_t = fake.sent("ui.type")
        if not sent_t or sent_t[-1]["params"].get("text") != "true":
            problems.append(f"una stringa e' arrivata come {sent_t[-1]['params'] if sent_t else '-'}")

        shot = client.rpc("tools/call", {"name": "ui_screenshot", "arguments": {}})
        blocks = (shot.get("result") or {}).get("content") or []
        if not blocks or blocks[0].get("type") != "image" or not blocks[0].get("data"):
            problems.append(f"screenshot senza immagine: {blocks[:1]}")

        bad = client.rpc("tools/call", {"name": "ui_click",
                                         "arguments": {"label": "NonEsiste"}})
        if not (bad.get("result") or {}).get("isError"):
            problems.append("un guasto dell'app non e' arrivato come isError")
        unknown = client.rpc("tools/call", {"name": "ui_inventato", "arguments": {}})
        if (unknown.get("error") or {}).get("code") != -32602:
            problems.append(f"tool sconosciuto: risposta {unknown}")
        if client.proc.poll() is not None:
            problems.append(f"il server e' morto (uscita {client.proc.returncode})")
        # Il modo va chiesto **con la finestra ancora su**: dopo la chiusura sarebbe
        # headless, e la prova direbbe un'altra cosa.
        code, _out, err = ui_declared_mode(control)
        if code != 0 or "modalita' bridged" not in err:
            problems.append(f"modo dichiarato male (uscita {code}): {err.strip()[:140]}")

        # E la finestra che sparisce **a meta' sessione**: la chiamata deve tornare un
        # guasto con la diagnosi, non una risposta vuota che sembra riuscita.
        fake.close()
        gone = client.rpc("tools/call", {"name": "ui_state", "arguments": {}})
        gone_text = ((gone.get("result") or {}).get("content") or [{}])[0].get("text", "")
        if not (gone.get("result") or {}).get("isError"):
            problems.append(f"finestra sparita: risposta senza guasto ({gone_text[:100]})")
        elif "non risponde piu'" not in gone_text:
            problems.append(f"finestra sparita senza diagnosi: {gone_text[:120]}")
        if problems:
            return "FAIL", "; ".join(problems)[:220]
    finally:
        if client is not None:
            ui_close_session(client)
        fake.close()
    return "PASS", ("15 tool, parametri tipizzati, immagine, isError su guasto, "
                    "-32602 sull'ignoto, modo bridged dichiarato, finestra sparita "
                    "a meta' sessione diagnosticata")


@case("senza finestra il traduttore ripiega", "unit")
def t_ui_headless(run: Runner) -> tuple[str, str]:
    """Finestra chiusa: la entry resta valida e parla col server **headless** del fornitore.

    Il finto CLI qui e' un server MCP minimo: la prova e' che i suoi frame arrivino al
    client attraverso il traduttore, senza riscritture e senza inventare tool.
    """
    fake_server = run.tmp / "finto-mcp.py"
    fake_server.write_text(
        "import json, sys\n"
        "for line in sys.stdin:\n"
        "    if not line.strip():\n"
        "        continue\n"
        "    req = json.loads(line)\n"
        "    if req.get('method') == 'initialize':\n"
        "        out = {'protocolVersion': '2025-06-18', 'serverInfo': {'name': 'finto'}}\n"
        "    elif req.get('method') == 'tools/list':\n"
        "        out = {'tools': [{'name': 'fake_tool', 'inputSchema': {'type': 'object'}}]}\n"
        "    else:\n"
        "        out = {}\n"
        "    sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': req.get('id'),\n"
        "                                 'result': out}) + '\\n')\n"
        "    sys.stdout.flush()\n", encoding="utf-8")
    missing = run.tmp / "control-assente.json"
    # Il comando headless della CLI vera e' `pdfcraft-cli mcp`: qui il ruolo della CLI
    # lo fa l'interprete e il server finto e' l'argomento che gli si passa, cosi' la
    # stessa catena (traduttore -> processo -> frame MCP) si prova senza il fornitore.
    headless = ["--cli", sys.executable, "--headless-args", str(fake_server)]
    code, _out, err = ui_declared_mode(missing, "--timeout", "20", *headless)
    if code != 0 or "modalita' headless" not in err:
        return "FAIL", f"il ripiego non e' stato dichiarato (uscita {code}): {err.strip()[:140]}"
    client = PILOT.McpClient(ui_command(missing, *headless))
    try:
        tools = (client.rpc("tools/list").get("result") or {}).get("tools") or []
        names = [t.get("name") for t in tools]
        if names != ["fake_tool"]:
            return "FAIL", f"i tool del server headless non sono passati: {names}"
    finally:
        ui_close_session(client)
    return "PASS", "nessuna finestra: il server headless del fornitore passa attraverso, dichiarato"


@case("finestra PdfCraft dal vivo", "static", env=True)
def t_ui_live(run: Runner) -> tuple[str, str]:
    """Sull'app vera: modo, catalogo e una chiamata. Salta (motivando) se e' chiusa."""
    control = UI.CONTROL_DIR / "pdfcraft-control.json"
    code, out, _err = run.run(str(HERE / "craft-bridge-ui.py"), "--slug", "pdfcraft",
                              "--list", "--json")
    if code != 0:
        return "FAIL", f"il traduttore non risponde (uscita {code})"
    report = json.loads(out)
    if report.get("mode") != "bridged":
        return "SKIP", f"finestra chiusa ({report.get('mode_why')}): l'entry va headless"
    drift = report.get("drift") or {}
    if not drift.get("checked"):
        return "FAIL", f"catalogo non confrontabile dal vivo: {drift}"
    if not drift.get("same"):
        return "FAIL", (f"il catalogo diverge: solo dall'app {drift.get('only_theirs')}, "
                        f"solo da noi {drift.get('only_ours')}")
    code_state, out_state, _ = run.run(str(HERE / "craft-bridge-ui.py"), "--slug",
                                       "pdfcraft", "--call", "state")
    if code_state != 0:
        return "FAIL", f"ui state sulla finestra e' uscito {code_state}"
    state = json.loads(out_state)
    if not state.get("window"):
        return "FAIL", f"state senza finestra: {list(state)[:6]}"
    return "PASS", (f"porta {report.get('port')} (pid {report.get('pid')}), "
                    f"{drift.get('ours')} metodi come li dichiara l'app")


def fake_cli(run: Runner, name: str, help_text: str) -> str:
    """Una CLI finta: il suo `--help` stampa il testo dato.

    Un `.cmd`, non un `.py`: la domanda e' cosa **la CLI** dichiara di saper fare, e
    Windows esegue un .cmd direttamente. Il testo resta senza caratteri che la shell
    interpreterebbe (`<`, `>`, `|`, `&`): qui si prova il confronto, non il quoting.
    """
    path = run.tmp / f"{name}.cmd"
    body = "".join(f"echo {line}\n" for line in help_text.splitlines())
    path.write_text("@echo off\n" + body, encoding="utf-8")
    return str(path)


HELP_CONNECT = "usage:\n  fintocraft-cli mcp [--connect PORT] [--sample]"
HELP_BRIDGE = "usage:\n  altrocraft-cli mcp [--bridge PORT] [--autosave]"
HELP_CONTROL = ("usage:\n  pdfcraft-cli ui --control FILE [method] [key=value]\n"
                "  pdfcraft-cli mcp [--root DIR]")


@case("flag di aggancio, verificato", "unit")
def t_flag_verdict(run: Runner) -> tuple[str, str]:
    """La tabella dichiara un flag; lo dichiara anche l'help della CLI? Adesso si chiede.

    Le tre risposte che contano: confermato, **non confermato** (la tabella afferma
    un'opzione che la CLI non nomina), e il caso rovesciato — un'app di cui la tabella
    dice che *non* ha un aggancio: se l'help lo nomina, la tabella e' vecchia.
    """
    with_connect = fake_cli(run, "fintocraft", HELP_CONNECT)
    with_bridge = fake_cli(run, "altrocraft", HELP_BRIDGE)
    control_only = fake_cli(run, "fintocontrol", HELP_CONTROL)
    cases = [
        ("l'help lo documenta", {"cli": with_connect, "flag": "--connect"}, "ok"),
        ("l'help non ne nomina nessuno", {"cli": control_only, "flag": "--connect"},
         "diverge"),
        ("l'help ne nomina un altro", {"cli": with_bridge, "flag": "--connect"}, "diverge"),
        ("nessun aggancio, e il canale e' quello", {"cli": control_only, "flag": None,
                                                    "control_flag": "--control",
                                                    "translated": True}, "ok"),
        ("nessun aggancio, ma l'help ce l'ha", {"cli": with_connect, "flag": None},
         "diverge"),
        ("la CLI non da' un help", {"cli": str(run.tmp / "assente.exe"),
                                     "flag": "--connect"}, "non leggibile"),
    ]
    problems = []
    for why, spec, expected in cases:
        row = SHIM.flag_facts("fintocraft", spec, timeout=20)
        if row["state"] != expected:
            problems.append(f"{why}: {row['state']} invece di {expected} ({row['detail'][:60]})")
    # Il verdetto complessivo, e la promessa negativa: "senza aggancio" vuol dire che
    # l'help non nomina nessuno dei due flag.
    report = SHIM.flag_report({"a": {"cli": with_connect, "flag": "--connect"},
                              "b": {"cli": with_bridge, "flag": "--bridge"},
                              "c": {"cli": control_only, "flag": None,
                                    "control_flag": "--control"}}, timeout=20)
    if report["diverging"] or len(report["ok"]) != 3:
        problems.append(f"verdetto complessivo: {report['ok']} ok, "
                        f"{report['diverging']} divergenti")
    if problems:
        return "FAIL", "; ".join(problems)[:220]
    return "PASS", ("confermato, non confermato, flag diverso, assenza confermata "
                    "e help illeggibile: sei verdetti, come li vuole l'help della CLI")


@case("doctor: flag non confermato", "unit")
def t_flag_doctor(run: Runner) -> tuple[str, str]:
    """La diagnosi deve **dirlo**, non solo saperlo: la tabella mente, la riga accusa.

    Tre giri del doctor (uno per verdetto), e non un quarto: ogni giro chiede l'help di
    tutte le CLI, quindi costa. La terza e' quella che vede un runner di CI senza app
    installate — le CLI non ci sono, e il verdetto deve essere una `nota` che lo dice,
    non un `ok`.
    """
    def row_of(apps: dict, name: str) -> dict:
        path = run.tmp / f"apps-{name}.json"
        path.write_text(json.dumps(apps), encoding="utf-8")
        code, out, err = run.run(str(HERE / "craft-bridge-doctor.py"),
                                 "--apps-file", str(path), "--no-live", "--json")
        try:
            report = json.loads(out)
        except json.JSONDecodeError:
            return {"state": "?", "detail": f"uscita non JSON ({code}): {err.strip()[:80]}"}
        return next((c for c in report["checks"] if c["check"] == "flag di aggancio"),
                    {"state": "?", "detail": "riga assente"})

    # La tabella dice `--connect`, la CLI annuncia `--bridge`: e' il caso che conta —
    # un'app aggiornata che ha rinominato il flag lascerebbe la tabella a promettere
    # un'opzione che non esiste piu'.
    spec = {"cli": fake_cli(run, "fintocraft", HELP_BRIDGE), "flag": "--connect",
            "addr": "{port}", "port": 7999, "cli_source": "tabella di prova",
            "declared_cli": "fintocraft-cli.exe", "app_exe": None, "app_hive": None}
    problems = []
    lying = row_of({"fintocraft": spec}, "bugiarda")
    if lying["state"] != "fail" or "fintocraft" not in lying["detail"]:
        problems.append(f"tabella non confermata: {lying['state']} - {lying['detail'][:80]}")
    if "--flags" not in lying.get("action", ""):
        problems.append(f"l'azione non dice come guardare la tabella: {lying.get('action', '')[:60]}")
    honest = row_of({"fintocraft": {**spec,
                                    "cli": fake_cli(run, "fintocontrol", HELP_CONTROL),
                                    "flag": None, "control_flag": "--control"}}, "onesta")
    if honest["state"] != "ok":
        problems.append(f"tabella confermata dal canale: {honest['state']} - {honest['detail'][:80]}")

    # E la CLI **assente** (un runner senza app installate): non e' "ok", e' una lacuna
    # dichiarata. E' l'esito che un runner di CI vede sempre, quindi deve essere giusto.
    silent = row_of({"fintocraft": {**spec, "cli": str(run.tmp / "assente.exe")}},
                    "assente")
    if silent["state"] != "nota" or "non leggibile" not in silent["detail"]:
        problems.append(f"CLI senza help: {silent['state']} - {silent['detail'][:80]}")
    if problems:
        return "FAIL", "; ".join(problems)[:220]
    return "PASS", ("tabella non confermata -> FIX con l'azione; confermata dal canale "
                    "-> ok; CLI assente -> nota")



@case("flag di aggancio dal vivo", "static", env=True)
def t_flag_live(run: Runner) -> tuple[str, str]:
    """Sulle CLI vere: ognuna dice la sua, e la diagnosi dice la stessa cosa."""
    code, out, err = run.run(str(HERE / "craft-bridge-mcp.py"), "--flags", "--json")
    if code not in (0, 1) or not out.strip():
        return "FAIL", f"il confronto non risponde (uscita {code}): {err.strip()[:120]}"
    report = json.loads(out)
    if report["diverging"]:
        detail = "; ".join(f"{r['check']}: {r['detail']}" for r in report["rows"]
                          if r["state"] == "diverge")
        return "FAIL", f"la tabella dice un flag che la CLI non conferma -> {detail[:180]}"
    if report["unreadable"]:
        return "SKIP", (f"le CLI non danno un help per {', '.join(report['unreadable'])}: "
                        f"li' il flag resta una dichiarazione della tabella")
    code_d, out_d, err_d = run.run(str(HERE / "craft-bridge-doctor.py"), "--no-live", "--json")
    if code_d not in (0, 1) or not out_d.strip():
        return "FAIL", f"doctor non risponde (uscita {code_d}): {err_d.strip()[:120]}"
    row = next((c for c in json.loads(out_d)["checks"]
                if c["check"] == "flag di aggancio"), None)
    if row is None or row["state"] != "ok":
        return "FAIL", f"la diagnosi non conferma quello che le CLI dicono: {row}"
    return "PASS", (f"{len(report['ok'])}/{report['total']} CLI documentano il flag della "
                    f"tabella, e la diagnosi lo ripete")


@case("cancello sulle regressioni", "unit")
def t_gate(run: Runner) -> tuple[str, str]:
    """Il cancello, con report finti: quali peggioramenti fermano e quali no.

    Il cancello decide un codice d'uscita, cioe' se un push si ferma: e' l'ultimo posto
    in cui accettare un "sembra giusto". Qui si danno alla funzione i due report che
    servono (stessi modi e stesso host, come nella realta') e si guarda cosa risponde,
    comprese le due volte in cui **non deve** rispondere: un'altra macchina e un'altra
    modalita'. La prova end-to-end del codice d'uscita e' un'altra cosa e sta nei
    comandi (vedi docs/tools/craft-bridge-tests.md).
    """
    def fake(cases: dict, host: str = "prova", static: bool = False,
             ci: bool = False, only=None) -> dict:
        return {"when": "2026-01-01T00:00:00", "host": host,
                "modes": {"static": static, "only": only, "ci": ci},
                "cases": [{"case": n, "kind": "unit", "state": s, "detail": f"{n}: {s}",
                           "seconds": 0.0} for n, s in cases.items()]}

    problems = []
    def want(condition: bool, why: str) -> None:
        if not condition:
            problems.append(why)

    base = fake({"a": "PASS", "b": "FAIL", "c": "SKIP", "d": "PASS"})
    rows, why = regressions(base, fake({"a": "FAIL", "b": "FAIL", "c": "SKIP", "d": "PASS"}))
    want([(r["case"], r["from"], r["to"]) for r in rows] == [("a", "PASS", "FAIL")]
         and not why, f"PASS->FAIL non accusato come vorrebbe: {rows} ({why})")

    rows, _ = regressions(base, fake({"a": "PASS", "b": "PASS", "c": "PASS", "d": "PASS"}))
    want(rows == [], f"un miglioramento (FAIL->PASS, SKIP->PASS) non ferma niente: {rows}")

    rows, _ = regressions(base, fake({"a": "PASS", "b": "FAIL", "c": "SKIP", "d": "SKIP"}))
    want([(r["case"], r["from"], r["to"]) for r in rows] == [("d", "PASS", "SKIP")],
         f"perdere una prova (PASS->SKIP) deve fermare: {rows}")

    rows, _ = regressions(base, fake({"a": "PASS", "b": "FAIL", "c": "SKIP"}))
    want([(r["case"], r["to"]) for r in rows] == [("d", "assente")],
         f"un caso non piu' eseguito e' la stessa perdita: {rows}")

    rows, _ = regressions(base, fake({"a": "PASS", "b": "FAIL", "c": "SKIP", "d": "PASS",
                                          "e": "FAIL"}))
    want(rows == [], f"un caso nuovo non e' una regressione: {rows}")

    rows, why = regressions(base, fake({"a": "FAIL"}, host="altra-macchina"))
    want(rows == [] and "altra macchina" in why,
         f"su un'altra macchina il cancello non si applica: {rows} ({why})")

    rows, why = regressions(base, fake({"a": "FAIL"}, ci=True))
    want(rows == [] and "--ci" in why,
         f"--ci e non --ci non si confrontano: {rows} ({why})")

    rows, why = regressions(base, fake({"a": "FAIL"}, static=True))
    want(rows == [] and "modi diversi" in why,
         f"--static contro una baseline completa non si confronta: {rows} ({why})")

    rows, why = regressions(None, base)
    want(rows == [] and "nessuna baseline" in why,
         f"senza baseline non c'e' niente da difendere: {rows} ({why})")

    # Una baseline per modalita': un `--only` non deve poter sovrascrivere la completa.
    base_p = Path("reports") / "craft-bridge-tests.json"
    got = [baseline_name(base_p, s, o, c).name
           for s, o, c in ((False, None, False), (True, None, False), (False, None, True),
                           (False, "finestra PdfCraft!", False), (True, "cancello", True))]
    want(got == ["craft-bridge-tests.json", "craft-bridge-tests.static.json",
                 "craft-bridge-tests.ci.json",
                 "craft-bridge-tests.only-finestra-PdfCraft.json",
                 "craft-bridge-tests.static.only-cancello.ci.json"],
         f"nomi delle baseline: {got}")

    # Il codice d'uscita: 1 batte 3 (un guasto vero e' un guasto vero), 3 c'e' solo
    # quando l'unica cosa che non va e' la baseline peggiorata.
    for failed, regressed, want_code in ((0, 0, 0), (0, 1, 3), (1, 0, 1), (1, 1, 1)):
        got = exit_code(failed=failed, regressed=regressed)
        want(got == want_code,
             f"{failed} falliti e {regressed} regressioni dovrebbero dare {want_code}, non {got}")

    if problems:
        return "FAIL", "; ".join(problems)
    return "PASS", ("sei peggioramenti accusati, quattro casi innocenti, due confronti "
                    "rifiutati e i quattro codici d'uscita")


@case("confronto col feed del launcher", "unit")
def t_feed_compare(run: Runner) -> tuple[str, str]:
    """Il confronto installata/pubblicata, con un feed finto: niente rete, niente app."""
    body = b"pacchetto di prova\n"
    digest = hashlib.sha256(body).hexdigest()
    other = hashlib.sha256(b"altri byte\n").hexdigest()
    table = {"alpha": {"cli": "alpha.exe"}, "beta": {"cli": "beta.exe"},
             "delta": {"cli": "delta.exe"}}
    feed = {"dir": "prova", "fetched_at": None, "releases": {},
            "apps": {
                "alpha": {"name": "Alpha", "repo": "storytold/alpha", "version": "2.0.0",
                          "assets": [
                              {"name": "alpha-2.0.0-windows-x64.msi", "sha256": digest,
                               "platform": {"os": "windows", "arch": "x64",
                                            "package_type": "msi"}},
                              {"name": "alpha-2.0.0-altro.zip", "sha256": other,
                               "platform": {"os": "windows", "arch": "x64",
                                            "package_type": "portable_zip"}}]},
                "beta": {"name": "Beta", "repo": "storytold/beta", "version": "1.0.0",
                         "assets": []},
                "epsilon": {"name": "Epsilon", "repo": "storytold/epsilon",
                            "version": "3.0.0", "assets": []}}}
    installed = {"alpha": {"version": "1.0.0", "source": "prova"},
                 "beta": {"version": "1.0.0.0", "source": "prova"},
                 "delta": {"version": None, "source": "prova"}}
    downloads = run.tmp / "downloads"
    downloads.mkdir()
    (downloads / "alpha-2.0.0-windows-x64.msi").write_bytes(body)      # come pubblicato
    (downloads / "alpha-2.0.0-altro.zip").write_bytes(body)            # byte diversi
    (downloads / "estraneo.zip").write_bytes(b"x")                    # non e' nel feed

    rows = FEED.rows(table, feed, installed, downloads_dir=downloads, packages=True,
                     system="windows", machine="x64")
    by = {row["check"]: row for row in rows}
    problems = []
    def want(condition: bool, why: str) -> None:
        if not condition:
            problems.append(why)

    want(by["alpha"]["kind"] == "behind" and by["alpha"]["state"] == "nota",
         f"alpha dietro non accusata: {by['alpha']}")
    want(by["beta"]["kind"] == "same", f"1.0.0.0 e 1.0.0 dovrebbero coincidere: {by['beta']}")
    want(by["delta"]["kind"] == "absent", f"app fuori dal feed non segnalata: {by['delta']}")
    want("epsilon" in by["fuori dal ponte"]["detail"], "app del feed fuori dal ponte non elencata")
    want("alpha-2.0.0-windows-x64.msi (installer MSI" in by["pacchetto alpha"]["detail"],
         f"pacchetto di questo sistema non indicato: {by['pacchetto alpha']['detail']}")
    want(by["download alpha-2.0.0-windows-x64.msi"]["state"] == "ok",
         "i byte giusti non sono stati riconosciuti")
    want(by["download alpha-2.0.0-altro.zip"]["state"] == "fail",
         "i byte diversi non sono stati accusati")
    want(by["download estraneo.zip"]["state"] == "nota",
         "un file fuori dal feed non deve diventare un guasto")
    want(FEED.compare("0.8.2.0", "0.8.2") == "same", "le code di zeri non sono pareggiate")
    want(FEED.compare(None, "1.0.0") == "unknown", "senza versione installata si deve dire unknown")
    if problems:
        return "FAIL", "; ".join(problems)[:200]
    return "PASS", (f"{len(rows)} righe: dietro, pari, assente, estraneo e i tre casi "
                     f"di byte")


@case("byte pubblicati contro installati", "unit")
def t_feed_bytes(run: Runner) -> tuple[str, str]:
    """La CLI installata e' quella dentro il pacchetto? Con archivi finti, senza rete."""
    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    installed_dir = run.tmp / "installati"
    installed_dir.mkdir()
    mine = installed_dir / "alpha-cli.exe"
    mine.write_bytes(b"eseguibile di prova\n")
    diverso = installed_dir / "beta-cli.exe"
    diverso.write_bytes(b"altra build\n")
    archives = run.tmp / "archivi"
    archives.mkdir()

    def make_zip(name: str, members: dict) -> Path:
        path = archives / name
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as bundle:
            for member, data in members.items():
                bundle.writestr(member, data)
        return path

    alpha = make_zip("alpha-1.0.0-windows-x64-portable.zip",
                     {"alpha-1.0.0-windows-x64-portable/alpha-cli.exe": mine.read_bytes(),
                      "alpha-1.0.0-windows-x64-portable/README.md": b"x"})
    beta = make_zip("beta-1.0.0-windows-x64-portable.zip",
                    {"beta-1.0.0-windows-x64-portable/beta-cli.exe": b"byte diversi\n"})

    def asset(path: Path) -> dict:
        return {"name": path.name, "sha256": digest(path),
                "size_bytes": path.stat().st_size,
                "platform": {"os": "windows", "arch": "x64", "package_type": "portable_zip"}}

    problems = []
    def want(condition: bool, why: str) -> None:
        if not condition:
            problems.append(why)

    ok = FEED.compare_cli_bytes(alpha, asset(alpha), "alpha", mine)
    want(ok["state"] == "ok" and "byte per byte" in ok["detail"], f"byte uguali non riconosciuti: {ok}")
    bad = FEED.compare_cli_bytes(beta, asset(beta), "beta", diverso)
    want(bad["state"] == "fail" and bad["kind"] == "bytes", f"byte diversi non accusati: {bad}")
    manomesso = FEED.compare_cli_bytes(alpha, dict(asset(alpha), sha256="0" * 64), "alpha", mine)
    want(manomesso["state"] == "fail" and manomesso["kind"] == "hash",
         f"archivio non pubblicato non accusato: {manomesso}")
    assente = FEED.compare_cli_bytes(alpha, asset(alpha), "alpha", installed_dir / "manca.exe")
    want(assente["state"] == "nota", f"CLI installata assente non e' una nota: {assente}")
    membro = FEED.compare_cli_bytes(alpha, asset(alpha), "alpha", installed_dir / "gamma-cli.exe")
    want(membro["state"] == "nota", f"membro inesistente non e' una nota: {membro}")
    want(FEED.extract_member(alpha, "nonesiste.exe") is None, "estratto un membro che non c'e'")

    # La preferenza fra artefatti: l'archivio della sola CLI prima del pacchetto grande.
    feed = {"apps": {"alpha": {"repo": "storytold/alpha", "version": "1.0.0", "assets": [
        dict(asset(alpha)),
        {"name": "alpha-cli-1.0.0-windows-x64.zip", "sha256": "1" * 64, "size_bytes": 1,
         "platform": {"os": "windows", "arch": "x64", "package_type": "cli_zip"}}]}}}
    scelto = FEED.archive_for(feed["apps"]["alpha"], "windows", "x64")
    want(scelto and scelto["name"] == "alpha-cli-1.0.0-windows-x64.zip",
         f"scelto l'artefatto sbagliato: {scelto and scelto['name']}")

    # E il giro completo: la tabella, il feed e gli archivi sul disco (qui solo il
    # pacchetto portabile, che e' quello che c'e' davvero).
    table = {"alpha": {"cli": str(mine)}}
    feed_portabile = {"apps": {"alpha": {"repo": "storytold/alpha", "version": "1.0.0",
                                        "assets": [dict(asset(alpha))]}}}
    righe = FEED.rows(table, feed_portabile,
                      {"alpha": {"version": "1.0.0", "source": "prova"}},
                      archive_dirs=[archives], cli_paths={"alpha": str(mine)},
                      system="windows", machine="x64")
    riga = {r["check"]: r for r in righe}.get("byte alpha")
    want(riga is not None and riga["state"] == "ok", f"la riga dei byte non e' passata dal giro: {riga}")
    if problems:
        return "FAIL", "; ".join(problems)[:200]
    return "PASS", "uguali ok, diversi FIX, archivio manomesso FIX, assente nota, cli_zip preferito"


@case("feed assente non e' un guasto", "unit")
def t_feed_missing(run: Runner) -> tuple[str, str]:
    """Senza launcher non c'e' un termine di paragone, ma il ponte non e' rotto."""
    rows = DOC.check_published(CONFIG.apps_table(), run.tmp / "nessun-feed")
    if rows[0]["state"] != "nota":
        return "FAIL", f"atteso nota, ottenuto {rows[0]['state']}: {rows[0]['detail']}"
    if "feed assente" not in rows[0]["detail"]:
        return "FAIL", f"la nota non dice perche': {rows[0]['detail']}"
    return "PASS", "doctor: nota con la ragione, non un FIX"


@case("feed illeggibile o estraneo", "static")
def t_feed_files(run: Runner) -> tuple[str, str]:
    """Un feed che non c'e' o non si legge ha un esito suo: 3, non un guasto del ponte."""
    tool = HERE / "craft-bridge-feed.py"
    empty = run.tmp / "feed-vuoto"
    empty.mkdir()
    code, out, err = run.run(str(tool), "--feed-dir", str(empty))
    if code != 3 or "feed assente" not in out + err:
        return "FAIL", f"cartella senza feed: uscita {code} (attesa 3)"
    broken = run.tmp / "feed-rotto"
    broken.mkdir()
    (broken / "feed.json").write_text("{non e' json", encoding="utf-8")
    code, out, err = run.run(str(tool), "--feed-dir", str(broken))
    if code != 3 or "illeggibile" not in out + err:
        return "FAIL", f"feed illeggibile: uscita {code} (attesa 3)"
    alien = run.tmp / "feed-estraneo"
    alien.mkdir()
    (alien / "feed.json").write_text(json.dumps({"release_info": {
        "apps": {"epsilon": {"name": "Epsilon", "repo": "storytold/epsilon",
                              "latest_release": {"version": "3.0.0", "assets": []}}}}}),
        encoding="utf-8")
    code, out, _ = run.run(str(tool), "--feed-dir", str(alien))
    if code != 0 or "fuori dal ponte" not in out:
        return "FAIL", f"feed estraneo: uscita {code} (attesa 0): {out.strip()[:120]}"
    return "PASS", "assente 3, illeggibile 3, estraneo 0 (nessun guasto inventato)"


@case("porta chiusa", "live", env=True)
def t_closed_port(run: Runner) -> tuple[str, str]:
    table = CONFIG.apps_table()
    ports = configured_ports(table, CONFIG.DEFAULT_CONFIG)
    slug, port = "vectorcraft", ports["vectorcraft"]
    if not port_free(port):
        return "SKIP", f"porta {port} occupata: non tocco app che non ho avviato"
    code, out, _ = run.run(str(HERE / "craft-bridge-ident.py"), "--port", str(port), "--slug", slug, "--json")
    if code != 1 or '"peer": "unreachable"' not in out:
        return "FAIL", f"ident su porta chiusa ha dato uscita {code}"
    msg = ('{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":'
           '"2025-06-18","capabilities":{},"clientInfo":{"name":"test","version":"0"}}}\n')
    proc = subprocess.run([sys.executable, str(HERE / "craft-bridge-mcp.py"),
                           "--slug", slug, "--port", str(port)],
                          input=msg, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=90)
    if "modalita' headless" not in (proc.stderr or ""):
        return "FAIL", "lo shim non e' andato headless su porta chiusa"
    return "PASS", f"ident unreachable, shim headless (porta {port})"


# ---------------------------------------------------------------------------------
# I casi: con app vere (solo su porte libere, e le chiude la suite)
# ---------------------------------------------------------------------------------

@case("app giusta sulla porta", env=True)
def t_good_build(run: Runner) -> tuple[str, str]:
    table = CONFIG.apps_table()
    slug, port = "gridcraft", configured_ports(table, CONFIG.DEFAULT_CONFIG)["gridcraft"]
    if not port_free(port):
        return "SKIP", f"porta {port} occupata: non tocco app che non ho avviato"
    pid = run.launch(IDENT.configured_exe(table[slug]["cli"]), port)
    if not wait_open(port):
        return "FAIL", f"l'app non ha aperto la porta {port} (pid {pid})"
    try:
        code, out, _ = run.run(str(HERE / "craft-bridge-ident.py"), "--port", str(port),
                               "--slug", slug)
        code_d, out_d, _ = run.run(str(HERE / "craft-bridge-doctor.py"))
        code_l, out_l, _ = run.run(str(HERE / "craft-bridge-launch.py"), "--apps", slug)
    finally:
        kill(pid)
    if code != 0 or "stessa build" not in out:
        return "FAIL", f"ident sull'app giusta: uscita {code}"
    if code_d != 0 or f"porta {port}" not in out_d:
        return "FAIL", f"doctor: uscita {code_d} (attesa 0): {first_fix(out_d) or 'vedi doctor'}"
    if code_l != 0:
        return "FAIL", f"launcher: uscita {code_l}"
    return "PASS", f"{slug} {port}: ident/doctor/launcher tutti d'accordo"


@case("build diversa", env=True)
def t_drift_build(run: Runner) -> tuple[str, str]:
    table = CONFIG.apps_table()
    slug, port = "gridcraft", configured_ports(table, CONFIG.DEFAULT_CONFIG)["gridcraft"]
    if not port_free(port):
        return "SKIP", f"porta {port} occupata: non tocco app che non ho avviato"
    fake = run.tmp / "gridcraft-0.5.0.exe"
    patch_version(IDENT.configured_exe(table[slug]["cli"]), fake, "0.5.0")
    pid = run.launch(fake, port)
    if not wait_open(port):
        return "FAIL", f"la copia 0.5.0 non ha aperto la porta {port} (pid {pid})"
    try:
        code_i, out_i, _ = run.run(str(HERE / "craft-bridge-ident.py"), "--port", str(port),
                                   "--slug", slug, "--json")
        code_d, out_d, _ = run.run(str(HERE / "craft-bridge-doctor.py"))
        code_l, out_l, _ = run.run(str(HERE / "craft-bridge-launch.py"),
                                   "--apps", slug, "--port", f"{slug}={port}")
    finally:
        kill(pid)
    if code_i != 1 or '"build": "different"' not in out_i:
        return "FAIL", f"ident sulla build diversa: uscita {code_i} (attesa 1 con different)"
    if code_d != 1 or f"FIX  porta {port}" not in out_d or "gira 0.5.0" not in out_d:
        return "FAIL", f"doctor: uscita {code_d}, attesa 1 con la build numerata"
    if code_l != 1 or "NON e' quella configurata" not in out_l:
        return "FAIL", f"launcher: uscita {code_l}, attesa 1 con la diagnosi sulla build"
    return "PASS", "doctor, ident e launcher: tutti e tre exit 1 con 0.5.0 != 0.6.1"


@case("altra app sulla porta", env=True)
def t_wrong_app(run: Runner) -> tuple[str, str]:
    table = CONFIG.apps_table()
    ports = configured_ports(table, CONFIG.DEFAULT_CONFIG)
    victim, port = "deckcraft", ports["deckcraft"]
    if not port_free(port):
        return "SKIP", f"porta {port} occupata: non tocco app che non ho avviato"
    pid = run.launch(IDENT.configured_exe(table["gridcraft"]["cli"]), port)   # GridCraft sulla porta di DeckCraft
    if not wait_open(port):
        return "FAIL", f"GridCraft non ha aperto la porta {port} (pid {pid})"
    try:
        code_d, out_d, _ = run.run(str(HERE / "craft-bridge-doctor.py"))
        code_i, out_i, _ = run.run(str(HERE / "craft-bridge-ident.py"), "--port", str(port),
                                   "--slug", victim, "--json")
    finally:
        kill(pid)
    if code_d != 1 or f"FIX  porta {port}" not in out_d or "un'altra app" not in out_d:
        return "FAIL", f"doctor: uscita {code_d}, attesa 1 con l'app estranea"
    if code_i != 1 or '"identity": "mismatch"' not in out_i:
        return "FAIL", f"ident: uscita {code_i}, atteso mismatch"
    return "PASS", f"GridCraft su {port}: doctor e ident lo riconoscono"


@case("credenziale rifiutata", env=True)
def t_bad_token(run: Runner) -> tuple[str, str]:
    table = CONFIG.apps_table()
    port = configured_ports(table, CONFIG.DEFAULT_CONFIG)["photocraft"]
    if not port_free(port):
        return "SKIP", f"porta {port} occupata: non tocco app che non ho avviato"
    # Due token validi (PhotoCraft vuole 64 caratteri esadecimali) e diversi fra loro:
    # la config ne cita uno, l'app ne usa un altro. Nessuno dei due e' quello vero.
    mine, theirs = run.tmp / "token-config.token", run.tmp / "token-app.token"
    mine.write_text(secrets.token_hex(32) + "\n", encoding="utf-8")
    theirs.write_text(secrets.token_hex(32) + "\n", encoding="utf-8")

    def mutate(servers):
        args = servers["photocraft"]["args"]
        args[args.index("--token-file") + 1] = str(mine)
    config = temp_config(CONFIG.DEFAULT_CONFIG, mutate, run.tmp)
    pid = run.launch(IDENT.configured_exe(table["photocraft"]["cli"]), port,
                     "--control-token-file", str(theirs))
    try:
        if not wait_open(port):
            return "FAIL", f"PhotoCraft non ha aperto la porta {port} (pid {pid})"
        code_d, out_d, _ = run.run(str(HERE / "craft-bridge-doctor.py"), "--config", str(config))
        code_i, out_i, _ = run.run(str(HERE / "craft-bridge-ident.py"), "--port", str(port),
                                   "--slug", "photocraft", "--token-file", str(mine), "--json")
    finally:
        kill(pid)
    if code_d != 1 or f"FIX  porta {port}" not in out_d or "rifiutato la credenziale" not in out_d:
        return "FAIL", f"doctor: uscita {code_d}, attesa 1 con la credenziale rifiutata"
    if code_i != 1 or '"authenticated": false' not in out_i:
        return "FAIL", f"ident: uscita {code_i}, atteso authenticated=false"
    return "PASS", "token diverso: accusato da doctor e ident (valore mai stampato)"


@case("client MCP multipli", "static")
def t_connect_clients(run: Runner) -> tuple[str, str]:
    """Il connettore scrive nella forma giusta e non tocca quello che non e' suo.

    Tutto su file temporanei con `--client-path` (e `--client` limita i bersagli): la
    config vera di un client non e' una cavia, come per `--config` negli altri casi.
    Copre le tre forme che non sono `mcpServers`: VS Code, TOML di Codex, YAML di dsh.
    """
    root = run.tmp / "connect"
    root.mkdir()
    agents = root / "agents.json"
    agents.write_text(json.dumps({"mcpServers": {"keepme": {"type": "stdio",
                     "command": "x", "args": [], "env": {}}}}), encoding="utf-8")
    vscode = root / "vscode.json"
    vscode.write_text(json.dumps({"servers": {"keepme": {"type": "stdio",
                      "command": "x", "args": [], "env": {}}}}), encoding="utf-8")
    codex = root / "config.toml"
    codex.write_text('[mcp_servers.keepme]\ncommand = "x"\n', encoding="utf-8")
    dsh = root / "cordis.patch.yml"
    dsh.write_text("- insert:\n    - id: altri\n      name: '@altro/plugin'\n", encoding="utf-8")

    def conn(*extra: str):
        return run.run(str(HERE / "craft-bridge-connect.py"),
                       "--client", "agents", "--client", "vscode-workspace",
                       "--client", "codex", "--client", "dsh",
                       "--client-path", f"agents={agents}",
                       "--client-path", f"vscode-workspace={vscode}",
                       "--client-path", f"codex={codex}",
                       "--client-path", f"dsh={dsh}",
                       "--apps", "cadcraft,deckcraft", *extra)

    before = agents.read_text(encoding="utf-8")
    code, out, _ = conn()                                   # dry-run: non scrive
    if code != 0 or agents.read_text(encoding="utf-8") != before:
        return "FAIL", f"il dry-run ha scritto (uscita {code})"

    code, out, _ = conn("--apply")
    if code != 0:
        return "FAIL", f"apply uscita {code}: {out[-160:]}"
    data = json.loads(agents.read_text(encoding="utf-8"))
    if "keepme" not in data["mcpServers"] or "cadcraft" not in data["mcpServers"]:
        return "FAIL", "JSON mcpServers: entry aggiunte o estranee perse"
    args = data["mcpServers"]["cadcraft"].get("args") or []
    if not args or args[0] != str(CONFIG.DEFAULT_INSTALL_DIR / "craft-bridge-mcp.py"):
        return "FAIL", "JSON: gli args non puntano allo shim installato"
    vs = json.loads(vscode.read_text(encoding="utf-8"))
    if "cadcraft" not in (vs.get("servers") or {}):
        return "FAIL", "VS Code (.vscode): entry scritta sotto la chiave sbagliata"
    if "[mcp_servers.cadcraft]" not in codex.read_text(encoding="utf-8") or \
            "[mcp_servers.keepme]" not in codex.read_text(encoding="utf-8"):
        return "FAIL", "TOML: blocco mancante o estraneo perso"
    if "id: craft-bridge-cadcraft" not in dsh.read_text(encoding="utf-8") or \
            "id: altri" not in dsh.read_text(encoding="utf-8"):
        return "FAIL", "YAML: insert mancante o estraneo perso"

    code, out, _ = conn("--apply")                          # idempotente
    if "=2" not in out:
        return "FAIL", f"non idempotente: {out.strip().splitlines()[-1][:120]}"

    code, out, _ = conn("--restore", "--apply")            # toglie solo il nostro
    if "cadcraft" in agents.read_text(encoding="utf-8") or "keepme" not in agents.read_text(encoding="utf-8"):
        return "FAIL", "restore: il JSON non e' tornato com'era"
    if "[mcp_servers.cadcraft]" in codex.read_text(encoding="utf-8"):
        return "FAIL", "restore: il TOML non e' tornato com'era"
    if "craft-bridge-cadcraft" in dsh.read_text(encoding="utf-8"):
        return "FAIL", "restore: lo YAML non e' tornato com'era"
    return "PASS", "JSON, VS Code, TOML e YAML: scritti, idempotenti, restore pulito"


@case("report di stato", "static")
def t_report_status(run: Runner) -> tuple[str, str]:
    """Il report scrive il JSON e la pagina lo incorpora.

    Su una config **di prova** (`--config`, come `doctor`) e su file temporanei: cosi' il
    caso dice la stessa cosa qui e su un runner senza config, ed e' la prova che la
    sezione `config` viene dal file indicato invece che da quello della macchina. La
    versione precedente leggeva la config vera e sul runner falliva (`config` vuota),
    cioe' scambiava per guasto l'ambiente che le mancava: trovato dalla CI.
    """
    CONNECT = _load("craft_bridge_connect", "craft-bridge-connect.py")
    plan = CONNECT.plan(CONFIG.DEFAULT_INSTALL_DIR,
                        str(Path.home() / ".craft-bridge" / "photocraft.token"),
                        str(Path.home() / ".craft-bridge" / "pdfcraft-control.json"))
    config = run.tmp / "status-config.json"          # scritta da zero, non copiata
    config.write_text(json.dumps({"mcpServers": {s: CONNECT._json_shape("json", e)
                                                 for s, e in plan.items()}}), encoding="utf-8")

    out_json, out_html = run.tmp / "status.json", run.tmp / "status.html"
    code, out, err = run.run(str(HERE / "craft-bridge-report.py"),
                             "--no-doctor", "--no-clients", "--no-feed",
                             "--config", str(config),
                             "--out-json", str(out_json), "--out-html", str(out_html))
    if code != 0 or not out_json.is_file() or not out_html.is_file():
        return "FAIL", f"uscita {code}: {(err or out)[-160:]}"
    data = json.loads(out_json.read_text(encoding="utf-8"))
    cfg = data.get("config") or {}
    if data.get("schema") != "craft-bridge-status/1" or cfg.get("count") != len(plan):
        return "FAIL", (f"json: schema {data.get('schema')!r}, {cfg.get('count')} entry "
                        f"su {len(plan)} della config indicata")
    if cfg.get("path") != str(config):
        return "FAIL", f"json: la config letta non e' quella indicata ({cfg.get('path')})"
    modes = {s.get("slug"): s.get("mode") for s in cfg.get("servers") or []}
    if modes.get("cadcraft") != "shim" or modes.get("pdfcraft") != "traduttore":
        return "FAIL", f"json: i modi non tornano (cadcraft {modes.get('cadcraft')}, " \
                        f"pdfcraft {modes.get('pdfcraft')})"
    page = out_html.read_text(encoding="utf-8")
    for needle in ('id="data"', "bridge-status.json", "Craft Bridge"):
        if needle not in page:
            return "FAIL", f"html: manca {needle!r}"
    if "__DATA__" in page:
        return "FAIL", "html: il segnaposto dei dati non e' stato riempito"
    return "PASS", (f"json {cfg['count']} entry dalla config indicata (shim e traduttore), "
                     f"html {len(page)} byte")


@case("client MCP nella diagnosi", "static", env=True)
def t_client_check(run: Runner) -> tuple[str, str]:
    """`doctor` accusa un client presente senza le entry del ponte, e tace quando le ha.

    Su file di prova con `--client-path` (la config vera di un client non e' una cavia),
    nelle due direzioni: 0 entry -> FIX con l'azione, 13 entry -> nessun FIX.
    """
    root = run.tmp / "cli-check"
    root.mkdir()
    empty = root / "mcp.json"
    empty.write_text(json.dumps({"mcpServers": {"keepme": {"type": "stdio",
                     "command": "x", "args": [], "env": {}}}}), encoding="utf-8")
    code, out, _ = run.run(str(HERE / "craft-bridge-doctor.py"), "--no-live",
                           "--client-path", f"cursor={empty}")
    if code != 1 or "FIX  client MCP" not in out or "cursor 0/13" not in out or \
            "craft-bridge-connect.py --apply" not in out:
        return "FAIL", f"client senza entry non accusato (uscita {code})"

    CONNECT = _load("craft_bridge_connect", "craft-bridge-connect.py")
    plan = CONNECT.plan(CONFIG.DEFAULT_INSTALL_DIR,
                        str(Path.home() / ".craft-bridge" / "photocraft.token"),
                        str(Path.home() / ".craft-bridge" / "pdfcraft-control.json"))
    filled = root / "mcp-full.json"
    filled.write_text(json.dumps({"mcpServers":
                     {s: CONNECT._json_shape("json", e) for s, e in plan.items()}}),
                      encoding="utf-8")
    code2, out2, _ = run.run(str(HERE / "craft-bridge-doctor.py"), "--no-live",
                             "--client-path", f"cursor={filled}")
    if "FIX" in out2 and "client MCP" in out2:
        return "FAIL", "accusa un client che ha tutte le entry del ponte"
    return "PASS", f"accusa cursor 0/13 ({code}) e tace con le 13 ({code2})"


@case("report --serve", "static")
def t_report_serve(run: Runner) -> tuple[str, str]:
    """`--serve` apre un server locale che serve pagina e JSON: si prova per davvero.

    Su file temporanei (`--out-json`/`--out-html` dentro la cartella della suite), cosi'
    non tocca i report veri, e senza diagnosi (`--no-doctor`) perche' qui conta il server.
    """
    d = run.tmp / "serve"
    d.mkdir()
    oj, oh = d / "bridge-status.json", d / "bridge-status.html"
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen(
        [sys.executable, str(HERE / "craft-bridge-report.py"), "--serve", "--no-open",
         "--no-doctor", "--no-clients", "--no-feed", "--port", str(port),
         "--out-json", str(oj), "--out-html", str(oh)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        if not wait_open(port, 25.0):
            return "FAIL", "il server di --serve non si e' aperto"
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/bridge-status.html", timeout=5) as r:
            body = r.read().decode("utf-8", "replace")
            if r.status != 200 or "Craft Bridge" not in body:
                return "FAIL", f"la pagina non risponde bene (status {r.status})"
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/bridge-status.json", timeout=5) as r:
            if json.loads(r.read().decode("utf-8")).get("schema") != "craft-bridge-status/1":
                return "FAIL", "il JSON servito non ha lo schema atteso"
    finally:
        kill(proc.pid)
    return "PASS", f"servito su 127.0.0.1:{port}: pagina 200 e JSON con lo schema"


ALL = [t_clean, t_stale_install, t_bad_entry, t_broken_path, t_missing_exe,
       t_locations, t_locations_live, t_feed_compare, t_feed_bytes, t_feed_missing,
       t_feed_files, t_gate,
       t_closed_port, t_good_build, t_drift_build, t_wrong_app, t_bad_token,
       t_ui_args, t_ui_session, t_ui_headless, t_ui_live,
       t_flag_verdict, t_flag_doctor, t_flag_live,
       t_connect_clients, t_report_status, t_report_serve, t_client_check]

# Gli strumenti che la suite verifica: le loro impronte finiscono nel report, cosi'
# due esecuzioni a distanza si confrontano anche su *cosa* e' cambiato.
FINGERPRINTED = ("craft-bridge-mcp.py", "craft-bridge-ident.py", "craft-bridge-doctor.py",
                 "craft-bridge-config.py", "craft-bridge-feed.py", "craft-bridge-tests.py",
                 "craft-bridge-ui.py", "craft-bridge-connect.py", "craft-bridge-report.py")


def tool_hashes() -> dict:
    out = {}
    for name in FINGERPRINTED:
        path = HERE / name
        if path.is_file():
            out[name] = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    return out


# Gli stati in ordine di gravita': `PASS` provato, `SKIP` non provato (dichiarato),
# `FAIL` smentito. Perdere una prova sta in mezzo di proposito: non e' una smentita,
# ma non e' nemmeno una prova, e per un cancello che ferma un push e' la cosa che si
# vuole vedere ("la suite ha smesso di dimostrare questo").
STATE_RANK = {"PASS": 0, "SKIP": 1, "FAIL": 2}


def baseline_name(base: Path, static: bool, only: str | None, ci: bool) -> Path:
    """Il nome della baseline, uno per modalita': `craft-bridge-tests.static.json`.

    Una sola baseline condivisa non regge: `--static` o `--only` la sovrascriverebbero
    con un'esecuzione parziale, e da quel momento il cancello (o il job che la confronta)
    guarderebbe un file che non descrive piu' l'insieme. Provato: un `--only cancello`
    ha ridotto la baseline completa a un caso, in silenzio. Ogni modalita' ha quindi il
    suo file, accanto agli altri, e ognuna si confronta con la sua.
    """
    if not static and not ci and not only:
        return base
    parts = []
    if static:
        parts.append("static")
    if only:
        parts.append("only-" + re.sub(r"[^0-9A-Za-z._-]+", "-", only).strip("-"))
    if ci:
        parts.append("ci")
    return base.with_name(f"{base.stem}.{'.'.join(parts)}{base.suffix}")


def gate_modes(report: dict) -> tuple:
    """Cosa rende due esecuzioni confrontabili: la modalita', non l'ora."""
    modes = report.get("modes") or {}
    return (bool(modes.get("static")), modes.get("only"), bool(modes.get("ci")))


def regressions(previous: dict | None, report: dict) -> tuple[list[dict], str]:
    """I casi peggiorati rispetto alla baseline, e perche' il cancello non si applica.

    Non e' il confronto (quello racconta *tutto* cio' che e' cambiato, comprese le
    impronte degli strumenti): qui si risponde a una domanda sola - la suite ha perso
    o smentito qualcosa che la baseline dava per acquisito? - e si risponde solo dove
    la domanda ha senso, cioe' **stesso host e stessi modi**: su un'altra macchina gli
    stati non sono comparabili, e chiamarlo guasto sarebbe accusare l'ambiente.
    """
    if not previous:
        return [], "nessuna baseline da confrontare"
    if previous.get("host") != report.get("host"):
        return [], (f"baseline di un'altra macchina ({previous.get('host')} != "
                    f"{report.get('host')})")
    if gate_modes(previous) != gate_modes(report):
        was, now = gate_modes(previous), gate_modes(report)
        if bool((previous.get("modes") or {}).get("ci")) != bool(report["modes"].get("ci")):
            detail = "modi diversi: uno dei due e' --ci (i casi d'ambiente li' si saltano)"
        else:
            detail = f"modi diversi dalla baseline (static/only/ci {was} != {now})"
        return [], detail
    rows = []
    old = {c["case"]: c for c in previous.get("cases", [])}
    new = {c["case"]: c for c in report["cases"]}
    for name, case in new.items():
        was = old.get(name)
        if was is None:                       # un caso nuovo non e' una regressione
            continue
        if STATE_RANK.get(case["state"], 0) > STATE_RANK.get(was["state"], 0):
            rows.append({"case": name, "from": was["state"], "to": case["state"],
                         "why": case["detail"]})
    for name, was in old.items():
        if name not in new:                   # stessa perdita, vista dall'altro lato
            rows.append({"case": name, "from": was["state"], "to": "assente",
                         "why": "non piu' eseguito in questa modalita'"})
    return rows, ""


def exit_code(failed: int, regressed: int) -> int:
    """Il codice d'uscita: un guasto vero batte una regressione, perche' e' piu' grave.

    Una funzione per una riga? Si': e' la riga che decide se un push si ferma, e cosi'
    il caso `cancello sulle regressioni` la prova davvero invece di ripeterla a mano.
    """
    if failed:
        return 1
    if regressed:
        return 3
    return 0


def gate_line(report: dict) -> str:
    """Una riga sola sul cancello, anche quando non si applica."""
    gate = report.get("gate") or {}
    if not gate.get("applied"):
        return f"cancello non applicato: {gate.get('why')}"
    rows = report.get("regressions") or []
    if not rows:
        return "cancello: nessuna regressione rispetto alla baseline"
    return (f"cancello: {len(rows)} regressione/i rispetto alla baseline "
            f"({friendly(report.get('compared_with'))})")


def build_report(results: list[dict], args, seconds: float, previous: dict | None) -> dict:
    failed = [r for r in results if r["state"] == "FAIL"]
    skipped = [r for r in results if r["state"] == "SKIP"]
    return {
        "when": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "host": socket.gethostname(),
        "python": sys.version.split()[0],
        "modes": {"static": bool(args.static), "only": args.only, "ci": bool(args.ci)},
        "tools": tool_hashes(),
        "cases": results,
        "passed": len(results) - len(failed) - len(skipped),
        "failed": len(failed),
        "skipped": len(skipped),
        "ok": not failed,
        "seconds": round(seconds, 1),
        "compared_with": (previous or {}).get("when"),
        "previous_seconds": (previous or {}).get("seconds"),
    }


def compare(previous: dict | None, report: dict) -> list[str]:
    """Cosa e' cambiato dall'esecuzione precedente: casi e strumenti."""
    if not previous:
        return []
    rows = []
    old = {c["case"]: c for c in previous.get("cases", [])}
    new = {c["case"]: c for c in report["cases"]}
    for name, case in new.items():
        was = old.get(name)
        if was is None:
            rows.append(f"`{name}`: nuovo ({case['state']})")
        elif was["state"] != case["state"]:
            rows.append(f"`{name}`: {was['state']} -> **{case['state']}** ({case['detail']})")
    for name in old:
        if name not in new:
            rows.append(f"`{name}`: non piu' eseguito (era {old[name]['state']})")
    for name, digest in report["tools"].items():
        was = (previous.get("tools") or {}).get(name)
        if was and was != digest:
            rows.append(f"`{name}`: {was} -> {digest}")
        elif not was:
            rows.append(f"`{name}`: nuovo strumento ({digest})")
    return rows


def duration_line(report: dict) -> str | None:
    """La durata non e' un cambiamento: e' contesto, e si stampa a parte."""
    before = report.get("previous_seconds")
    now = report["seconds"]
    if before is None:
        return f"durata: {now}s"
    return f"durata: {now}s (precedente {before}s, {now - float(before):+.1f}s)"


def friendly(stamp: str | None) -> str:
    """Una data del report in forma leggibile (`2026-10-13T15:53` -> `13/10/2026 15:53`)."""
    if not stamp:
        return "?"
    try:
        return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S").strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return stamp


def plain(row: str) -> str:
    """Le stesse righe di confronto, senza i segni di markdown: per il terminale."""
    return row.replace("`", "").replace("**", "")


def markdown(report: dict, changes: list[str], previous: dict | None) -> str:
    when = friendly(report["when"])
    mark = {"PASS": "ok", "FAIL": "**FAIL**", "SKIP": "saltato"}
    lines = [
        "# Report della suite di guasti",
        "",
        f"**Generato:** {when} · **host:** {report['host']} · **Python:** {report['python']}",
        f"**Modi:** {'solo statici' if report['modes']['static'] else 'completo'}"
        + (f" · filtro `{report['modes']['only']}`" if report["modes"]["only"] else "")
        + (" · CI (casi d'ambiente saltati)" if report["modes"].get("ci") else "")
        + f" · **durata:** {report['seconds']}s",
        "**Strumenti:** " + " · ".join(f"`{n.replace('craft-bridge-', '').replace('.py', '')}` "
                                      f"`{h}`" for n, h in report["tools"].items()),
        "",
        "## Esito",
        "",
        f"**{report['passed']} passati, {report['failed']} falliti, {report['skipped']} saltati**"
        + (" → tutto in ordine" if report["ok"] else " → da guardare"),
        "",
        "| Caso | Tipo | Stato | Secondi | Dettaglio |",
        "|---|---|---|---|---|",
    ]
    for case in report["cases"]:
        detail = case["detail"].replace("|", "\\|")
        lines.append(f"| {case['case']} | {case['kind']} | {mark[case['state']]} | "
                     f"{case['seconds']} | {detail} |")
    lines += ["", "## Confronto con l'esecuzione precedente", ""]
    if previous is None:
        lines.append("Nessun report precedente: questo e' il riferimento.")
    elif not changes:
        lines.append(f"Niente e' cambiato rispetto al report del {friendly(previous.get('when'))}.")
    else:
        lines.append(f"Rispetto al report del {friendly(previous.get('when'))}:")
        lines += [""] + [f"- {row}" for row in changes]
    lines += ["", duration_line(report), ""]
    # Il cancello ha una sezione sua: il confronto racconta cosa e' cambiato, questa
    # dice se qualcosa e' **peggiorato**, che e' la domanda per cui si ferma un push.
    rows = report.get("regressions") or []
    applied = (report.get("gate") or {}).get("applied")
    lines += ["", "## Regressioni (cancello)", ""]
    if not rows:
        lines.append("Nessuna regressione: la baseline regge." if applied else
                     f"Niente da confrontare: {(report.get('gate') or {}).get('why')}.")
    else:
        lines.append(("Peggiorati rispetto alla baseline "
                      f"({friendly(report.get('compared_with'))}), uscita 3:") if applied else
                     ("Peggiorati rispetto alla baseline "
                      f"({friendly(report.get('compared_with'))}), ma il cancello non decide: "
                      f"{(report.get('gate') or {}).get('why')}:"))
        lines += [""] + [f"- `{r['case']}`: {r['from']} -> **{r['to']}** ({r['why']})"
                         for r in rows]
    lines += [""]
    return "\n".join(lines)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser()
    parser.add_argument("--static", action="store_true", help="solo i casi senza app avviate")
    parser.add_argument("--ci", action="store_true",
                        help="salta spiegando perche' i casi che richiedono il ponte "
                             "installato su questa macchina (per un runner di CI)")
    parser.add_argument("--only", help="filtra per nome (sottostringa)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report", "--out", dest="report", default=None,
                        help="dove scrivere i report (default: reports/ nel progetto, con la "
                             "modalita' nel nome: `craft-bridge-tests.json` per l'esecuzione "
                             "completa, `.static.json` con --static, `.ci.json` con --ci, "
                             "`.only-<filtro>.json` con --only; il markdown prende lo stesso "
                             "nome, .md); `--out` come negli altri strumenti del progetto")
    parser.add_argument("--no-report", action="store_true", help="non scrivere niente su disco")
    parser.add_argument("--no-status", action="store_true",
                        help="non rigenerare il report di stato (reports/bridge-status.json e "
                             ".html) a fine esecuzione; di default lo rigenera, cosi' la pagina "
                             "riflette sempre l'ultima esecuzione")
    parser.add_argument("--compare",
                        help="confronta con un report precedente "
                             "(default: il report stesso, cioe' l'esecuzione precedente)")
    parser.add_argument("--no-compare", action="store_true")
    parser.add_argument("--no-gate", action="store_true",
                        help="confronta senza decidere: una regressione rispetto alla "
                             "baseline non cambia il codice d'uscita")
    args = parser.parse_args()

    # La baseline e' quella della **propria** modalita': la completa resta la completa
    # anche se poi gira un `--static` (vedi `baseline_name`).
    target = Path(args.report) if args.report else baseline_name(DEFAULT_REPORT, args.static,
                                                               args.only, args.ci)
    # Il confronto e' automatico col report che si sta per sovrascrivere: basta
    # rieseguire la suite nella stessa cartella per vedere cosa e' cambiato.
    previous, previous_from = None, None
    if not args.no_compare:
        previous_from = Path(args.compare) if args.compare else (
            None if args.no_report else target)
        if previous_from is not None:
            if previous_from.is_file():
                try:
                    previous = json.loads(previous_from.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    print(f"[!] report precedente illeggibile ({previous_from}): {exc}",
                          file=sys.stderr)
            elif args.compare:
                print(f"[!] nessun report da confrontare in {previous_from}", file=sys.stderr)

    cases = ALL
    if args.static:
        cases = [c for c in cases if c.case_kind != "e2e"]
    if args.only:
        cases = [c for c in cases if args.only.lower() in c.case_name.lower()]
    if not cases:
        print("nessun caso da eseguire", file=sys.stderr)
        return 2

    run = Runner()
    results = []
    started_all = time.time()
    if not args.json:                                    # come il doctor: o umano o JSON
        print("craft-bridge tests")
    try:
        for fn in cases:
            started = time.time()
            gap = environment_gap() if (args.ci and fn.case_env) else None
            try:
                if gap:
                    state, detail = "SKIP", f"ambiente assente su questo runner: {gap}"
                else:
                    state, detail = fn(run)
            except Exception as exc:                     # un caso non deve fermare la suite
                state, detail = "FAIL", f"eccezione: {type(exc).__name__}: {exc}"
            results.append({"case": fn.case_name, "kind": fn.case_kind, "state": state,
                            "detail": detail, "seconds": round(time.time() - started, 1)})
            if not args.json:
                mark = {"PASS": "ok  ", "FAIL": "FAIL", "SKIP": "skip"}[state]
                print(f"  {mark} {fn.case_name:<26} {detail}")
    finally:
        run.cleanup()

    failed = [r for r in results if r["state"] == "FAIL"]
    skipped = [r for r in results if r["state"] == "SKIP"]
    report = build_report(results, args, time.time() - started_all, previous)
    changes = compare(previous, report)
    report["changes"] = changes
    # Il cancello legge la baseline, non il report che si sta scrivendo: se la modalita'
    # non combacia (o la baseline non c'e') lo dice e non decide niente, invece di
    # accusare l'ambiente di una differenza che non e' un guasto. `--no-gate` toglie la
    # decisione, non la misura: cosa e' peggiorato resta scritto nel report.
    rows, why = regressions(previous, report)
    if args.no_gate and not why:
        why = "--no-gate: le regressioni sono registrate ma non decidono l'uscita"
    report["regressions"] = rows
    report["gate"] = {"applied": not why, "why": why}
    report["regressed"] = len(rows)

    if not args.no_report:
        json_path = target
        md_path = json_path.with_suffix(".md")
        report["report_files"] = {"json": str(json_path), "markdown": str(md_path)}
        try:
            json_path.parent.mkdir(parents=True, exist_ok=True)
            json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")
            md_path.write_text(markdown(report, changes, previous), encoding="utf-8")
        except OSError as exc:
            print(f"[!] report non scritto: {exc}", file=sys.stderr)

    # A fine esecuzione la pagina di stato si rigenera da sola: legge le baseline appena
    # scritte, quindi mostra l'ultima esecuzione invece di una fotografia vecchia. Non e'
    # una misura in piu' (chiede a `craft-bridge-report.py`, che a sua volta chiede a
    # doctor), quindi un suo guasto non fa fallire la suite: lo si dice e basta.
    if not args.no_report and not args.no_status:
        proc = subprocess.run([sys.executable, str(HERE / "craft-bridge-report.py")],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            print(f"[!] stato non rigenerato: {(proc.stderr or proc.stdout or '').strip()[-160:]}",
                  file=sys.stderr)
        elif not args.json:
            print("\nstato: reports/bridge-status.json · reports/bridge-status.html")

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"\n{report['passed']} passati, {len(failed)} falliti, {len(skipped)} saltati")
        if failed:
            print("falliti:")
            for r in failed:
                print(f"  - {r['case']}: {r['detail']}")
        if skipped:
            print("saltati:")
            for r in skipped:
                print(f"  - {r['case']}: {r['detail']}")
        if previous_from is not None and not args.no_compare:
            if previous is None:
                print(f"\nconfronto: nessun report precedente in {previous_from}"
                      f" - questo diventa il riferimento")
            elif not changes:
                print(f"\nconfronto con {previous_from}: niente e' cambiato")
            else:
                print(f"\nconfronto con {previous_from}:")
                for row in changes:
                    print(f"  - {plain(row)}")
            print(f"  {duration_line(report)}")
        if rows:
            print("\nregressioni rispetto alla baseline:")
            for row in rows:
                print(f"  - {row['case']}: {row['from']} -> {row['to']} ({row['why']})")
        print(f"\n{gate_line(report)}")
        if report.get("report_files"):
            print(f"\nreport: {report['report_files']['json']}"
                  f"  ·  {report['report_files']['markdown']}")
    return exit_code(len(failed), len(rows) if not args.no_gate else 0)


if __name__ == "__main__":
    sys.exit(main())
