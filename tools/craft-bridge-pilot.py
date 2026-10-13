#!/usr/bin/env python3
"""Pilota un'app desktop Craft attraverso il server MCP in modalita' bridged.

Esegue una sequenza ordinata di chiamate MCP contro il server stdio di una
`*-cli.exe` collegata con --connect/--bridge all'app aperta, salva gli artefatti
immagine restituiti e scrive un report JSON. Serve a provare che l'agente guida
davvero la finestra in esecuzione (stato che cambia, pixel catturati) e non una
sessione headless.

Uso:
    python craft-bridge-pilot.py \
        --cmd "C:\\Program Files\\PhotoCraft\\photocraft-cli.exe" \
        --args=mcp --args=--bridge --args=127.0.0.1:7981 \
        --args=--control-token-file --args="C:/Users/me/.craft-bridge/photocraft.token" \
        --step '{"tool":"ui_inspect"}' \
        --step '{"tool":"ui_set","args":{"fields":{"brush":{"size":33}}}}' \
        --step '{"tool":"ui_inspect"}' \
        --step '{"tool":"ui_screenshot","args":{"max_side":512},"artifact":"shot.png"}' \
        --out report.json
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE.parent / "reports" / "craft-bridge-pilot-report.json"
TIMEOUT = 90


class McpClient:
    def __init__(self, cmd: list[str]):
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

    def rpc(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        msg = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            msg["params"] = params
        assert self.proc.stdin
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        deadline = time.time() + TIMEOUT
        assert self.proc.stdout
        while time.time() < deadline:
            line = self.proc.stdout.readline()
            if not line:
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
        raise TimeoutError(f"nessuna risposta a {method} entro {TIMEOUT}s")


def summarize(payload: dict) -> dict:
    """Riduce il risultato di un tool a un sommario senza riversare tutto."""
    out = {"is_error": bool(payload.get("isError"))}
    text, images = [], []
    for item in payload.get("content") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text" and item.get("text"):
            text.append(item["text"])
        if item.get("type") == "image":
            images.append(item)
    out["text"] = "\n".join(text)
    out["image_count"] = len(images)
    return out, images


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cmd", required=True)
    parser.add_argument("--args", action="append", default=[])
    parser.add_argument("--step", action="append", default=[], help="JSON {tool,args?,artifact?}")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--artifact-dir", default=".")
    args = parser.parse_args()

    steps = [json.loads(s) for s in args.step]
    cmd = [args.cmd] + args.args
    artifact_dir = Path(args.artifact_dir)

    report: dict = {"cmd": cmd, "steps": [], "ok": False}
    client = McpClient(cmd)
    try:
        init = client.rpc(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "craft-bridge-pilot", "version": "0.1.0"},
            },
        )
        report["server_info"] = (init.get("result") or {}).get("serverInfo")
        report["protocol_version"] = (init.get("result") or {}).get("protocolVersion")
        client.proc.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
        )
        client.proc.stdin.flush()

        all_ok = True
        for step in steps:
            name = step["tool"]
            entry = {"tool": name, "args": step.get("args") or {}}
            reply = client.rpc("tools/call", {"name": name, "arguments": entry["args"]})
            if "error" in reply:
                entry["rpc_error"] = reply["error"]
                all_ok = False
            else:
                summary, images = summarize(reply["result"])
                entry.update(summary)
                if summary.get("is_error"):
                    all_ok = False
                if step.get("artifact") and images:
                    raw = base64.b64decode(images[0].get("data", ""))
                    path = artifact_dir / step["artifact"]
                    path.write_bytes(raw)
                    entry["artifact"] = str(path)
                    entry["artifact_bytes"] = len(raw)
                    entry["artifact_sha256"] = hashlib.sha256(raw).hexdigest()[:16]
                    entry["artifact_mime"] = images[0].get("mimeType")
                    entry["artifact_magic"] = raw[:8].hex()
            report["steps"].append(entry)
            print(f"[{name}] is_error={entry.get('is_error')} "
                  f"text={ (entry.get('text') or '')[:120]!r} "
                  f"artifact={entry.get('artifact')}")
        report["ok"] = all_ok
    finally:
        try:
            client.proc.stdin.close()  # type: ignore[union-attr]
        except Exception:
            pass
        try:
            client.proc.wait(timeout=15)
        except Exception:
            client.proc.kill()
        try:
            err = (client.proc.stderr.read() or "").strip()  # type: ignore[union-attr]
        except Exception:
            err = ""
        if err:
            report["stderr"] = err[:2000]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nreport: {args.out}  ok={report['ok']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
