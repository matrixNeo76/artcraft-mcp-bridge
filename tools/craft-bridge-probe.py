#!/usr/bin/env python3
"""Sonda MCP per la modalita' bridged delle Crafting Apps.

Parla JSON-RPC 2.0 con framing line-delimited a un server MCP stdio qualsiasi
(qui: `*-cli.exe mcp --connect/--bridge ...`) e riporta in JSON cosa ha visto:
versione di protocollo negoziata, numero di tool, e il risultato di una chiamata.
Serve a distinguere un bridge davvero collegato all'app aperta da un fallback
silenzioso alla sessione headless.

Uso:
    # elenca i tool (bridge verso l'app aperta)
    python craft-bridge-probe.py --cmd "C:\\Program Files\\PhotoCraft\\photocraft-cli.exe" \
        --args mcp --args --bridge --args 127.0.0.1:7981 \
        --args --control-token-file --args "C:\\Users\\me\\.craft-bridge\\photocraft.token"

    # chiama un tool che esiste solo con l'app aperta
    python craft-bridge-probe.py ... --tool ui.screenshot --tool-args '{"width":200}'

Esito:
    0  la sessione MCP ha risposto (per un test negativo usare --expect-fail)
    1  il server non ha risposto o ha risposto con errore
    2  errore d'uso
"""
from __future__ import annotations

import argparse
import json
import queue
import subprocess
import sys
import threading
import time

TIMEOUT = 60


class McpClient:
    def __init__(self, cmd: list[str], timeout: float = TIMEOUT):
        self.timeout = timeout
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        self._id = 0
        # La lettura va su un thread: una `readline` bloccante non rispetta alcun
        # deadline, quindi un server che non risponde blocca il probe per sempre.
        self._lines: queue.Queue[str | None] = queue.Queue()
        threading.Thread(target=self._pump_lines, daemon=True).start()

    def _pump_lines(self) -> None:
        assert self.proc.stdout
        for line in self.proc.stdout:
            self._lines.put(line)
        self._lines.put(None)

    def send(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        msg = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            msg["params"] = params
        assert self.proc.stdin
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        deadline = time.time() + self.timeout
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutError(f"nessuna risposta a {method} entro {self.timeout}s")
            try:
                line = self._lines.get(timeout=remaining)
            except queue.Empty:
                raise TimeoutError(f"nessuna risposta a {method} entro {self.timeout}s") from None
            if line is None:
                raise RuntimeError("server MCP chiuso in anticipo")
            line = line.strip()
            if not line:
                continue
            try:
                reply = json.loads(line)
            except json.JSONDecodeError:
                continue
            if reply.get("id") == self._id:
                return reply

    def notify(self, method: str, params: dict | None = None) -> None:
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        assert self.proc.stdin
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()

    def close(self) -> tuple[int, str]:
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
            rc = self.proc.wait(timeout=15)
        except Exception:
            self.proc.kill()
            rc = -9
        err = ""
        try:
            if self.proc.stderr:
                err = self.proc.stderr.read() or ""
        except Exception:
            pass
        return rc, err.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cmd", required=True, help="eseguibile del server MCP")
    parser.add_argument("--args", action="append", default=[], help="un argomento (ripetibile)")
    parser.add_argument("--tool", help="nome del tool da chiamare")
    parser.add_argument("--tool-args", default="{}", help="parametri JSON del tool")
    parser.add_argument("--expect-fail", action="store_true", help="esito 0 se la sessione fallisce")
    parser.add_argument("--schemas", action="store_true", help="includi gli schema dei tool")
    parser.add_argument("--timeout", type=float, default=TIMEOUT, help="secondi per risposta")
    parser.add_argument("--json", action="store_true", help="solo JSON")
    args = parser.parse_args()

    cmd = [args.cmd] + args.args
    result: dict = {"cmd": cmd, "ok": False}
    try:
        client = McpClient(cmd, timeout=args.timeout)
    except Exception as exc:  # pragma: no cover - lancio impossibile
        result["error"] = f"avvio fallito: {exc}"
        print(json.dumps(result, indent=2) if args.json else result["error"])
        return 0 if args.expect_fail else 1

    try:
        init = client.send(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "craft-bridge-probe", "version": "0.1.0"},
            },
        )
        if "error" in init:
            result["error"] = f"initialize: {init['error']}"
        else:
            body = init["result"]
            result["protocol_version"] = body.get("protocolVersion")
            result["server_info"] = body.get("serverInfo")
            result["capabilities"] = body.get("capabilities")
            client.notify("notifications/initialized")

            listing = client.send("tools/list")
            if "error" in listing:
                result["error"] = f"tools/list: {listing['error']}"
            else:
                tools = listing["result"].get("tools", [])
                result["tool_count"] = len(tools)
                result["tools"] = [t.get("name") for t in tools]
                result["tools_live"] = [
                    t.get("name")
                    for t in tools
                    if "app" in json.dumps(t.get("description") or "").lower()
                    or "desktop" in json.dumps(t.get("description") or "").lower()
                ]
                if args.schemas:
                    result["tool_defs"] = tools
                result["ok"] = True

                if args.tool:
                    call = client.send(
                        "tools/call",
                        {"name": args.tool, "arguments": json.loads(args.tool_args)},
                    )
                    if "error" in call:
                        result["tool_error"] = call["error"]
                        result["ok"] = False
                    else:
                        payload = call["result"]
                        result["tool"] = args.tool
                        result["is_error"] = payload.get("isError", False)
                        content = payload.get("content") or []
                        result["content_types"] = [c.get("type") for c in content
                                                   if isinstance(c, dict)]
                        result["tool_content"] = [
                            (c.get("text") or "")[:600] for c in content if isinstance(c, dict)
                        ]
                        if not any(result["tool_content"]) and not result["content_types"]:
                            result["result_keys"] = sorted(payload)
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        rc, err = client.close()
        result["exit_code"] = rc
        if err:
            result["stderr"] = err[:2000]

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))

    if args.expect_fail:
        return 0 if not result.get("ok") else 1
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
