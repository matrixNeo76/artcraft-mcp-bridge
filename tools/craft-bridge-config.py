#!/usr/bin/env python3
"""Installa lo shim bridged e riscrive le entry MCP delle Crafting Apps.

Genera le entry di `~/.agents/mcp.json` che passano dal wrapper
`craft-bridge-mcp.py`, cosi' ogni app viene guidata nella sua finestra quando e'
aperta e resta usabile in headless quando non lo e'. Le entry `artcraft` e
qualsiasi altra entry non elencata qui restano intatte.

    python craft-bridge-config.py                  # mostra cosa cambierebbe
    python craft-bridge-config.py --apply          # scrive (con backup)
    python craft-bridge-config.py --apply --port photocraft=7981
    python craft-bridge-config.py --restore        # torna alle entry headless
    python craft-bridge-config.py --json           # solo le entry generate

La tabella delle app arriva dal wrapper stesso (`--dump-apps`): una sola fonte.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
WRAPPER = HERE / "craft-bridge-mcp.py"
# Lo shim delega a questo la domanda sulla build (PID della porta, eseguibile,
# versione dichiarata dall'app): va installato accanto a lui, altrimenti lo shim
# installato non puo' rispondere e resta senza il controllo.
IDENT = HERE / "craft-bridge-ident.py"
FILES = (WRAPPER, IDENT)
DEFAULT_INSTALL_DIR = Path.home() / "AppData" / "Local" / "Programs" / "craft-bridge"
DEFAULT_CONFIG = Path.home() / ".agents" / "mcp.json"
PYTHON = Path.home() / "AppData" / "Local" / "Programs" / "Python" / "Python312" / "python.exe"


def apps_table() -> dict:
    proc = subprocess.run(
        [sys.executable, str(WRAPPER), "--dump-apps"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        raise SystemExit(f"impossibile leggere la tabella delle app: {proc.stderr}")
    return json.loads(proc.stdout)


def entry_for(slug: str, spec: dict, port: int, wrapper_path: Path, token_file: str | None):
    args = [str(wrapper_path), "--slug", slug, "--port", str(port)]
    if spec.get("needs_token"):
        args += ["--token-file", token_file]
    return {"type": "stdio", "command": str(PYTHON), "args": args, "env": {}}


def load_config(path: Path) -> dict:
    if not path.is_file():
        return {"mcpServers": {}}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def planned_entries(table: dict, wrapper_path: Path, token_file: str,
                    overrides: dict | None = None, restore: bool = False) -> dict:
    """Le entry che questo installer scriverebbe, senza toccare niente.

    Una sola definizione: la usano sia `--apply` sia `craft-bridge-doctor.py` per
    dire se la config e' quella attesa, cosi' i due non possono divergere.
    """
    plan = {}
    for slug, spec in table.items():
        if restore:
            plan[slug] = {"type": "stdio", "command": spec["cli"], "args": ["mcp"], "env": {}}
        else:
            port = int((overrides or {}).get(slug, spec["port"]))
            plan[slug] = entry_for(slug, spec, port, wrapper_path, token_file)
    return plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--install-dir", default=str(DEFAULT_INSTALL_DIR))
    parser.add_argument("--port", action="append", default=[], help="slug=porta (ripetibile)")
    parser.add_argument("--token-file",
                        default=str(Path.home() / ".craft-bridge" / "photocraft.token"))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--restore", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    config_path = Path(args.config)
    install_dir = Path(args.install_dir)
    overrides = dict(p.split("=", 1) for p in args.port)
    table = apps_table()

    wrapper_path = install_dir / WRAPPER.name
    plan = planned_entries(table, wrapper_path, args.token_file,
                           overrides=overrides, restore=args.restore)

    if args.json:
        print(json.dumps({"mcpServers": plan}, indent=2))
        return 0

    config = load_config(config_path)
    servers = config.setdefault("mcpServers", {})
    changed, unchanged = [], []
    for slug, entry in plan.items():
        if servers.get(slug) == entry:
            unchanged.append(slug)
        else:
            changed.append(slug)

    # Lo shim **installato** e' quello che i client eseguono davvero: va allineato al
    # repo anche quando nessuna entry cambia, altrimenti una modifica allo shim resta
    # nel repo e il comportamento installato e' quello vecchio (misurato: entry
    # invariate -> nessuna copia, e i due file differivano).
    def stale(src: Path) -> bool:
        try:
            return src.read_bytes() != (install_dir / src.name).read_bytes()
        except OSError:
            return True

    stale_files = [src for src in FILES if stale(src)]

    print(f"config      : {config_path}")
    print(f"wrapper     : {wrapper_path}"
          + (" (da allineare al repo)" if stale_files and not args.restore else
             " (gia' allineato)" if not args.restore else " (lasciato com'e')"))
    print(f"da aggiornare ({len(changed)}): {', '.join(changed) or '-'}")
    print(f"invariate ({len(unchanged)}): {', '.join(unchanged) or '-'}")
    untouched = [s for s in servers if s not in plan]
    print(f"non toccate  : {', '.join(untouched) or '-'}")

    if not args.apply:
        print("\n(dry-run: usa --apply per scrivere)")
        return 0

    if changed:
        install_dir.mkdir(parents=True, exist_ok=True)
        if config_path.is_file():
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = config_path.with_suffix(f".json.bak-{stamp}")
            shutil.copy2(config_path, backup)
            print(f"backup      : {backup}")
        servers.update(plan)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config, indent=4), encoding="utf-8")
        print(f"scritto     : {config_path}")
    if stale_files and not args.restore:
        install_dir.mkdir(parents=True, exist_ok=True)
        for src in stale_files:
            shutil.copy2(src, install_dir / src.name)
        print(f"installato  : {', '.join(str(install_dir / s.name) for s in stale_files)}")

    print("verifica tutto l'assieme con: python craft-bridge-doctor.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
