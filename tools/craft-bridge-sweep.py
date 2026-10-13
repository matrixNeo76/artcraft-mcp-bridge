#!/usr/bin/env python3
"""Passa in rassegna più Crafting Apps e misura la stessa entry MCP nei due modi.

Per ogni app: interroga l'entry **con l'app chiusa** (headless), avvia l'app col
canale di controllo sulla porta che la config si aspetta, riinterroga la stessa
entry (bridged), scopre un tool che esiste solo con l'app aperta e lo chiama per
davvero, poi chiude l'app. Tutto finisce in un report JSON.

    python craft-bridge-sweep.py                       # tutte le app shim
    python craft-bridge-sweep.py --apps cadcraft,lightcraft
    python craft-bridge-sweep.py --skip-tool           # solo il confronto di modi
    python craft-bridge-sweep.py --out sweep.json

Esito: 0 se ogni app provata è passata a bridged, 1 altrimenti.
"""
from __future__ import annotations

import argparse
import json
import re
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBE = HERE / "craft-bridge-probe.py"
DEFAULT_OUT = HERE.parent / "reports" / "craft-bridge-sweep.json"
DEFAULT_CONFIG = Path.home() / ".agents" / "mcp.json"
LOGDIR = Path.home() / ".craft-bridge" / "sweep-logs"

# Un tool che dichiara di lavorare sulla finestra viva: è la prova che il bridge
# non è un fallback. Le descrizioni variano per app, quindi si cerca il senso.
LIVE_TOOL = re.compile(
    r"bridge mode|live app|desktop app only|app_only|running app|"
    r"screenshot of the .*window|drive the running app",
    re.IGNORECASE,
)


FOREGROUND_PS = """
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Front {{
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
}}
"@
$p = Get-Process -Name '{name}' -ErrorAction SilentlyContinue |
     Where-Object {{ $_.MainWindowHandle -ne 0 }} | Select-Object -First 1
if (-not $p) {{ exit 3 }}
[Front]::ShowWindow($p.MainWindowHandle, 9) | Out-Null
[Front]::SetForegroundWindow($p.MainWindowHandle) | Out-Null
"""


def to_foreground(process_name: str) -> bool:
    """Porta la finestra in primo piano.

    I tool di cattura fotografano la finestra viva: se resta dietro le altre non
    ridisegna e la chiamata va in timeout. Senza questo passo l'harness
    riporterebbe un falso negativo, che è esattamente quello che è successo al
    primo giro su GridCraft.
    """
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
             FOREGROUND_PS.format(name=process_name)],
            capture_output=True, text=True, timeout=30)
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def probe(command: str, argv: list[str], tool: str | None = None,
          tool_args: str = "{}", schemas: bool = False, timeout: float = 45) -> dict:
    cmd = [sys.executable, str(PROBE), "--cmd", command, "--timeout", str(timeout)]
    for a in argv:
        cmd.append(f"--args={a}")
    if schemas:
        cmd.append("--schemas")
    if tool:
        cmd += ["--tool", tool, "--tool-args", tool_args]
    cmd.append("--json")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              timeout=timeout + 60)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"la sonda non ha risposto entro {timeout + 60}s"}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": "uscita non JSON", "raw": proc.stdout[-400:]}


def mode_of(result: dict) -> str:
    text = (result.get("stderr") or "").lower()
    if "modalita' bridged" in text:
        return "bridged"
    if "modalita' headless" in text:
        return "headless"
    return "?"


def args_for(defs: list[dict], tool: str, artifacts: Path | None = None) -> str:
    """Argomenti minimi per un tool: i cattura-schermo vogliono dove scrivere.

    Chiamare `screenshot` con `{}` non prova che il tool funzioni, prova che
    accetta un path nullo. Se lo schema espone `path`/`out`, lo si riempie.
    """
    spec = next((t for t in defs if t.get("name") == tool), None)
    props = ((spec or {}).get("inputSchema") or {}).get("properties") or {}
    for key in ("path", "out", "output", "file"):
        if key in props:
            target = (artifacts or Path(tempfile.gettempdir())) / f"sweep-{tool}.png"
            return json.dumps({key: str(target).replace("\\", "/")})
    return "{}"


def live_call(command: str, argv: list[str], defs: list[dict], extra: list[str]) -> dict:
    """Prova i tool solo-app finché uno risponde.

    Prima quelli che compaiono **solo** con l'app aperta (differenza esatta fra le
    due liste di tool), poi quelli che si dichiarano bridged nella descrizione.
    """
    declared = [t["name"] for t in defs if LIVE_TOOL.search(t.get("description") or "")]
    candidates = extra + [n for n in declared if n not in extra]
    tried = []
    for name in candidates[:4]:
        tool_args = args_for(defs, name)
        result = probe(command, argv, tool=name, tool_args=tool_args)
        content = " ".join(result.get("tool_content") or [])
        tried.append({"tool": name, "args": tool_args,
                      "ok": bool(result.get("ok")) and not result.get("is_error"),
                      "content": content[:400], "error": result.get("error"),
                      "content_types": result.get("content_types"),
                      "result_keys": result.get("result_keys")})
        if tried[-1]["ok"]:
            return {"candidates": candidates, "tried": tried, "winner": name,
                    "content": content[:400]}
    return {"candidates": candidates, "tried": tried, "winner": None}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--apps", help="slug separati da virgola (default: tutte le entry shim)")
    parser.add_argument("--wait", type=int, default=45, help="secondi di attesa del canale")
    parser.add_argument("--skip-tool", action="store_true")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    servers = json.loads(Path(args.config).read_text(encoding="utf-8-sig"))["mcpServers"]
    table = json.loads(subprocess.run(
        [sys.executable, str(HERE / "craft-bridge-mcp.py"), "--dump-apps"],
        capture_output=True, text=True, encoding="utf-8").stdout)

    wanted = args.apps.split(",") if args.apps else sorted(table)
    LOGDIR.mkdir(parents=True, exist_ok=True)
    report = {"apps": {}, "attempted": 0, "bridged": 0}

    for slug in wanted:
        spec = table.get(slug)
        entry = servers.get(slug)
        if not spec or not entry:
            print(f"[--] {slug}: nessuna entry shim in config, salto")
            continue
        argv = entry.get("args") or []
        command = entry["command"]
        port = int(argv[argv.index("--port") + 1])
        app_exe = Path(spec["cli"].replace("-cli.exe", ".exe"))
        record: dict = {"app": str(app_exe), "port": port, "entry": [command] + argv}
        report["attempted"] += 1
        print(f"\n=== {slug} (porta {port}) ===", flush=True)

        before = probe(command, argv, schemas=True)
        headless_tools = [t["name"] for t in (before.get("tool_defs") or [])]
        record["headless"] = {"mode": mode_of(before), "tools": before.get("tool_count"),
                              "ok": bool(before.get("ok")), "tools_names": headless_tools}
        print(f"  app chiusa : modo={record['headless']['mode']} tool={record['headless']['tools']}")

        # Se la config passa un control-token file allo shim, l'app va avviata con lo
        # stesso file: altrimenti genera un token suo e il bridge autentica male.
        launch = [str(app_exe), "--control", str(port)]
        if "--token-file" in argv:
            launch += ["--control-token-file", argv[argv.index("--token-file") + 1]]
        record["launch"] = launch
        log = LOGDIR / f"{slug}.log"
        with log.open("w", encoding="utf-8", errors="replace") as fh:
            child = subprocess.Popen(launch, stdout=fh, stderr=subprocess.STDOUT)
        deadline = time.time() + args.wait
        while time.time() < deadline and not port_open(port):
            if child.poll() is not None:
                break
            time.sleep(0.7)
        record["channel"] = port_open(port)
        line = [l for l in log.read_text(encoding="utf-8", errors="replace").splitlines()
                if "control" in l.lower() and ("listening" in l.lower() or "channel" in l.lower())]
        record["channel_log"] = line[-1][:220] if line else ""
        print(f"  canale     : {'attivo' if record['channel'] else 'NON attivo'} {record['channel_log']}")

        if record["channel"]:
            after = probe(command, argv, schemas=True)
            record["bridged"] = {"mode": mode_of(after), "tools": after.get("tool_count"),
                                 "ok": bool(after.get("ok"))}
            defs = after.get("tool_defs") or []
            bridged_tools = [t["name"] for t in defs]
            record["bridged"]["tools_names"] = bridged_tools
            extra = [n for n in bridged_tools if n not in headless_tools]
            only_headless = [n for n in headless_tools if n not in bridged_tools]
            record["app_only_tools"] = extra
            record["headless_only_tools"] = only_headless
            print(f"  app aperta : modo={record['bridged']['mode']} tool={record['bridged']['tools']}"
                  f" | solo-app: {len(extra)} {extra[:6]}"
                  + (f" | solo-headless: {only_headless}" if only_headless else ""))
            if not args.skip_tool and record["bridged"]["mode"] == "bridged":
                record["foregrounded"] = to_foreground(app_exe.stem)
                time.sleep(1.5)
                record["live_call"] = live_call(command, argv, defs, extra)
                winner = record["live_call"]["winner"]
                print(f"  chiamata   : {'OK ' + winner if winner else 'nessuna riuscita'}"
                      f" {('-> ' + record['live_call']['content'][:90]) if winner else ''}")
            if record["bridged"]["mode"] == "bridged":
                report["bridged"] += 1

        child.terminate()
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
        time.sleep(1.5)
        report["apps"][slug] = record

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n{report['bridged']}/{report['attempted']} app passate a bridged · report: {args.out}")
    return 0 if report["bridged"] == report["attempted"] else 1


if __name__ == "__main__":
    sys.exit(main())
