#!/usr/bin/env python3
"""Shim stdio MCP: guida l'app Craft aperta, altrimenti ripiega sull'headless.

Le `*-cli.exe` delle Crafting Apps sanno fare da server MCP in due modi:

  * **headless** — sessione in-process, nessuna finestra (il comportamento di
    default, quello che la config `~/.agents/mcp.json` usa oggi);
  * **bridged** — `mcp --connect/--bridge <addr>` inoltra ogni chiamata al
    canale di controllo dell'app desktop aperta, cosi' l'agente vede e muove la
    finestra vera (stato UI, screenshot, documenti aperti).

Collegato a un'app **irraggiungibile** il bridged non ripiega: esce con un errore
(verificato su GridCraft e PhotoCraft). Se pero' sulla porta risponde qualcos'altro
che *accetta la connessione* e poi tace, almeno una CLI (DeckCraft, misurato)
prosegue in headless **senza dirlo** — 25 tool e nessun errore: un bridge che non
bridga. Quindi una `connect()` non basta a dire "bridged".

La scelta del modo si fa quindi con un **handshake**: il canale e' JSON-lines e
ogni app risponde a qualsiasi richiesta ben formata, anche a un metodo che non
conosce, ripetendo l'`id` con `ok`/`error`/`result`.

    -> {"id":1,"method":"__craft_bridge_ident__","params":{}}
    <- {"error":"unknown method `__craft_bridge_ident__`","id":1,"ok":false}

Quella firma = c'e' il canale; silenzio o byte estranei = sulla porta c'e' altro, e
si va in **headless** dichiarandolo, invece di promettere un bridged che poi ripiega
da solo. La riga di stato su stderr dice sempre il modo e la ragione.

Il canale dice anche *quale app* risponde (dal catalogo dei comandi che dichiara), non
quale versione: due build della stessa app coprono lo stesso catalogo, quindi il peer
sembra a posto anche quando l'eseguibile in ascolto non e' quello che la config
avvierebbe. All'avvio, quindi, si controlla anche la **build** (`craft-bridge-ident.py
--build-only`: PID della porta, versione di quell'eseguibile, versione dichiarata
dall'app nel proprio log) e una divergenza fa scrivere un avviso. Non fa andare
headless: il protocollo e' lo stesso, e il silenzio nasconderebbe proprio il caso in
cui si guida la finestra sbagliata.

Lo stesso controllo e' anche uno strumento a se' (diagnosi, verifica di una porta,
tutte le app insieme): `craft-bridge-ident.py`.

Il modo si sceglie **una volta sola, all'avvio**, di proposito: i due modi
espongono liste di tool diverse (il bridged aggiunge i tool `ui_*`) e cambiare
modo a metà sessione lascerebbe il client con un `tools/list` stantio. Se l'app
viene chiusa durante la sessione, le chiamate falliscono con un errore esplicito
per chiamata (misurato: `... is not reachable: connection timed out`), senza che
il server MCP muoia: basta riaprire l'app e, se serve, rifare la connessione dal
pannello Connectors.

Uso (come `command`/`args` di una entry MCP):
    python craft-bridge-mcp.py --slug lightcraft --port 7980

    # PhotoCraft richiede il control-token: il file lo scrive l'app stessa
    python craft-bridge-mcp.py --slug photocraft --port 7976 \
        --token-file C:/Users/me/.craft-bridge/photocraft.token

    --require-bridge   non ripiegare: se l'app non risponde al protocollo, esce 3

Esito: quello del server MCP, oppure 3 se --require-bridge e nessun peer Craft
risponde sulla porta.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

# slug -> (percorso CLI, flag del bridge, modello dell'indirizzo, flag opzionali)
APPS: dict[str, dict] = {
    "cadcraft":    {"cli": r"C:\Program Files\CADCraft\cadcraft-cli.exe",
                    "flag": "--connect", "addr": "127.0.0.1:{port}", "port": 7971},
    "deckcraft":   {"cli": r"C:\Program Files\DeckCraft\deckcraft-cli.exe",
                    "flag": "--connect", "addr": "{port}", "port": 7972},
    "designcraft": {"cli": r"C:\Program Files\DesignCraft\designcraft-cli.exe",
                    "flag": "--connect", "addr": "{port}", "port": 7973},
    "effectcraft": {"cli": r"C:\Program Files\EffectCraft\effectcraft-cli.exe",
                    "flag": "--bridge", "addr": "{port}", "port": 9877},
    "filmcraft":   {"cli": r"C:\Program Files\FilmCraft\filmcraft-cli.exe",
                    "flag": "--bridge", "addr": "127.0.0.1:{port}", "port": 7974},
    "gridcraft":   {"cli": r"C:\Program Files\GridCraft\gridcraft-cli.exe",
                    "flag": "--connect", "addr": "{port}", "port": 7975},
    "lightcraft":  {"cli": r"C:\Program Files\LightCraft\lightcraft-cli.exe",
                    "flag": "--connect", "addr": "127.0.0.1:{port}", "port": 7980},
    "photocraft":  {"cli": r"C:\Program Files\PhotoCraft\photocraft-cli.exe",
                    "flag": "--bridge", "addr": "127.0.0.1:{port}", "port": 7976,
                    "needs_token": True},
    "soundcraft":  {"cli": r"C:\Program Files\SoundCraft\soundcraft-cli.exe",
                    "flag": "--connect", "addr": "{port}", "port": 7977},
    "vectorcraft": {"cli": r"C:\Program Files\VectorCraft\vectorcraft-cli.exe",
                    "flag": "--connect", "addr": "127.0.0.1:{port}", "port": 7979},
    "wordcraft":   {"cli": r"C:\Program Files\WordCraft\wordcraft-cli.exe",
                    "flag": "--connect", "addr": "127.0.0.1:{port}", "port": 7978},
}

# ---------------------------------------------------------------------------------
# Dove sta davvero l'app
# ---------------------------------------------------------------------------------
#
# I percorsi qui sopra sono quelli che ci **ricordiamo**. Windows registra quelli
# veri: aprendo un'app per nome, l'interfaccia di sistema legge `App Paths`, e quelle
# voci le scrive l'installer dell'app — quindi le aggiorna chi reinstalla, non noi. La
# tabella resta come ultima risorsa, ma la fonte dei percorsi e' il sistema, e quando
# i due non coincidono la differenza si vede invece di restare sotto un percorso
# scritto a mano che nessuno controlla piu'.
#
# Del **launcher** di ArtCraft qui non si usa niente per avviare: non ha un modo da
# riga di comando per farlo (l'unico flag accettato e' `--hidden`, nessuno schema URL,
# e le issue del progetto lo chiedono come funzione mancante). Il launcher sa quali
# release **esistono** — quel lato lo legge `craft-bridge-feed.py` — non dove sono
# installate. E' pero' lui a mostrare che in questo ecosistema le installazioni
# per-utente esistono: il launcher si registra in `HKCU`, non in `HKLM`.
APP_PATHS = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"


# I nomi dei file di ogni app, in un posto solo: la CLI e l'app hanno lo stesso nome
# di base, e questo vale per tutte e undici (verificato).
def cli_beside(app_exe: str) -> Path:
    return Path(app_exe).with_name(Path(app_exe).stem + "-cli.exe")


def registered_exe(slug: str) -> tuple[str | None, str | None]:
    """Cosa il **sistema** registra per quell'app: `(percorso, hive)`, o `(None, None)`.

    `winreg` e non PowerShell: questo codice gira all'avvio di ogni sessione MCP, e
    una lettura del registro costa millisecondi mentre un processo in piu' costerebbe
    quanto l'handshake. Si provano le due viste (64 e 32 bit: l'app puo' essere
    registrata nell'una o nell'altra) e **i due hive**, utente prima di macchina:
    un'app installata "solo per me" finisce in `HKCU`, una per tutti in `HKLM`, e
    questo e' l'ordine con cui Windows risolve il nome di un programma. Il launcher
    stesso sta in `HKCU` — guardare solo `HKLM` renderebbe invisibile
    un'installazione per-utente, cioe' di nuovo un percorso vecchio al posto di quello
    vero. `hive` dice da dove viene, cosi' il fatto si vede invece di restare implicito.
    """
    if os.name != "nt":
        return None, None
    try:
        import winreg
    except ImportError:
        return None, None
    hives = (("utente", winreg.HKEY_CURRENT_USER), ("macchina", winreg.HKEY_LOCAL_MACHINE))
    for hive_name, hive in hives:
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive, f"{APP_PATHS}\\{slug}.exe", 0,
                                    winreg.KEY_READ | view) as key:
                    value, _ = winreg.QueryValueEx(key, "")     # valore predefinito
            except OSError:
                continue
            if value:
                return str(value), hive_name
    return None, None


def choose_cli(registered: str | None, declared: str,
               hive: str | None = None) -> tuple[str, str]:
    """Quale CLI usare e da dove viene. Funzione pura: si prova senza toccare il registro.

    Tre esiti, in ordine di fiducia: la CLI che sta **accanto all'app che il sistema
    registra** (e l'esito dice anche da quale hive viene), la CLI dichiarata qui,
    oppure la dichiarata **assente** — che e' una informazione, non un silenzio: chi
    legge sa che quel percorso non esiste.
    """
    if registered:
        beside = cli_beside(registered)
        if beside.is_file():
            return str(beside), (f"registro App Paths ({hive})" if hive
                                 else "registro App Paths")
    if Path(declared).is_file():
        return declared, "tabella"
    return declared, "tabella (assente sul disco)"


_RESOLVED: dict | None = None


def app_table() -> dict:
    """La tabella con i percorsi risolti: la usano lo shim, l'installer e la diagnosi.

    Oltre a `cli` (quello da usare) restano visibili `cli_source` (da dove viene),
    `declared_cli` (cosa dicevamo noi) e `app_exe` (cosa dice il sistema): senza questi
    tre campi uno scostamento fra tabella e sistema sarebbe invisibile, che e' il modo
    in cui un percorso cablato invecchia senza che nessuno se ne accorga.
    """
    global _RESOLVED
    if _RESOLVED is None:
        _RESOLVED = {}
        for slug, spec in APPS.items():
            app, hive = registered_exe(slug)
            cli, source = choose_cli(app, spec["cli"], hive)
            _RESOLVED[slug] = {**spec, "cli": cli, "cli_source": source,
                               "declared_cli": spec["cli"], "app_exe": app,
                               "app_hive": hive}
    return _RESOLVED


# ---------------------------------------------------------------------------------
# Il flag di aggancio: quello che la tabella dichiara, e quello che la CLI dice di se'
# ---------------------------------------------------------------------------------
#
# La tabella dice **quale flag** serve per guidare la finestra (`--connect` o
# `--bridge`), e per le app servite dal traduttore dice che un flag non c'e' affatto.
# E' una dichiarazione, e invecchia come tutte: un'app aggiornata che rinomina o toglie
# l'opzione lascerebbe la tabella a promettere qualcosa che non esiste, e il guasto
# arriverebbe all'avvio del connettore, lontano da qui. Quindi la stessa domanda si fa
# alla CLI, nel suo help: e' **la sua** interfaccia, non la nostra memoria.

BRIDGE_FLAGS = ("--connect", "--bridge")


def cli_help(cli: str, timeout: float = 20.0) -> dict:
    """L'help che la CLI da' di se stessa. Vuoto = non leggibile, e lo dice."""
    if not Path(cli).is_file():
        return {"readable": False, "why": f"CLI assente sul disco: {cli}", "text": ""}
    try:
        proc = subprocess.run([cli, "--help"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"readable": False, "why": f"help non leggibile: {exc}", "text": ""}
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if not text:
        return {"readable": False, "why": f"help vuoto (uscita {proc.returncode})",
                "text": ""}
    return {"readable": True, "text": text, "exit": proc.returncode}


def flag_facts(slug: str, spec: dict, timeout: float = 20.0) -> dict:
    """Il flag della tabella contro quello che l'help della CLI documenta.

    Tre esiti per le app con un flag dichiarato (`--connect`/`--bridge`): `ok` se
    l'help lo nomina, `diverge` se non lo nomina — la tabella afferma un'opzione che la
    CLI non documenta — e `non leggibile` se la CLI non da' un help, che e' una lacuna
    dichiarata, non un ok. Per le app **senza** flag (quelle del traduttore) la domanda
    si rovescia: l'help non deve nominare `--connect`/`--bridge`, e deve documentare il
    canale che si usa invece (`--control`).
    """
    help_ = cli_help(str(spec.get("cli") or ""), timeout)
    text = help_.get("text", "")
    seen = [f for f in BRIDGE_FLAGS if f in text]
    declared = spec.get("flag")
    control = spec.get("control_flag")
    row = {"check": slug, "declared": declared, "cli": str(spec.get("cli") or ""),
           "translated": bool(spec.get("translated")), "documents": seen,
           "why": help_.get("why", "")}
    if not help_["readable"]:
        row.update(state="non leggibile",
                   detail=f"la CLI non da' un help ({help_['why']}): il flag resta una "
                          f"dichiarazione della tabella")
        return row
    if declared:
        if declared in text:
            row.update(state="ok", detail=f"l'help della CLI documenta `{declared}`")
        else:
            extra = f" (nomina {', '.join(seen)})" if seen else " (non ne nomina nessuno)"
            row.update(state="diverge",
                       detail=f"la tabella dichiara `{declared}`, l'help non lo nomina{extra}")
        return row
    if seen:
        row.update(state="diverge",
                   detail=f"la tabella non usa un flag di aggancio, ma l'help nomina "
                          f"{', '.join(seen)}: la CLI sa agganciarsi")
        return row
    if control and control not in text:
        row.update(state="non leggibile",
                   detail=f"l'help non nomina ne' {', '.join(BRIDGE_FLAGS)} ne' "
                          f"`{control}`: non si sa come si guidi questa CLI")
        return row
    row.update(state="ok",
               detail=(f"l'help non ha {', '.join(BRIDGE_FLAGS)} e documenta `{control}`: "
                       f"si guida per traduzione" if control else
                       f"l'help non ha {', '.join(BRIDGE_FLAGS)}"))
    return row


def flag_report(apps: dict | None = None, timeout: float = 20.0) -> dict:
    """Il verdetto su tutte le app: quante confermate, quali no, quali non leggibili.

    Gli help si chiedono **in parallelo**: sono processi indipendenti e brevi (~0,06 s
    l'uno), e in fila facevano ~0,8 s a ogni giro del doctor. L'ordine dei risultati
    resta quello della tabella.
    """
    table = apps if apps is not None else app_table()
    slugs = sorted(table)
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(slugs) or 1)) as pool:
        rows = list(pool.map(lambda s: flag_facts(s, table[s], timeout), slugs))
    return {"rows": rows,
            "ok": [r["check"] for r in rows if r["state"] == "ok"],
            "diverging": [r["check"] for r in rows if r["state"] == "diverge"],
            "unreadable": [r["check"] for r in rows if r["state"] == "non leggibile"],
            "total": len(rows)}


HERE = Path(__file__).resolve().parent
BUILD_TOOL = HERE / "craft-bridge-ident.py"

PROBE_TIMEOUT = 0.6
HANDSHAKE_TIMEOUT = 1.5

# Metodo inesistente di proposito: la risposta attesa e' l'errore, che prova il
# protocollo senza dipendere da un metodo presente in tutte le app.
IDENT_METHOD = "__craft_bridge_ident__"


def craft_peer(port: int, host: str = "127.0.0.1") -> str:
    """Chi c'e' sulla porta: `craft`, `silent`, `foreign` o `closed`.

    `silent` e' il caso insidioso: la connessione riesce (qualcosa ascolta) ma il
    peer non parla il protocollo. Un secondo tentativo copre l'app momentaneamente
    occupata, cosi' un'app viva ma lenta non viene declassata per sbaglio.
    """
    for timeout in (HANDSHAKE_TIMEOUT, HANDSHAKE_TIMEOUT * 2):
        verdict = _ask_protocol(port, host, timeout)
        if verdict != "silent":
            return verdict
    return "silent"


# Quanta parte del catalogo locale deve coprire il peer per essere "questa app".
# Misurato: l'app giusta copre 1.00, qualunque altra app sta sotto 0.15.
MATCH_COVERAGE = 0.9


def _request(sock, method: str, params: dict, timeout: float, ident: int = 1,
             limit: int = 8 << 20) -> bytes:
    """Una richiesta JSON-lines e la risposta (fino a un limite di sicurezza).

    Fine messaggio riconosciuta **parsando**, non cercando un a capo: le app
    lasciano un `\\n` isolato dopo la risposta precedente, e fermarsi li' faceva
    leggere un byte vuoto al posto del catalogo dei comandi (misurato: e' la
    ragione per cui l'identita' risultava "sconosciuta" a intermittenza).

    Non solleva mai: se il peer chiude la connessione (succede quando rifiuta una
    credenziale) si torna quello che si e' letto. Uno shim che muore all'avvio per
    un errore di rete non e' un verdetto, e' un server MCP perso.
    """
    deadline = time.time() + timeout
    buffer = b""
    try:
        sock.sendall(json.dumps({"id": ident, "method": method, "params": params}).encode() + b"\n")
    except OSError:
        return buffer
    while time.time() < deadline:
        try:
            sock.settimeout(max(0.1, min(0.5, deadline - time.time())))
            chunk = sock.recv(1 << 16)
        except (socket.timeout, OSError):
            break
        if not chunk:
            break
        buffer += chunk
        if len(buffer) > limit:
            break
        try:
            json.loads(buffer.decode("utf-8", "replace"))
        except json.JSONDecodeError:
            continue  # risposta incompleta: continua a leggere
        break
    return buffer


def _command_ids(raw: bytes) -> set[str] | None:
    """Gli id di comando di un catalogo, nelle due forme che si incontrano.

    Dal canale arriva `{"id":2,"ok":true,"result":[...]}`, dal CLI `commands
    --json` un array nudo: leggere solo la prima forma faceva risultare "nessun
    catalogo locale" e l'identita' non veniva mai confrontata (misurato).
    """
    try:
        reply = json.loads(raw.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        return None
    if isinstance(reply, dict) and isinstance(reply.get("result"), list):
        reply = reply["result"]
    if not isinstance(reply, list):
        return None
    ids = {str(c.get("id") or c.get("name")) for c in reply if isinstance(c, dict)}
    ids.discard("None")
    return ids or None


ID_IN_TEXT = re.compile(r"^[A-Za-z][A-Za-z0-9_]*\.[A-Za-z0-9_.]+")


def _ids_from_text(text: str) -> set[str]:
    """Id di comando da un catalogo stampato come tabella (SoundCraft non fa JSON)."""
    ids = set()
    for line in text.splitlines():
        head = line.strip().split(None, 1)[0] if line.strip() else ""
        if ID_IN_TEXT.match(head):
            ids.add(head)
    return ids


def local_catalog(cli: str) -> set[str] | None:
    """Il catalogo che il CLI installato dichiara: e' la carta d'identita' dell'app."""
    for args in (["commands", "--json"], ["commands"]):
        try:
            proc = subprocess.run([cli, *args], capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=60)
        except (OSError, subprocess.SubprocessError):
            return None
        text = (proc.stdout or "").strip()
        if not text:
            continue
        ids = _command_ids(text.encode()) or _ids_from_text(text)
        if ids and (args[-1] == "--json" or len(ids) >= 20):
            return ids
    return None


def channel_catalog(port: int, token: str | None, host: str, timeout: float) -> set[str] | None:
    """Gli id di comando che l'app dietro la porta dichiara di avere.

    Il catalogo e' un corpo grosso (fino a ~120 KB misurati): il timeout qui e' piu'
    largo di quello dell'handshake, altrimenti sotto carico la risposta non arriva in
    tempo e un'app giusta verrebbe presa per estranea. Nel caso normale e' immediata.
    """
    bulk = max(timeout, 10.0)
    try:
        sock = socket.create_connection((host, port), timeout=PROBE_TIMEOUT)
    except OSError:
        return None
    try:
        if token:
            _request(sock, "auth", {"token": token}, timeout)
        for method in ("app.commands", "engine.commands"):
            ids = _command_ids(_request(sock, method, {}, bulk, ident=2))
            if ids:
                return ids
    finally:
        sock.close()
    return None


def _ask_protocol(port: int, host: str, timeout: float) -> str:
    try:
        sock = socket.create_connection((host, port), timeout=PROBE_TIMEOUT)
    except OSError:
        return "closed"
    try:
        buffer = _request(sock, IDENT_METHOD, {}, timeout, limit=65536)
    finally:
        sock.close()
    if not buffer.strip():
        return "silent"
    try:
        reply = json.loads(buffer.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        return "foreign"
    signed = (isinstance(reply, dict) and reply.get("id") == 1
              and any(k in reply for k in ("ok", "error", "result")))
    return "craft" if signed else "foreign"


def log(message: str) -> None:
    sys.stderr.write(f"craft-bridge-mcp: {message}\n")
    sys.stderr.flush()


def check_peer_build(slug: str, port: int) -> dict:
    """Dice se sulla porta gira **un'altra build** della stessa app, e lo annota.

    Il catalogo dice quale app, non quale versione: due build della stessa app lo
    coprono uguale (copertura 1.00), quindi il peer sembra a posto anche quando
    l'eseguibile in ascolto non e' quello che la config avvierebbe. Il confronto lo
    fa `craft-bridge-ident.py --build-only` (PID della porta, versione di
    quell'eseguibile, versione dichiarata dall'app nel proprio log, impronta
    registrata): costa ~1 s e si paga una volta sola, all'avvio.

    Una build diversa **non** fa andare headless: il canale parla lo stesso
    protocollo, quindi si procede bridged con un avviso esplicito. Il silenzio
    sarebbe peggio: e' esattamente il caso in cui la finestra guidata non e' quella
    che si crede di guidare.
    """
    cmd = [sys.executable, str(BUILD_TOOL), "--port", str(port), "--slug", slug,
           "--build-only", "--json"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=90)
        verdict = json.loads(proc.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        log(f"{slug}: build non verificata ({type(exc).__name__}): procedo bridged")
        return {"build": "unknown"}
    if verdict.get("build") == "different":
        running = verdict.get("running") or {}
        configured = verdict.get("configured") or {}
        log(f"{slug}: attenzione, sulla porta {port} gira la build {running.get('version')} "
            f"({running.get('exe') or '?'}) mentre la config si aspetta {configured.get('version')} "
            f"({configured.get('source')}): stessa app, altra build. Procedo bridged, ma non e' "
            f"la build con cui la config e' stata verificata")
    return verdict


def pump(source, target, on_close=None) -> None:
    """Copia byte senza buffering: os.read consegna ogni frammento appena arriva.

    Un `source.read(N)` su pipe resta bloccato finche' non ha N byte o l'EOF:
    con i messaggi MCP corti significherebbe non inoltrare mai nulla.
    """
    src_fd = source.fileno()
    dst_fd = target.fileno()
    try:
        while True:
            data = os.read(src_fd, 65536)
            if not data:
                break
            os.write(dst_fd, data)
    except (OSError, ValueError):
        pass
    finally:
        try:
            target.close()
        except Exception:
            pass
        if on_close:
            on_close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", choices=sorted(APPS))
    parser.add_argument("--dump-apps", action="store_true",
                        help="stampa la tabella delle app in JSON ed esce (percorsi "
                             "risolti dal sistema, con la fonte e il dichiarato)")
    parser.add_argument("--port", type=int, help="porta del canale di controllo")
    parser.add_argument("--token-file", help="control-token file (PhotoCraft)")
    parser.add_argument("--host", default="127.0.0.1", help="host della sonda")
    parser.add_argument("--require-bridge", action="store_true")
    parser.add_argument("--flags", action="store_true",
                        help="confronta il flag di aggancio della tabella con quello che "
                             "l'help di ogni CLI dichiara, ed esce")
    parser.add_argument("--flag-timeout", type=float, default=20.0,
                        help="secondi per l'help di una CLI (default 20)")
    parser.add_argument("--json", action="store_true", help="uscita JSON")
    args = parser.parse_args()

    if args.dump_apps:
        print(json.dumps(app_table(), indent=2))
        return 0
    if args.flags:
        report = flag_report(timeout=args.flag_timeout)
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 1 if report["diverging"] else 0
        marks = {"ok": "ok  ", "diverge": "FIX ", "non leggibile": "n/d "}
        for row in report["rows"]:
            print(f"  {marks[row['state']]} {row['check']:<12} {row['detail']}")
        tail = f"{len(report['ok'])}/{report['total']} confermati dall'help della CLI"
        if report["diverging"]:
            tail += f", {len(report['diverging'])} divergenti ({', '.join(report['diverging'])})"
        if report["unreadable"]:
            tail += f", {len(report['unreadable'])} non leggibili"
        print(tail)
        return 1 if report["diverging"] else 0
    if not args.slug:
        parser.error("--slug e' obbligatorio (oppure usa --dump-apps)")

    spec = app_table()[args.slug]
    cli = Path(spec["cli"])
    port = args.port or spec["port"]

    if not cli.is_file():
        log(f"CLI assente: {cli}")
        return 127
    if spec.get("needs_token") and not args.token_file:
        log("PhotoCraft in bridge richiede --token-file (l'app lo scrive da sola se avviata "
            "con --control-token-file sullo stesso percorso)")
        return 2

    peer = craft_peer(port, args.host)
    # Il canale non dichiara nome ne' versione: si riconosce dai comandi che elenca.
    # La CLI da sola non se ne accorge — misurato: messa su un'altra app ripiega in
    # headless senza dirlo (25 tool, nessun errore). Qui si guarda prima di scegliere.
    wrong_app = ""
    if peer == "craft":
        own = local_catalog(str(cli))
        token = None
        if spec.get("needs_token") and args.token_file:
            try:
                token = Path(args.token_file).read_text(encoding="utf-8").strip()
            except OSError:
                token = None
        theirs = channel_catalog(port, token, args.host, HANDSHAKE_TIMEOUT * 2)
        if own and theirs and len(own & theirs) / len(own) < MATCH_COVERAGE:
            wrong_app = (f"copre {len(own & theirs)}/{len(own)} comandi di {args.slug}")
            log(f"{args.slug}: sulla porta {port} risponde un'altra app ({wrong_app}): "
                f"la CLI ripiegherebbe in headless senza dirlo. Vado headless")
    # Stessa app ma altra build: il catalogo non lo distingue, l'eseguibile si'. Qui
    # e' solo un avviso (il canale funziona lo stesso); i comandi che *verificano* la
    # config — craft-bridge-launch.py, craft-bridge-ident.py — ne fanno un guasto.
    if peer == "craft" and not wrong_app:
        check_peer_build(args.slug, port)
    mode = "bridged" if (peer == "craft" and not wrong_app) else "headless"
    if peer == "silent":
        log(f"{args.slug}: la porta {args.host}:{port} e' in ascolto ma non risponde al "
            f"protocollo di controllo: c'e' altro su quella porta. Vado headless invece di "
            f"dichiarare bridged e ripiegare in silenzio al primo tool")
    elif peer == "foreign":
        log(f"{args.slug}: la porta {args.host}:{port} risponde con byte che non sono il "
            f"canale di controllo: vado headless")
    if mode == "headless" and args.require_bridge:
        log(f"nessuna app risponde su {args.host}:{port} (peer={peer}): avviala con "
            f"`{args.slug} --control {port}`")
        return 3

    if mode == "bridged":
        command = [str(cli), "mcp", spec["flag"], spec["addr"].format(port=port)]
        if spec.get("needs_token"):
            command += ["--control-token-file", args.token_file]
    else:
        command = [str(cli), "mcp"]

    log(f"{args.slug}: modalita' {mode} (porta {port}, peer={peer}"
        + (f", app estranea: {wrong_app}" if wrong_app else "") + ")")

    child = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=None,  # eredita lo stderr del client: i log delle CLI restano visibili
    )
    for thread in (
        threading.Thread(target=pump, args=(sys.stdin.buffer, child.stdin), daemon=True),
        threading.Thread(target=pump, args=(child.stdout, sys.stdout.buffer), daemon=True),
    ):
        thread.start()

    exit_code = child.wait()
    return exit_code if exit_code >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
