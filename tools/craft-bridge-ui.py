#!/usr/bin/env python3
"""Ponte traduttore: i metodi della finestra come tool MCP, un processo per chiamata.

Il problema
-----------
PdfCraft sa fare una cosa che le altre undici app non fanno, e non fa quella che
fanno loro. L'app avviata con `--control FILE` apre un canale di controllo su una
**porta casuale** e ne scrive i dettagli (`pid`, `port`, `token`) in un file JSON;
la CLI lo raggiunge **un metodo per volta**:

    pdfcraft-cli ui --control FILE <method> [key=value ...] [--out shot.png]

Ma il suo server MCP non ha un verbo per agganciarsi alla finestra:
`pdfcraft-cli mcp --connect ...` risponde `mcp: unknown option --connect`. Una
sessione MCP e' lunga e deve pubblicare il catalogo dei tool della finestra viva;
quello che PdfCraft offre e' una chiamata per volta. Lo shim delle altre app non ha
niente davanti a cui mettersi, perche' il pezzo da agganciare non esiste.

La soluzione
------------
Questo processo fa da traduttore: parla **MCP su stdio** verso il client e, per ogni
`tools/call`, esegue **un processo CLI** con quel solo metodo. Il costo e' dichiarato
(un processo per chiamata, ~0,2-0,5 s) e il guadagno e' che l'agente vede la finestra
vera: stato UI, albero dei widget, comandi del menu, screenshot.

    client MCP  --stdio-->  craft-bridge-ui.py  --processo-->  pdfcraft-cli ui --control FILE <method>

Il modo si sceglie **una volta sola, all'avvio**, come per lo shim:
  * la finestra risponde (`ui state` autenticato) -> si espongono i **15 metodi**
    della finestra (`ui_*`), ognuno una invocazione della CLI;
  * la finestra non risponde -> l'entry resta valida: si delega al server MCP
    **headless** del fornitore (`pdfcraft-cli mcp`), che e' un'altra cosa e lo dice.
Il modo e' scritto su stderr a ogni avvio (`modalita' bridged` / `modalita'
headless`), cosi' un client non deve indovinare da che parte sta parlando.

Cosa e' misurato e cosa e' dedotto
----------------------------------
I 15 metodi e i loro parametri **non sono inventati**: l'app elenca il proprio
catalogo quando riceve un metodo che non conosce

    pdfcraft-cli: unknown method "ui.doc_list" (ui.state, ui.inspect, ui.click,
    ui.focus, ui.resize, ui.quit, ui.move, ui.drag, ui.type, ui.key, ui.command,
    ui.commands, ui.set, ui.open, ui.screenshot)

e i parametri obbligatori li dice il messaggio d'errore di ognuno (`ui.resize: height
must be between 320 and 8192 logical points`, `ui.set: missing string parameter key`,
...). Lo schema dichiarato qui e' quindi una **copia della risposta dell'app**, e
`--list` la confronta con quella viva: una divergenza si vede invece di restare
nascosta.

Uso (come `command`/`args` di una entry MCP):
    python craft-bridge-ui.py --slug pdfcraft --control ~/.craft-bridge/pdfcraft-control.json

Diagnosi:
    python craft-bridge-ui.py --slug pdfcraft --list              # modo, canale, catalogo
    python craft-bridge-ui.py --slug pdfcraft --call state        # un metodo, esito verbatim
    python craft-bridge-ui.py --slug pdfcraft --call set key=theme value=dark

    --cli PATH                    CLI diversa da quella che il sistema registra
    --require-bridge              non ripiegare: esce 3 se la finestra non risponde
    --timeout SECONDI             tempo massimo per ogni invocazione della CLI

Esito: quello del server MCP; in `--list`/`--call` quello della CLI invocata (0 esito
positivo, 1 guasto, 2 errore d'uso), 3 se `--require-bridge` e la finestra non c'e'.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHIM = HERE / "craft-bridge-mcp.py"
IDENT = HERE / "craft-bridge-ident.py"

CONTROL_DIR = Path.home() / ".craft-bridge"
PROTOCOL = "2025-06-18"                 # quella che parla il server del fornitore
VERSION = "1.0"
SERVER_NAME = "pdfcraft-ui"
DEFAULT_TIMEOUT = 30.0
CONNECT_TIMEOUT = 0.6

HEADLESS_ARGS = ("mcp",)

# ---------------------------------------------------------------------------------
# I 15 metodi della finestra: nome, parametri, descrizione, se e' in sola lettura
# ---------------------------------------------------------------------------------
# `args` = i nomi dei parametri come li vuole l'app (verificati uno per uno: sono
# quelli nominati nei suoi messaggi d'errore). `required` e' quello che l'app pretende
# prima di fare qualsiasi cosa. Nessuno di questi campi e' dedotto: vengono dal
# catalogo che l'app dichiara e dalle sue validazioni.
METHODS: dict[str, dict] = {
    "state": {
        "summary": "Stato della finestra: tema, pannelli, documenti aperti, dialoghi.",
        "args": {}, "required": [], "read_only": True,
    },
    "inspect": {
        "summary": "Albero dei widget: id, ruolo, etichetta, cliccabile. Con `query` "
                   "filtra per etichetta (serve a trovare l'id da cliccare).",
        "args": {"query": "string|null", "limit": "integer|null"},
        "required": [], "read_only": True,
    },
    "commands": {
        "summary": "Catalogo dei comandi della finestra (id, etichetta, menu, scorciatoia): "
                   "sono gli id che accetta `ui_command`.",
        "args": {}, "required": [], "read_only": True,
    },
    "screenshot": {
        "summary": "Fotografia della finestra come immagine PNG.",
        "args": {}, "required": [], "read_only": True, "image": True,
    },
    "click": {
        "summary": "Clic su un widget (per id o etichetta) oppure su un punto della finestra.",
        "args": {"id": "string|null", "label": "string|null",
                 "x": "number|null", "y": "number|null"},
        "required": [], "read_only": False,
    },
    "focus": {
        "summary": "Porta il fuoco su **un** widget, per id o etichetta.",
        "args": {"id": "string|null", "label": "string|null"},
        "required": [], "read_only": False,
    },
    "resize": {
        "summary": "Ridimensiona la finestra (punti logici, 320..8192).",
        "args": {"width": "number", "height": "number"},
        "required": ["width", "height"], "read_only": False,
    },
    "move": {
        "summary": "Sposta la finestra alle coordinate indicate (punti).",
        "args": {"x": "number", "y": "number"},
        "required": ["x", "y"], "read_only": False,
    },
    "drag": {
        "summary": "Trascina da un punto a un altro (`[x, y]` in punti).",
        "args": {"from": "array", "to": "array"},
        "required": ["from", "to"], "read_only": False,
    },
    "type": {
        "summary": "Scrive del testo nella finestra (widget che ha il fuoco).",
        "args": {"text": "string"}, "required": ["text"], "read_only": False,
    },
    "key": {
        "summary": "Premi un tasto (nomi egui: Enter, Escape, ArrowDown, F5, ...).",
        "args": {"key": "string"}, "required": ["key"], "read_only": False,
    },
    "command": {
        "summary": "Esegue un comando della finestra per id (vedi `ui_commands`).",
        "args": {"id": "string"}, "required": ["id"], "read_only": False,
    },
    "set": {
        "summary": "Cambia un'impostazione della finestra (`key` = nome, `value` = valore).",
        "args": {"key": "string", "value": "any"},
        "required": ["key", "value"], "read_only": False,
    },
    "open": {
        "summary": "Apre un documento nella finestra.",
        "args": {"path": "string"}, "required": ["path"], "read_only": False,
    },
    "quit": {
        "summary": "Chiude la finestra e l'app.",
        "args": {}, "required": [], "read_only": False,
    },
}

JSON_TYPES = {"string": "string", "number": "number", "integer": "integer",
              "boolean": "boolean", "array": "array", "object": "object"}


def log(message: str) -> None:
    """La diagnostica va su stderr: su stdout passano solo i frame JSON-RPC."""
    sys.stderr.write(f"[craft-bridge-ui] {message}\n")
    sys.stderr.flush()


def load(name: str, path: Path):
    """Carica uno strumento vicino come modulo: una sola implementazione per domanda."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"strumento non caricabile: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolve_cli(slug: str, override: str | None) -> tuple[str, str]:
    """La CLI dell'app, dal **sistema** (registro `App Paths`), come fa lo shim.

    Nessun percorso scritto a mano: se l'app si sposta, la voce `App Paths` la segue.
    `--cli` serve a puntare un binario diverso (una build di prova, un finto server
    per i test), e la fonte viene dichiarata in ogni caso.
    """
    if override:
        return override, "opzione --cli"
    shim = load("craft_bridge_mcp_ui", SHIM)
    exe, hive = shim.registered_exe(slug)
    if exe:
        cli = shim.cli_beside(exe)
        if cli.is_file():
            return str(cli), f"registro App Paths ({hive})"
    declared = str(Path(r"C:\Program Files") / slug.capitalize() / f"{slug}-cli.exe")
    return declared, "ripiego (il sistema non registra l'app)"


# ---------------------------------------------------------------------------------
# Il canale di controllo e la CLI
# ---------------------------------------------------------------------------------

def read_control(path: Path) -> dict:
    """Il file di controllo: `{pid, port, token}`. Errore esplicito se non c'e'."""
    if not path.is_file():
        raise SystemExit(
            f"file di controllo assente: {path}\n"
            f"  l'app non e' aperta in modo guidabile. Avviala con:\n"
            f"  pdfcraft.exe --control \"{path}\"")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"file di controllo illeggibile ({path}): {exc}")
    missing = [k for k in ("pid", "port", "token") if k not in data]
    if missing:
        raise SystemExit(f"file di controllo senza {', '.join(missing)}: {path}")
    return data


def channel_open(port: int, host: str = "127.0.0.1", timeout: float = CONNECT_TIMEOUT) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def method_argv(cli: str, control: Path, method: str, params: dict,
                out: str | None = None) -> list[str]:
    """Il comando per **un** metodo. Funzione pura: si prova senza eseguire niente.

    I valori passano come `key=value`, e la CLI li interpreta come JSON quando puo'
    (`100` -> numero, `true` -> booleano, `[1,2]` -> lista). Per questo ogni valore
    viene serializzato con `json.dumps`: una stringa diventa `"true"` e torna a essere
    la stringa `true`, non il booleano — senza le virgolette la CLI la leggerebbe come
    booleano, e il parametro arriverebbe all'app sbagliato.
    """
    argv = [cli, "ui", "--control", str(control), method]
    for key, value in params.items():
        argv.append(f"{key}={json.dumps(value)}")
    if out:
        argv += ["--out", str(out)]
    return argv


def run_method(cli: str, control: Path, method: str, params: dict,
               timeout: float = DEFAULT_TIMEOUT,
               out: str | None = None) -> dict:
    """Un metodo, un processo: esito, uscita, errore. Non solleva mai per rete."""
    argv = method_argv(cli, control, method, params, out)
    started = time.time()
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "code": None, "argv": argv,
                "error": f"la CLI non ha risposto entro {timeout:g}s"}
    except OSError as exc:
        return {"ok": False, "code": None, "argv": argv,
                "error": f"la CLI non si e' potuta eseguire: {exc}"}
    result = {"ok": proc.returncode == 0, "code": proc.returncode, "argv": argv,
              "stdout": proc.stdout or "", "stderr": proc.stderr or "",
              "seconds": round(time.time() - started, 2)}
    if result["ok"]:
        text = (proc.stdout or "").strip()
        try:
            result["json"] = json.loads(text) if text else None
        except json.JSONDecodeError:
            result["json"] = None                     # non JSON: resta il testo
    else:
        result["error"] = (proc.stderr or proc.stdout or "").strip() or "nessun messaggio"
    return result


def app_methods(cli: str, control: Path, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """Il catalogo dei metodi come lo dichiara **l'app** (drift check).

    L'app elenca il proprio catalogo quando riceve un metodo che non conosce. E' una
    domanda legittima -- "cosa sai fare?" -- posta nel modo in cui l'app la sa
    ricevere: la risposta e' la sua, non una nostra copia. Se il messaggio cambia
    forma, il risultato dice `non leggibile` invece di inventare un elenco.
    """
    probe_method = "__craft_bridge_ui_catalog__"
    out = run_method(cli, control, probe_method, {}, timeout=timeout)
    text = out.get("error") or out.get("stdout") or ""
    if "(" not in text or ")" not in text:
        return {"readable": False, "why": "l'app non ha elencato i metodi",
                "message": text[:200], "methods": []}
    inside = text[text.rindex("(") + 1:text.rindex(")")]
    theirs = [m.strip().removeprefix("ui.") for m in inside.split(",") if m.strip()]
    return {"readable": True, "methods": theirs, "message": text[:200]}


def drift(cli: str, control: Path, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """La nostra tabella contro il catalogo dell'app: le differenze, se ci sono."""
    theirs = app_methods(cli, control, timeout)
    ours = list(METHODS)
    if not theirs["readable"]:
        return {"checked": False, "why": theirs["why"], "ours": len(ours)}
    only_theirs = sorted(set(theirs["methods"]) - set(ours))
    only_ours = sorted(set(ours) - set(theirs["methods"]))
    return {"checked": True, "ours": len(ours), "theirs": len(theirs["methods"]),
            "only_theirs": only_theirs, "only_ours": only_ours,
            "same": not only_theirs and not only_ours}


def decide_mode(cli: str, control: Path, timeout: float) -> dict:
    """Bridged o headless: si decide una volta sola, e si dichiara il perche'.

    Una porta in ascolto non e' una prova: puo' essere occupata da altro, o il file
    di controllo puo' essere stantio (l'app e' stata chiusa). La prova e' una
    chiamata vera (`ui state`), che autentica col token del file e risponde.
    """
    if not control.is_file():
        return {"mode": "headless", "why": "file di controllo assente"}
    try:
        data = read_control(control)
    except SystemExit as exc:
        return {"mode": "headless", "why": str(exc).splitlines()[0]}
    if not channel_open(int(data["port"])):
        return {"mode": "headless",
                "why": f"nessuno in ascolto sulla porta {data['port']} (file stantio?)",
                "control": data}
    result = run_method(cli, control, "state", {}, timeout=timeout)
    if not result["ok"]:
        return {"mode": "headless", "why": f"ui state: {result.get('error', '')[:120]}",
                "control": data}
    return {"mode": "bridged", "why": "la finestra risponde e autentica", "control": data,
            "state": result.get("json")}


# ---------------------------------------------------------------------------------
# Lo schema dei tool, dai parametri che l'app stessa nomina
# ---------------------------------------------------------------------------------

def json_schema(args: dict) -> dict:
    properties = {}
    for name, kind in args.items():
        nullable = kind.endswith("|null")
        base = kind[:-5] if nullable else kind
        if base == "any":
            properties[name] = {"description": "valore qualsiasi (JSON)"}
            continue
        entry: dict = {"type": JSON_TYPES.get(base, "string")}
        if base == "array":
            entry |= {"items": {"type": "number"}, "minItems": 2, "maxItems": 2}
        if nullable:
            entry["type"] = [entry["type"], "null"]
        properties[name] = entry
    return {"type": "object", "properties": properties, "required": []}


def tool_definitions() -> list[dict]:
    tools = []
    for method, spec in METHODS.items():
        tools.append({
            "name": f"ui_{method}",
            "title": f"Finestra: {method}",
            "description": spec["summary"] + (
                f" (parametri obbligatori: {', '.join(spec['required'])})"
                if spec["required"] else ""),
            "inputSchema": json_schema(spec["args"]),
            "annotations": {"title": f"ui.{method}",
                            "readOnlyHint": bool(spec["read_only"]),
                            "destructiveHint": method == "quit",
                            "idempotentHint": False,
                            "openWorldHint": False},
        })
    return tools


# ---------------------------------------------------------------------------------
# Il server MCP: stdio, JSON-RPC 2.0, una chiamata = una invocazione della CLI
# ---------------------------------------------------------------------------------

class Translator:
    """Traduce `tools/call` in una invocazione della CLI. Uno stato minimo, dichiarato."""

    def __init__(self, slug: str, cli: str, cli_source: str, control: Path,
                 timeout: float):
        self.slug = slug
        self.cli = cli
        self.cli_source = cli_source
        self.control = control
        self.timeout = timeout
        self.calls = 0

    def tool_result(self, method: str, params: dict) -> dict:
        result = run_method(self.cli, self.control, method, params, timeout=self.timeout)
        self.calls += 1
        name = f"ui.{method}"
        if not result["ok"]:
            return {"content": [{"type": "text", "text": self.explain(method, result)}],
                    "isError": True}
        payload = result.get("json")
        if METHODS[method].get("image"):
            return self.image_result(method, result, payload)
        text = json.dumps(payload, ensure_ascii=False, indent=2) if payload is not None \
            else (result.get("stdout") or "").strip()
        return {"content": [{"type": "text", "text": text}], "isError": False}

    def image_result(self, method: str, result: dict, payload: dict | None) -> dict:
        """`ui.screenshot` risponde con il PNG in base64: diventa un contenuto immagine."""
        if not isinstance(payload, dict) or not payload.get("png_base64"):
            text = json.dumps(payload, ensure_ascii=False) if payload is not None \
                else (result.get("stdout") or "").strip()
            return {"content": [{"type": "text", "text": text}], "isError": False}
        meta = {k: payload.get(k) for k in ("width", "height", "pixels_per_point")
                if payload.get(k) is not None}
        return {"content": [
            {"type": "image", "data": payload["png_base64"], "mimeType": "image/png"},
            {"type": "text", "text": "finestra " + json.dumps(meta, ensure_ascii=False)},
        ], "isError": False}

    def explain(self, method: str, result: dict) -> str:
        """Il guasto detto come si deve: messaggio della CLI piu' la diagnosi del ponte.

        Il messaggio della CLI e' preciso ("ui.resize: height must be between...") e
        resta in testa; sotto si aggiunge l'unica cosa che la CLI non puo' sapere --
        che questa entry parla con una **finestra**, e che se la finestra non c'e' il
        modo di questa sessione e' headless (o l'app e' stata chiusa a meta').
        """
        lines = [str(result.get("error") or "guasto senza messaggio").strip(),
                 f"(metodo `ui.{method}`, CLI da {self.cli_source}, "
                 f"uscita {result.get('code')})"]
        if channel_open(self._port()):
            lines.append("la porta del file di controllo risponde ma il metodo no: "
                         "guarda il messaggio sopra")
        else:
            lines.append("la finestra non risponde piu' sulla porta del file di "
                         "controllo: l'app e' stata chiusa, o e' stata riavviata e il "
                         "file e' stantio. Riapri l'app con `--control "
                         f"{self.control}` e rifai la sessione.")
        return "\n".join(lines)

    def _port(self) -> int:
        try:
            return int(read_control(self.control)["port"])
        except (SystemExit, KeyError, ValueError, TypeError):
            return 0


def handle(t: Translator, request: dict) -> dict | None:
    """Una richiesta -> una risposta (o None per le notifiche, che non ne vogliono)."""
    method = request.get("method")
    rid = request.get("id")
    if rid is None and method != "initialize":            # notifica
        return None
    if method == "initialize":
        client_protocol = str((request.get("params") or {}).get("protocolVersion") or "")
        return reply(rid, {
            "protocolVersion": client_protocol or PROTOCOL,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "title": "PdfCraft (finestra)", "version": VERSION},
            "instructions": ("Drive the running PdfCraft window. Each call runs "
                             "`pdfcraft-cli ui --control FILE <method>` once. Use "
                             "ui_inspect to find widget ids and ui_commands for command ids."),
        })
    if method == "ping":
        return reply(rid, {})
    if method == "tools/list":
        return reply(rid, {"tools": tool_definitions()})
    if method == "tools/call":
        params = request.get("params") or {}
        name = str(params.get("name") or "")
        args = params.get("arguments") or {}
        if not name.startswith("ui_"):
            return error(rid, -32602, f"tool sconosciuto: {name}")
        ui_method = name[3:]
        if ui_method not in METHODS:
            return error(rid, -32602, f"tool sconosciuto: {name}")
        if not isinstance(args, dict):
            return error(rid, -32602, "arguments deve essere un oggetto")
        return reply(rid, t.tool_result(ui_method, args))
    if method in ("notifications/initialized", "notifications/cancelled",
                  "notifications/progress"):
        return None
    return error(rid, -32601, f"metodo non implementato: {method}")


def reply(rid, result) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def error(rid, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def emit(obj: dict) -> None:
    raw = (json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    stream = getattr(sys.stdout, "buffer", None)
    if stream is None:
        sys.stdout.write(raw.decode("utf-8"))
        sys.stdout.flush()
    else:
        stream.write(raw)
        stream.flush()


def serve(t: Translator) -> int:
    """Il ciclo stdio. Su stdout solo frame JSON-RPC; tutto il resto su stderr."""
    log(f"modalita' bridged: i {len(METHODS)} metodi della finestra, "
        f"un processo CLI per chiamata (CLI da {t.cli_source})")
    if not channel_open(t._port()):
        log("attenzione: la finestra non risponde piu' sulla porta del file di controllo")
    stream = getattr(sys.stdin, "buffer", None)
    while True:
        raw = stream.readline() if stream is not None else sys.stdin.readline().encode()
        if not raw:
            return 0
        if not raw.strip():
            continue
        try:
            request = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            emit(error(None, -32700, f"JSON non valido: {exc}"))
            continue
        try:
            response = handle(t, request)
        except Exception as exc:                       # pragma: no cover - difensivo
            response = error(request.get("id"), -32603, f"guasto interno: {exc}")
        if response is not None:
            emit(response)


def relay(cli: str, headless_args: list[str] | None = None) -> int:
    """Senza finestra si delega al server MCP **headless** del fornitore, verbatim.

    Non e' una modalita' mista: la scelta e' gia' stata fatta una volta sola e qui non
    si torna indietro. I byte passano nei due sensi senza riscritture, perche' il
    server del fornitore e' gia' conforme -- il proxy di conformita' serve all'MCP
    generativo (`artcraft-mcp-proxy.py`), non a questo. L'uscita e' la sua.
    """
    argv = [cli, *(headless_args or HEADLESS_ARGS)]
    try:
        child = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
    except OSError as exc:
        log(f"server headless non avviabile: {exc}")
        return 126

    def pump_out() -> None:
        assert child.stdout is not None
        while True:
            raw = child.stdout.readline()
            if not raw:
                break
            stream = getattr(sys.stdout, "buffer", None)
            if stream is None:
                sys.stdout.write(raw.decode("utf-8", "replace"))
                sys.stdout.flush()
            else:
                stream.write(raw)
                stream.flush()

    def pump_err() -> None:
        assert child.stderr is not None
        while True:
            raw = child.stderr.readline()
            if not raw:
                break
            sys.stderr.write("[cli] " + raw.decode("utf-8", "replace"))
            sys.stderr.flush()

    threading.Thread(target=pump_out, daemon=True).start()
    threading.Thread(target=pump_err, daemon=True).start()

    stdin = getattr(sys.stdin, "buffer", None)
    try:
        while True:
            raw = stdin.readline() if stdin is not None else sys.stdin.readline().encode()
            if not raw:
                break
            child.stdin.write(raw)
            child.stdin.flush()
    except (BrokenPipeError, KeyboardInterrupt):
        pass
    finally:
        try:
            child.stdin.close()
        except OSError:
            pass
    try:
        return child.wait(timeout=10)
    except subprocess.TimeoutExpired:                   # pragma: no cover - difensivo
        child.kill()
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Espone i metodi della finestra PdfCraft come tool MCP, "
                    "invocando la CLI un metodo per volta.")
    parser.add_argument("--slug", default="pdfcraft", help="app (default: pdfcraft)")
    parser.add_argument("--control", help="file di controllo scritto dall'app "
                                          f"(default: {CONTROL_DIR / 'pdfcraft-control.json'})")
    parser.add_argument("--cli", help="CLI da usare invece di quella registrata dal sistema")
    parser.add_argument("--headless-args", nargs="+", default=list(HEADLESS_ARGS),
                        help="come si chiede il server headless a quella CLI (default: mcp)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                        help="secondi per ogni invocazione della CLI")
    parser.add_argument("--require-bridge", action="store_true",
                        help="esce 3 se la finestra non risponde, invece di ripiegare")
    parser.add_argument("--list", action="store_true", help="modo, canale e catalogo, poi esce")
    parser.add_argument("--where", action="store_true",
                        help="dove sta la CLI e il file di controllo, poi esce (senza sonda)")
    parser.add_argument("--call", help="esegue un solo metodo e stampa l'esito verbatim")
    parser.add_argument("--out", help="file immagine per `--call screenshot`")
    parser.add_argument("--json", action="store_true", help="uscita JSON per --list")
    args, extra = parser.parse_known_args()

    control = Path(args.control).expanduser() if args.control else \
        CONTROL_DIR / f"{args.slug}-control.json"
    cli, cli_source = resolve_cli(args.slug, args.cli)

    if not Path(cli).is_file() and not args.call:
        print(f"CLI assente: {cli} (da {cli_source})", file=sys.stderr)
        return 2

    if args.where:
        # Nessuna sonda: serve a chi deve **scrivere** una entry (l'installer) o a chi
        # vuole sapere dove guarda questo ponte, senza toccare l'app.
        where = {"slug": args.slug, "cli": cli, "cli_source": cli_source,
                 "cli_exists": Path(cli).is_file(), "control": str(control),
                 "control_exists": control.is_file(), "methods": sorted(METHODS)}
        if args.json:
            print(json.dumps(where, ensure_ascii=False, indent=2))
        else:
            print(f"cli        : {cli} (da {cli_source})")
            print(f"file       : {control} ({'presente' if control.is_file() else 'assente'})")
            print(f"metodi     : {', '.join(sorted(METHODS))}")
        return 0

    if args.list:
        mode = decide_mode(cli, control, args.timeout)
        report = {
            "slug": args.slug, "cli": cli, "cli_source": cli_source,
            "control": str(control), "control_exists": control.is_file(),
            "mode": mode["mode"], "mode_why": mode["why"],
            "methods": sorted(METHODS),
        }
        if mode.get("control"):
            report["port"] = mode["control"].get("port")
            report["pid"] = mode["control"].get("pid")
            report["window"] = (mode.get("state") or {}).get("window")
        if mode["mode"] == "bridged":
            report["drift"] = drift(cli, control, args.timeout)
            try:
                report["app_version"] = load("craft_bridge_ident_ui", IDENT).binary_version(cli)
            except SystemExit:
                pass
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
        print(f"app        : {args.slug} (CLI da {cli_source})")
        print(f"file       : {control} ({'presente' if control.is_file() else 'ASSENTE'})")
        if report.get("port"):
            print(f"canale     : porta {report['port']}, pid {report['pid']}")
        if report.get("window"):
            w = report["window"]
            print(f"finestra   : {w.get('width')}x{w.get('height')} punti")
        print(f"modo       : {mode['mode']} ({mode['why']})")
        if report.get("app_version"):
            print(f"versione   : {report['app_version']}")
        if report.get("drift"):
            d = report["drift"]
            if d.get("checked"):
                state = "coincide" if d["same"] else "DIVERGE"
                print(f"catalogo   : {d['ours']} metodi nostri, {d['theirs']} dall'app: {state}")
                if d.get("only_theirs"):
                    print(f"             solo dall'app  : {', '.join(d['only_theirs'])}")
                if d.get("only_ours"):
                    print(f"             solo da noi    : {', '.join(d['only_ours'])}")
            else:
                print(f"catalogo   : non confrontabile ({d['why']})")
        print(f"metodi     : {', '.join(sorted(METHODS))}")
        return 0 if mode["mode"] == "bridged" or not args.require_bridge else 3

    if args.call:
        if args.call not in METHODS:
            print(f"metodo sconosciuto: {args.call} (noti: {', '.join(sorted(METHODS))})",
                  file=sys.stderr)
            return 2
        params = {}
        for item in extra:
            if "=" not in item:
                print(f"parametri nella forma key=value, ricevuto: {item}", file=sys.stderr)
                return 2
            key, value = item.split("=", 1)
            try:
                params[key] = json.loads(value)
            except json.JSONDecodeError:
                params[key] = value
        result = run_method(cli, control, args.call, params, timeout=args.timeout,
                            out=args.out)
        if result.get("stdout"):
            sys.stdout.write(result["stdout"] if result["stdout"].endswith("\n")
                             else result["stdout"] + "\n")
        if result.get("stderr"):
            sys.stderr.write(result["stderr"] if result["stderr"].endswith("\n")
                             else result["stderr"] + "\n")
        if not result["ok"]:
            return 1
        return 0

    # Il modo si sceglie una volta sola: la finestra risponde, o si delega all'headless.
    mode = decide_mode(cli, control, args.timeout)
    if mode["mode"] == "headless":
        if args.require_bridge:
            log(f"nessuna finestra: {mode['why']}")
            return 3
        log(f"modalita' headless: {mode['why']} - delego a "
            f"`{Path(cli).name} {' '.join(args.headless_args)}`")
        return relay(cli, args.headless_args)

    translator = Translator(args.slug, cli, cli_source, control, args.timeout)
    return serve(translator)


if __name__ == "__main__":
    sys.exit(main())
