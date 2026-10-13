#!/usr/bin/env python3
"""
artcraft-mcp-proxy - shim stdio che rende conforme all'MCP il server ArtCraft.

Problema
--------
`artcraft-mcp.exe` v1.1.0 risponde con chiavi in snake_case dove la specifica MCP
richiede camelCase, quindi i client rigorosi (Claude Code, e i client conformi in
generale) rifiutano il server:

    initialize  ->  protocol_version / server_info / capabilities.tools.list_changed
    tools/list  ->  tools[].input_schema
    tools/call  ->  result.is_error

Soluzione
---------
Questo processo si mette in mezzo: parla MCP standard verso il client e rilancia
tutto al binario reale, riscrivendo *solo* i campi di protocollo noti. Nessuna
conversione cieca: le chiavi dei payload dei tool e gli schemi JSON (type,
properties, required, ...) restano intatti.

Uso (come lo invoca un client MCP):
    python artcraft-mcp-proxy.py

Variabili d'ambiente:
    ARTCRAFT_MCP_BIN   percorso del binario reale (default: installazione standard)

Nota: comunica in UTF-8 su stdin/stdout in modalita' binaria, quindi nessuna
traduzione di newline e nessuna perdita di caratteri non ASCII.
"""

import json
import os
import subprocess
import sys
import threading

DEFAULT_BIN = r"C:\Users\auresystem\AppData\Local\Programs\artcraft-mcp\artcraft-mcp.exe"

# chiavi di protocollo da rinominare nel blocco `result`
RENAME_RESULT = {
    "protocol_version": "protocolVersion",
    "server_info": "serverInfo",
    "is_error": "isError",
}
# chiavi dentro `result.capabilities.<capability>`
RENAME_CAPABILITY = {
    "list_changed": "listChanged",
}
# chiavi di ciascun tool in `result.tools[]`
RENAME_TOOL = {
    "input_schema": "inputSchema",
    "output_schema": "outputSchema",
}


def log(message):
    sys.stderr.write("[artcraft-proxy] %s\n" % message)
    sys.stderr.flush()


def _rename(obj, table):
    """Rinomina in place, solo se la chiave vecchia esiste e la nuova no (idempotente)."""
    for old, new in table.items():
        if old in obj and new not in obj:
            obj[new] = obj.pop(old)


def make_conformant(obj):
    """Riscrive i soli campi di protocollo non conformi. Ritorna l'oggetto."""
    if not isinstance(obj, dict):
        return obj
    result = obj.get("result")
    if not isinstance(result, dict):
        return obj

    _rename(result, RENAME_RESULT)

    capabilities = result.get("capabilities")
    if isinstance(capabilities, dict):
        for value in capabilities.values():
            if isinstance(value, dict):
                _rename(value, RENAME_CAPABILITY)

    tools = result.get("tools")
    if isinstance(tools, list):
        for tool in tools:
            if isinstance(tool, dict):
                _rename(tool, RENAME_TOOL)

    return obj


def _readline_binary(stream):
    """Legge una riga da un buffer binario senza decodifica preventiva."""
    return stream.readline()


def pump_stdout(child):
    """Server -> client: riscrive i campi non conformi."""
    try:
        while True:
            raw = _readline_binary(child.stdout)
            if not raw:
                break
            if not raw.strip():
                continue
            try:
                obj = json.loads(raw.decode("utf-8"))
            except Exception:
                _emit(raw)  # non e' JSON: inoltro verbatim
                continue
            try:
                fixed = json.dumps(
                    make_conformant(obj),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8") + b"\n"
            except Exception as exc:  # pragma: no cover - difensivo
                log("riscrittura fallita (%s): inoltro originale" % exc)
                fixed = raw if raw.endswith(b"\n") else raw + b"\n"
            _emit(fixed)
    except Exception as exc:  # pragma: no cover - difensivo
        log("errore nel pump di stdout: %s" % exc)


def pump_stderr(child):
    """Server -> stderr del client: diagnostica trasparente."""
    try:
        while True:
            raw = _readline_binary(child.stderr)
            if not raw:
                break
            stream = getattr(sys.stderr, "buffer", None)
            if stream is not None:
                stream.write(raw)
                stream.flush()
            else:
                sys.stderr.write(raw.decode("utf-8", "replace"))
                sys.stderr.flush()
    except Exception:
        pass


def _emit(payload):
    """Scrive una riga sul client in modalita' binaria, senza traduzioni."""
    stream = getattr(sys.stdout, "buffer", None)
    if stream is None:
        sys.stdout.write(payload.decode("utf-8", "replace"))
        sys.stdout.flush()
    else:
        stream.write(payload)
        stream.flush()


def _stdin_lines():
    """Righe dal client, in binario, con terminatore normalizzato a \\n."""
    stream = getattr(sys.stdin, "buffer", None)
    if stream is None:
        for line in sys.stdin:
            yield line.encode("utf-8")
        return
    while True:
        raw = stream.readline()
        if not raw:
            return
        if not raw.strip():
            continue
        yield raw


def main():
    binary = os.environ.get("ARTCRAFT_MCP_BIN", DEFAULT_BIN)
    if not os.path.isfile(binary):
        log("binario del server non trovato: %s" % binary)
        return 127

    try:
        child = subprocess.Popen(
            [binary],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        log("avvio del server fallito: %s" % exc)
        return 126

    threading.Thread(target=pump_stdout, args=(child,), daemon=True).start()
    threading.Thread(target=pump_stderr, args=(child,), daemon=True).start()

    try:
        for raw in _stdin_lines():
            if not raw.endswith(b"\n"):
                raw += b"\n"
            child.stdin.write(raw)
            child.stdin.flush()
    except (BrokenPipeError, KeyboardInterrupt):
        pass
    finally:
        try:
            child.stdin.close()
        except Exception:
            pass

    try:
        return child.wait()
    except KeyboardInterrupt:  # pragma: no cover
        child.kill()
        return 130


if __name__ == "__main__":
    sys.exit(main())
