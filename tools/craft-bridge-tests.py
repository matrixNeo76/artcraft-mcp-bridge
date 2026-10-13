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

Esito:
    0  ogni caso passato (le SKIP non sono guasti)
    1  almeno un FAIL
    2  errore d'uso
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
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


ALL = [t_clean, t_stale_install, t_bad_entry, t_broken_path, t_missing_exe, t_closed_port,
       t_good_build, t_drift_build, t_wrong_app, t_bad_token]

# Gli strumenti che la suite verifica: le loro impronte finiscono nel report, cosi'
# due esecuzioni a distanza si confrontano anche su *cosa* e' cambiato.
FINGERPRINTED = ("craft-bridge-mcp.py", "craft-bridge-ident.py", "craft-bridge-doctor.py",
                 "craft-bridge-config.py", "craft-bridge-tests.py")


def tool_hashes() -> dict:
    out = {}
    for name in FINGERPRINTED:
        path = HERE / name
        if path.is_file():
            out[name] = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    return out


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
    parser.add_argument("--report", "--out", dest="report", default=str(DEFAULT_REPORT),
                        help="dove scrivere i report (default: reports/ nel progetto; il "
                             "markdown prende lo stesso nome, .md); `--out` come negli altri "
                             "strumenti del progetto")
    parser.add_argument("--no-report", action="store_true", help="non scrivere niente su disco")
    parser.add_argument("--compare",
                        help="confronta con un report precedente "
                             "(default: il report stesso, cioe' l'esecuzione precedente)")
    parser.add_argument("--no-compare", action="store_true")
    args = parser.parse_args()

    # Il confronto e' automatico col report che si sta per sovrascrivere: basta
    # rieseguire la suite nella stessa cartella per vedere cosa e' cambiato.
    previous, previous_from = None, None
    if not args.no_compare:
        previous_from = Path(args.compare) if args.compare else (
            None if args.no_report else Path(args.report))
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

    if not args.no_report:
        json_path = Path(args.report)
        md_path = json_path.with_suffix(".md")
        report["report_files"] = {"json": str(json_path), "markdown": str(md_path)}
        try:
            json_path.parent.mkdir(parents=True, exist_ok=True)
            json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")
            md_path.write_text(markdown(report, changes, previous), encoding="utf-8")
        except OSError as exc:
            print(f"[!] report non scritto: {exc}", file=sys.stderr)

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
        if report.get("report_files"):
            print(f"\nreport: {report['report_files']['json']}"
                  f"  ·  {report['report_files']['markdown']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
