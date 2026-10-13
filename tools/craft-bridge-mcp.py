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
                        help="stampa la tabella delle app in JSON ed esce")
    parser.add_argument("--port", type=int, help="porta del canale di controllo")
    parser.add_argument("--token-file", help="control-token file (PhotoCraft)")
    parser.add_argument("--host", default="127.0.0.1", help="host della sonda")
    parser.add_argument("--require-bridge", action="store_true")
    args = parser.parse_args()

    if args.dump_apps:
        import json
        print(json.dumps(APPS, indent=2))
        return 0
    if not args.slug:
        parser.error("--slug e' obbligatorio (oppure usa --dump-apps)")

    spec = APPS[args.slug]
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
