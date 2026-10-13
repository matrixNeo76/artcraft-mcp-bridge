#!/usr/bin/env python3
"""Verifica end-to-end delle entry MCP così come sono scritte in config.

Non simula nulla: legge `~/.agents/mcp.json` e per ogni entry esegue **esattamente**
il comando configurato (`command` + `args`), facendogli fare `initialize` e
`tools/list` (e opzionalmente una chiamata a un tool). Riporta la modalità scelta
dallo shim leggendo lo stderr, così si distingue un connettore bridged da uno
headless.

    python craft-bridge-verify.py                      # tutte le entry
    python craft-bridge-verify.py --expect headless    # app chiuse
    python craft-bridge-verify.py --only gridcraft,wordcraft --tool ui_inspect
    python craft-bridge-verify.py --only gridcraft --expect bridged --tool screenshot \
        --tool-args '{"path":"C:/Users/me/Desktop/gridcraft.png"}'

Esito: 0 se tutte le entry verificate rispondono (e le modalità attese tornano),
1 altrimenti. --expect bridged|headless|any.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBE = HERE / "craft-bridge-probe.py"
DEFAULT_CONFIG = Path.home() / ".agents" / "mcp.json"


def run_entry(command: str, argv: list[str], tool: str | None, tool_args: str) -> dict:
    cmd = [sys.executable, str(PROBE), "--cmd", command, "--tool-args", tool_args, "--json"]
    for a in argv:
        cmd.append(f"--args={a}")
    if tool:
        cmd += ["--tool", tool]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=180)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": "uscita non JSON", "raw": proc.stdout[-500:],
                "exit_code": proc.returncode}


def detect_mode(stderr: str) -> str:
    text = (stderr or "").lower()
    if "modalita' bridged" in text or "modalita` bridged" in text:
        return "bridged"
    if "modalita' headless" in text or "modalita` headless" in text:
        return "headless"
    if "connected to the" in text and " app at " in text:
        return "bridged"
    if "headless" in text:
        return "headless"
    return "?"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--only", help="lista di slug separati da virgola")
    parser.add_argument("--skip", default="", help="slug da saltare (separati da virgola)")
    parser.add_argument("--expect", choices=["bridged", "headless", "any"], default="any")
    parser.add_argument("--tool")
    parser.add_argument("--tool-args", default="{}")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    servers = json.loads(Path(args.config).read_text(encoding="utf-8-sig"))["mcpServers"]
    only = set(args.only.split(",")) if args.only else None
    skip = {s for s in args.skip.split(",") if s}

    rows, failures = [], 0
    for slug, entry in sorted(servers.items()):
        if only and slug not in only:
            continue
        if slug in skip:
            continue
        argv = entry.get("args") or []
        result = run_entry(entry["command"], argv, args.tool, args.tool_args)
        # La modalita' riguarda solo le entry che passano dallo shim: artcraft (proxy
        # di protocollo) e pdfcraft (meccanismo diverso) non ne hanno una.
        is_shim = any("craft-bridge-mcp.py" in a for a in argv)
        mode = detect_mode(result.get("stderr", "")) if is_shim else "n/a"
        ok = bool(result.get("ok")) and not result.get("is_error")
        if args.expect != "any" and is_shim and mode != args.expect:
            ok = False
        if not ok:
            failures += 1
        rows.append({
            "slug": slug,
            "ok": ok,
            "mode": mode,
            "tools": result.get("tool_count"),
            "tool": args.tool,
            "tool_error": result.get("tool_error") or (result.get("text") or "")[:120],
            "error": result.get("error"),
            "content": " ".join(result.get("tool_content") or [])[:160],
            "stderr_tail": (result.get("stderr") or "").strip().splitlines()[-1:] or [""],
        })
        print(f"[{'OK ' if ok else 'KO '}] {slug:12s} modo={mode:8s} tool={result.get('tool_count')} "
              f"{'' if ok else (rows[-1]['error'] or rows[-1]['tool_error'] or '')}")

    if args.json:
        print(json.dumps({"rows": rows, "failures": failures}, indent=2))

    shim_rows = [r for r in rows if r["mode"] != "n/a"]
    print(f"\n{len(rows) - failures}/{len(rows)} entry verificate "
          f"({len(shim_rows)} con shim, atteso: {args.expect}) -> "
          f"{'TUTTO OK' if failures == 0 else 'FALLIMENTI'}")
    if args.tool:
        for row in rows:
            if row["content"]:
                print(f"  {row['slug']}: {row['content']}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
