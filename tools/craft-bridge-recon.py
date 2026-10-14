#!/usr/bin/env python3
"""Recon read-only del canale di controllo (bridged mode) delle Crafting Apps.

Non avvia nessuna applicazione: legge i binari in streaming e cerca i needle
del canale di controllo, estraendo un contesto stampabile attorno a ogni hit.
Serve a documentare con prove, e non a indovinare, i flag esatti di ogni app:
quale desktop app espone `--control`, quale CLI sa fare da bridge, e da dove
arriva il `control-token`.

Dove sta l'app lo dice il **sistema**: per ogni slug si chiede allo shim, cioe' alla
stessa funzione che legge la registrazione `App Paths` con cui il ponte trova la CLI
da collegare e l'eseguibile da avviare. `--root` resta il ripiego per le app che il
sistema non registra (e per un sistema che non ha il registro).

Uso:
    python craft-bridge-recon.py --matrix          # chi espone cosa (veloce)
    python craft-bridge-recon.py --app photocraft  # contesti su un'app
    python craft-bridge-recon.py --all-context     # contesti su tutte
    python craft-bridge-recon.py --json            # matrice + contesti in JSON
    python craft-bridge-recon.py --needle "control-token"
    python craft-bridge-recon.py --app gridcraft --root "D:/Apps"    # ripiego esplicito
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHIM = HERE / "craft-bridge-mcp.py"
DEFAULT_ROOT = r"C:\Program Files"

APPS = {
    "cadcraft": "CADCraft",
    "deckcraft": "DeckCraft",
    "designcraft": "DesignCraft",
    "effectcraft": "EffectCraft",
    "figcraft": "FigCraft",
    "filmcraft": "FilmCraft",
    "gridcraft": "GridCraft",
    "lightcraft": "LightCraft",
    "pdfcraft": "PdfCraft",
    "photocraft": "PhotoCraft",
    "soundcraft": "SoundCraft",
    "vectorcraft": "VectorCraft",
    "wordcraft": "WordCraft",
}

DEFAULT_NEEDLES = (
    b"--control",
    b"--bridge",
    b"--connect",
    b"--headless",
    b"--automation-read-root",
    b"control-token",
    b"control_token",
    b"CONTROL_TOKEN",
    b"control key",
    b"CONTROL_KEY",
    b"control-key",
    b"control-protocol.md",
    b"control server",
    b"Automation",
)

CHUNK = 4 * 1024 * 1024
OVERLAP = 512
CONTEXT = 200


_SHIM = None


def shim():
    """Lo shim caricato come modulo: la domanda sul registro si fa in un posto solo."""
    global _SHIM
    if _SHIM is None:
        spec = importlib.util.spec_from_file_location("craft_bridge_mcp_recon", SHIM)
        if spec is None or spec.loader is None:
            raise SystemExit(f"shim non caricabile: {SHIM}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _SHIM = module
    return _SHIM


def registered_dir(slug: str) -> Path | None:
    """La cartella dell'app secondo **il sistema**.

    `registered_exe` e' la stessa funzione con cui il ponte trova la CLI da collegare:
    una sola implementazione del registro, e un'app che si sposta non lascia qui un
    percorso vecchio. `None` quando il sistema non la registra (o il registro non
    esiste): allora vale `--root`.
    """
    exe, _hive = shim().registered_exe(slug)
    return Path(str(exe)).parent if exe else None


def printable(raw: bytes) -> str:
    out = []
    for byte in raw:
        char = chr(byte)
        out.append(char if 0x20 <= byte <= 0x7E else " ")
    return "".join(out)


def scan(path: Path, needles: list[bytes], max_hits: int):
    hits: list[tuple[bytes, str]] = []
    seen: set[str] = set()
    counts: dict[bytes, int] = {n: 0 for n in needles}
    tail = b""
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(CHUNK)
            if not chunk:
                break
            buf = tail + chunk
            for needle in needles:
                start = 0
                while True:
                    idx = buf.find(needle, start)
                    if idx < 0:
                        break
                    counts[needle] += 1
                    start = idx + 1
                    lo = max(0, idx - CONTEXT)
                    hi = min(len(buf), idx + len(needle) + CONTEXT)
                    text = " ".join(printable(buf[lo:hi]).split())
                    key = text[:160]
                    if key not in seen and len(hits) < max_hits:
                        seen.add(key)
                        hits.append((needle, text))
            tail = buf[-OVERLAP:]
    return counts, hits


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=None,
                        help="dove cercare le app che il sistema non registra "
                             f"(default: {DEFAULT_ROOT})")
    parser.add_argument("--app", help="slug di una sola app")
    parser.add_argument("--matrix", action="store_true", help="solo presenza dei needle")
    parser.add_argument("--all-context", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--needle", action="append", default=None)
    parser.add_argument("--max-hits", type=int, default=6)
    args = parser.parse_args()

    needles = [n.encode() for n in args.needle] if args.needle else list(DEFAULT_NEEDLES)
    root = Path(args.root or DEFAULT_ROOT)

    slugs = [args.app] if args.app else sorted(APPS)
    report: dict[str, dict] = {}
    for slug in slugs:
        folder = APPS.get(slug)
        if not folder:
            print(f"slug sconosciuto: {slug}", file=sys.stderr)
            return 2
        app_dir = registered_dir(slug) or (root / folder)
        entry = {}
        for kind, name in (("cli", f"{slug}-cli.exe"), ("app", f"{slug}.exe")):
            path = app_dir / name
            if not path.is_file():
                entry[kind] = {"missing": str(path)}
                continue
            counts, hits = scan(path, needles, args.max_hits)
            entry[kind] = {
                "path": str(path),
                "size": path.stat().st_size,
                "counts": {n.decode(): c for n, c in counts.items() if c},
                "hits": [
                    {"needle": n.decode(errors="replace"), "context": t} for n, t in hits
                ],
            }
        report[slug] = entry

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    if args.matrix or not args.all_context:
        # matrice: needle -> (cli, app)
        header = "needle".ljust(26) + "cli  app"
        print(header)
        print("-" * len(header))
        for needle in needles:
            row = []
            for kind in ("cli", "app"):
                present = 0
                for entry in report.values():
                    data = entry.get(kind, {})
                    if data.get("counts", {}).get(needle.decode()):
                        present += 1
                row.append(present)
            print(needle.decode().ljust(26) + f"{row[0]:<5}{row[1]}")
        print("\n(valori = numero di app in cui il needle compare)")

    if args.all_context or args.app:
        for slug, entry in report.items():
            print(f"\n=== {slug} ===")
            for kind in ("cli", "app"):
                data = entry.get(kind, {})
                if "missing" in data:
                    print(f"  [{kind}] MANCANTE")
                    continue
                print(f"  [{kind}] {data['path']}  ({data['size']} byte)")
                for hit in data["hits"]:
                    print(f"    ({hit['needle']}) ...{hit['context']}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
