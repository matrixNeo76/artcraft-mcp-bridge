#!/usr/bin/env python3
"""
report-mcp-tools - inventario reale dei tool MCP configurati.

Legge la configurazione dei connettori (`~/.agents/mcp.json`, la stessa che
Freebuff Desktop mostra nel pannello "Connectors"), avvia ogni server stdio,
esegue l'handshake MCP e chiede `tools/list`. Scrive un report Markdown.

Uso:
    python report-mcp-tools.py [--config <path>] [--out <file.md>] [--timeout 60]

Non modifica nessuna configurazione: e' di sola lettura verso i server.
"""

import argparse
import datetime
import json
import os
import subprocess
import sys

DEFAULT_CONFIG = os.path.join(os.path.expanduser("~"), ".agents", "mcp.json")
DEFAULT_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           os.pardir, "reports", "mcp-tools-report.md")

INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "report-mcp-tools", "version": "1.0"},
    },
}
INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}
TOOLS_LIST = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}


def freebuff_entry_ok(entry):
    """Rispecchia lo schema stdioEntry/remoteEntry del McpConfigStore di Freebuff."""
    if not isinstance(entry, dict):
        return False, "entry non e' un oggetto"
    if "command" in entry:
        if entry.get("type") not in (None, "stdio"):
            return False, 'type deve essere "stdio"'
        if not isinstance(entry.get("command"), str) or not entry["command"]:
            return False, "command mancante"
        if "args" in entry and not (
            isinstance(entry["args"], list)
            and all(isinstance(a, str) for a in entry["args"])
        ):
            return False, "args deve essere un array di stringhe"
        if "env" in entry and not (
            isinstance(entry["env"], dict)
            and all(isinstance(v, str) for v in entry["env"].values())
        ):
            return False, "env deve essere una mappa stringa->stringa"
        return True, "stdio valido"
    if "url" in entry:
        if entry.get("type") not in (None, "http", "sse"):
            return False, "type remoto non valido"
        return True, "remoto valido"
    return False, "ne' command ne' url"


def probe(entry, timeout):
    """Avvia il server stdio e ritorna (status, protocollo, tool, errore)."""
    command = entry.get("command")
    args = list(entry.get("args") or [])
    env = dict(os.environ)
    env.update(entry.get("env") or {})

    payload = "\n".join(json.dumps(m) for m in (INIT, INITIALIZED, TOOLS_LIST)) + "\n"
    try:
        proc = subprocess.run(
            [command] + args,
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            cwd=entry.get("cwd") or None,
            timeout=timeout,
        )
    except FileNotFoundError:
        return "FAIL", None, [], "eseguibile non trovato: %s" % command
    except subprocess.TimeoutExpired:
        return "TIMEOUT", None, [], "nessuna risposta entro %ss" % timeout
    except OSError as exc:
        return "FAIL", None, [], "avvio fallito: %s" % exc

    protocol, tools, error = None, [], None
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        if msg.get("id") == 1 and isinstance(msg.get("result"), dict):
            res = msg["result"]
            protocol = res.get("protocolVersion") or res.get("protocol_version")
        if msg.get("error") and error is None:
            error = "server error: %s" % json.dumps(msg["error"])[:200]
        if msg.get("id") == 2 and isinstance(msg.get("result"), dict):
            for tool in msg["result"].get("tools", []):
                if isinstance(tool, dict) and tool.get("name"):
                    tools.append(tool["name"])

    if tools:
        return "OK", protocol, tools, None
    if error:
        return "FAIL", protocol, [], error
    err = (proc.stderr or "").strip().splitlines()
    detail = err[-1] if err else "nessun tool restituito (rc=%s)" % proc.returncode
    return "FAIL", protocol, [], detail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--timeout", type=int, default=60)
    opts = ap.parse_args()

    if not os.path.isfile(opts.config):
        print("configurazione non trovata: %s" % opts.config, file=sys.stderr)
        return 1

    try:
        with open(opts.config, encoding="utf-8") as handle:
            config = json.load(handle)
    except json.JSONDecodeError as exc:
        print("File is not valid JSON: %s (riga %d, colonna %d)"
              % (opts.config, exc.lineno, exc.colno), file=sys.stderr)
        return 1
    except OSError as exc:
        print("impossibile leggere %s: %s" % (opts.config, exc), file=sys.stderr)
        return 1

    if not isinstance(config, dict):
        print("configurazione non valida: atteso un oggetto JSON con 'mcpServers'", file=sys.stderr)
        return 1

    servers = config.get("mcpServers") or {}
    if not isinstance(servers, dict):
        print("'mcpServers' deve essere un oggetto", file=sys.stderr)
        return 1
    print("server configurati in %s: %d\n" % (opts.config, len(servers)))

    results = []
    for name in sorted(servers):
        entry = servers[name]
        valid, why = freebuff_entry_ok(entry)
        if not valid:
            results.append(
                {"name": name, "entry": entry, "valid": False, "why": why,
                 "status": "SCHEMA", "protocol": None, "tools": [], "error": why}
            )
            print("  [schema] %-14s %s" % (name, why))
            continue
        if "command" not in entry:
            results.append(
                {"name": name, "entry": entry, "valid": True, "why": why,
                 "status": "REMOTE", "protocol": None, "tools": [],
                 "error": "server remoto (%s): non avviabile come processo locale"
                          % entry.get("url")}
            )
            print("  [http] %-14s remoto, non testato" % name)
            continue

        status, protocol, tools, error = probe(entry, opts.timeout)
        results.append(
            {"name": name, "entry": entry, "valid": True, "why": why,
             "status": status, "protocol": protocol, "tools": tools, "error": error}
        )
        flag = "ok " if status == "OK" else "!! "
        print("  [%s] %-14s %3d tool%s" % (flag, name, len(tools),
                                           "" if not error else "  -- %s" % error[:70]))

    ok = [r for r in results if r["status"] == "OK"]
    total_tools = sum(len(r["tools"]) for r in results)

    lines = []
    lines.append("# Report dei tool MCP disponibili")
    lines.append("")
    lines.append("**Generato:** %s" % datetime.datetime.now().strftime("%d/%m/%Y %H:%M"))
    lines.append("**Configurazione:** `%s` (la stessa del pannello **Connectors** di Freebuff)" % opts.config)
    lines.append("**Server configurati:** %d · **connessi:** %d · **tool totali esposti:** %d"
                 % (len(results), len(ok), total_tools))
    lines.append("")
    lines.append("## Riepilogo")
    lines.append("")
    lines.append("| Server | Trasporto | Stato | Protocollo | Tool |")
    lines.append("|---|---|---|---|---|")
    for r in results:
        transport = "stdio" if "command" in r["entry"] else "http"
        state = {
            "OK": "connesso",
            "FAIL": "fallito",
            "TIMEOUT": "timeout",
            "SCHEMA": "schema non valido",
            "REMOTE": "remoto (non testato)",
        }[r["status"]]
        lines.append("| `%s` | %s | %s | %s | %d |"
                     % (r["name"], transport, state, r["protocol"] or "-", len(r["tools"])))
    lines.append("")

    problems = [r for r in results if r["status"] != "OK"]
    if problems:
        lines.append("## Problemi")
        lines.append("")
        for r in problems:
            lines.append("- **`%s`** (%s): %s" % (r["name"], r["status"], r["error"] or "n/d"))
        lines.append("")

    lines.append("## Tool per server")
    lines.append("")
    for r in results:
        lines.append("### `%s` (%d tool)" % (r["name"], len(r["tools"])))
        lines.append("")
        if "command" in r["entry"]:
            lines.append("`%s %s`" % (r["entry"]["command"], " ".join(r["entry"].get("args") or [])))
        else:
            lines.append("`%s`" % r["entry"].get("url"))
        lines.append("")
        if r["tools"]:
            for tool in r["tools"]:
                lines.append("- `%s`" % tool)
        else:
            lines.append("_nessun tool disponibile_")
        lines.append("")

    parent = os.path.dirname(os.path.abspath(opts.out))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(opts.out, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))

    print("\nreport scritto in %s" % os.path.abspath(opts.out))
    print("server connessi %d, non connessi %d, tool totali %d"
          % (len(ok), len(results) - len(ok), total_tools))
    return 0 if len(ok) == len(results) else 2


if __name__ == "__main__":
    sys.exit(main())
