#!/usr/bin/env python3
"""Registra il ponte Craft nei *client MCP* che l'utente ha davvero installato.

`craft-bridge-config.py` scrive **una** config (`~/.agents/mcp.json`), quella che
Freebuff e gli agenti `.agents` leggono. Ma lo stesso shim lo possono vedere anche
Claude Desktop, Claude Code, Cursor, Windsurf, VS Code/Copilot, Cline, LM Studio,
Zed, Codex (ChatGPT desktop) e DeepSeek Harness (`dsh`): ognuno con il **suo** file,
in formati diversi (JSON `mcpServers`, JSON `servers`, JSON `context_servers`
annidato, TOML, YAML di patch). Riscriverli a mano, per ogni client, e' il punto in
cui si sbaglia - e non si sa di aver sbagliato, perche' il client semplicemente non
mostra il server.

Questo strumento prende le entry da **una sola fonte** (`craft-bridge-config.py`,
la stessa funzione che le scrive) e le deposita, senza duplicare la tabella delle
app. Per ogni client: se il file c'e' lo aggiorna (con backup), se non c'e' lo dice,
se e' gia' a posto non tocca niente. I formati non-JSON sono trattati con cura
minima ma idempotente: TOML per Codex (`[mcp_servers.<slug>]`), YAML per `dsh`
(un `insert` per app, id `craft-bridge-<slug>`), `context_servers` annidato per Zed.

    python craft-bridge-connect.py                       # dry-run: cosa cambierebbe
    python craft-bridge-connect.py --list                # quali client ci sono e cosa vedono
    python craft-bridge-connect.py --apply               # scrive (con backup)
    python craft-bridge-connect.py --apply --client cursor --client zed
    python craft-bridge-connect.py --apply --client codex --client dsh
    python craft-bridge-connect.py --restore --client cursor   # toglie le nostre entry
    python craft-bridge-connect.py --json

Sicurezza: di default **non scrive niente** (dry-run). Solo `--apply` scrive, e prima
fa una copia `.bak-<timestamp>`. La config vera non e' mai una cavia: i test usano
`--client-path <id>=<file>` su file temporanei (come la suite fa con `--config`).

Client e percorsi di default (Windows, per-utente). I percorsi li dichiara la
documentazione di ogni client; se un client cambia posto, `--client-path` lo corregge
senza toccare il codice.

    agents          ~/.agents/mcp.json                          (Freebuff e agenti .agents)
    claude-desktop  %APPDATA%/Claude/claude_desktop_config.json
    claude-code     via CLI `claude mcp add --scope user`
    cursor          ~/.cursor/mcp.json
    windsurf        ~/.codeium/windsurf/mcp_config.json
    antigravity     ~/.gemini/config/mcp_config.json
    vscode          ~/.copilot/mcp-config.json                  (Copilot, utente)
    vscode-workspace  <progetto>/.vscode/mcp.json               (chiave `servers`, per-utente)
    cline           ~/.cline/data/settings/cline_mcp_settings.json
    lmstudio        ~/.lmstudio/mcp.json
    zed             %APPDATA%/Zed/settings.json                 (chiave `context_servers`)
    codex           ~/.codex/config.toml                        (TOML)
    dsh             ~/.dsh/profiles/desktop/cordis.patch.yml    (YAML di patch)

Esito:
    0  niente da fare, oppure scrittura riuscita
    1  almeno un client ha rifiutato una scrittura (vedi il dettaglio)
    2  errore d'uso (client o slug sconosciuto)
    3  file di un client illeggibile: nessuna modifica fatta su quel client
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
WRAPPER = HERE / "craft-bridge-mcp.py"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    if spec is None or spec.loader is None:
        raise SystemExit(f"strumento non caricabile: {HERE / filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONFIG = _load("craft_bridge_config", "craft-bridge-config.py")

MARKER = "craft-bridge"          # prefisso degli id/entry che scriviamo noi


def home() -> Path:
    return Path.home()


def roaming() -> Path:
    return Path(os.environ.get("APPDATA") or (home() / "AppData" / "Roaming"))


# ---------------------------------------------------------------------------------
# I client: dove leggono, e in che forma
# ---------------------------------------------------------------------------------
# `kind` dice come si scrive, non *cosa*: le entry arrivano tutte da `planned_entries`.
# `path` a None significa "dipende dal progetto": lo si passa con --client-path.

def clients() -> list[dict]:
    return [
        {"id": "agents", "title": "Freebuff / agenti .agents", "kind": "json",
         "path": home() / ".agents" / "mcp.json",
         "note": "e' anche la config di craft-bridge-config.py --apply"},
        {"id": "claude-desktop", "title": "Claude Desktop", "kind": "json",
         "path": roaming() / "Claude" / "claude_desktop_config.json"},
        {"id": "claude-code", "title": "Claude Code (CLI)", "kind": "cli",
         "path": None, "command": "claude"},
        {"id": "cursor", "title": "Cursor", "kind": "json",
         "path": home() / ".cursor" / "mcp.json"},
        {"id": "windsurf", "title": "Windsurf / Cascade", "kind": "json",
         "path": home() / ".codeium" / "windsurf" / "mcp_config.json"},
        {"id": "antigravity", "title": "Antigravity", "kind": "json",
         "path": home() / ".gemini" / "config" / "mcp_config.json"},
        {"id": "vscode", "title": "VS Code / Copilot (utente)", "kind": "json",
         "path": home() / ".copilot" / "mcp-config.json", "key": "mcpServers"},
        {"id": "vscode-workspace", "title": "VS Code workspace (.vscode/mcp.json)",
         "kind": "vscode", "path": None,
         "note": "per-progetto: passa --client-path vscode-workspace=<dir>/.vscode/mcp.json"},
        {"id": "cline", "title": "Cline", "kind": "json",
         "path": home() / ".cline" / "data" / "settings" / "cline_mcp_settings.json"},
        {"id": "lmstudio", "title": "LM Studio", "kind": "json",
         "path": home() / ".lmstudio" / "mcp.json"},
        {"id": "zed", "title": "Zed", "kind": "zed",
         "path": roaming() / "Zed" / "settings.json"},
        {"id": "codex", "title": "OpenAI Codex / ChatGPT desktop", "kind": "toml",
         "path": home() / ".codex" / "config.toml"},
        {"id": "dsh", "title": "DeepSeek Harness (dsh), profilo desktop", "kind": "yaml",
         "path": home() / ".dsh" / "profiles" / "desktop" / "cordis.patch.yml"},
    ]


def client_by_id(cid: str) -> dict | None:
    for c in clients():
        if c["id"] == cid:
            return c
    return None


def client_path(c: dict, override: dict | None = None) -> Path | None:
    """Il file di un client, con la sostituzione dei test (`--client-path`)."""
    if override and c["id"] in override:
        return Path(override[c["id"]])
    return c["path"]


def present_clients(override: dict | None = None) -> list[dict]:
    """I client la cui cartella esiste su questa macchina (il file puo' non esserci)."""
    out = []
    for c in clients():
        p = client_path(c, override)
        if p is not None and p.parent.is_dir():
            out.append(c)
    return out


def bridge_slugs(c: dict, path: Path, expected: set[str]) -> set[str] | None:
    """Quali slug di `expected` questo client ha **come entry del ponte**.

    "Del ponte" vuol dire che l'entry nomina lo shim o il traduttore: un'entry
    headless del fornitore (la CLI con `mcp`) **non** conta, ed e' proprio il caso che
    il controllo deve accusare. `None` = non leggibile, o una forma (la CLI di Claude
    Code) che non si ispeziona da un file.
    """
    kind = c["kind"]
    if kind == "cli":
        return None
    if kind in ("json", "vscode", "zed"):
        try:
            cfg = _json_read(path)
        except (OSError, json.JSONDecodeError):
            return None
        key = {"vscode": "servers", "zed": "context_servers"}.get(kind, "mcpServers")
        servers = cfg.get(key) or {}
        return {slug for slug, entry in servers.items()
                if slug in expected and _mentions_bridge(entry, kind)}
    if kind in ("toml", "yaml") and path.is_file():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        if kind == "toml":
            lines = text.splitlines()
            return {s for s in expected if _toml_is_bridge(lines, s)}
        return {s for s in expected if f"id: {MARKER}-{s}" in text}
    return set()


def _mentions_bridge(entry: dict, kind: str) -> bool:
    if not isinstance(entry, dict):
        return False
    if kind == "zed":
        cmd = str((entry.get("command") or {}).get("path") or "")
        args = " ".join(str(a) for a in ((entry.get("command") or {}).get("args") or []))
    else:
        cmd = str(entry.get("command") or "")
        args = " ".join(str(a) for a in (entry.get("args") or []))
    blob = f"{cmd} {args}"
    return "craft-bridge-mcp.py" in blob or "craft-bridge-ui.py" in blob


def _toml_is_bridge(lines: list[str], slug: str) -> bool:
    rng = _block_range(lines, f"[mcp_servers.{slug}]")
    return bool(rng) and "craft-bridge" in "\n".join(lines[rng[0]:rng[1]])


# ---------------------------------------------------------------------------------
# Le entry: dalla stessa funzione che le scrive in ~/.agents/mcp.json
# ---------------------------------------------------------------------------------

def plan(install_dir: Path, token_file: str, control_file: str,
         overrides: dict | None = None, slugs: set[str] | None = None) -> dict:
    table = CONFIG.apps_table()
    entries = CONFIG.planned_entries(table, install_dir / WRAPPER.name, token_file,
                                     overrides=overrides, install_dir=install_dir,
                                     control_file=control_file)
    if slugs:
        entries = {k: v for k, v in entries.items() if k in slugs}
    return entries


# ---------------------------------------------------------------------------------
# Scrittori, uno per forma. Ognuno: legge -> (invariate, da aggiornare) -> scrive.
# ---------------------------------------------------------------------------------

def _json_read(path: Path) -> dict:
    if not path.is_file():
        return {}
    raw = path.read_text(encoding="utf-8-sig")
    return json.loads(raw) if raw.strip() else {}


def _backup(path: Path) -> Path | None:
    if not path.is_file():
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = path.with_name(path.name + f".bak-{stamp}")
    shutil.copy2(path, bak)
    return bak


def _json_shape(kind: str, entry: dict) -> dict:
    """La entry nella forma che quel client vuole (i campi restano: type/command/args/env)."""
    if kind == "zed":
        return {"command": {"path": entry["command"], "args": entry["args"],
                            "env": entry.get("env") or {}}}
    return {"type": "stdio", "command": entry["command"], "args": entry["args"],
            "env": entry.get("env") or {}}


def write_json(path: Path, key: str, kind: str, entries: dict, restore: bool) -> dict:
    cfg = _json_read(path)
    servers = cfg.setdefault(key, {})
    added, updated, unchanged, removed = [], [], [], []
    for slug, entry in entries.items():
        want = _json_shape(kind, entry)
        if restore:
            if slug in servers:
                servers.pop(slug)
                removed.append(slug)
            continue
        if slug not in servers:
            servers[slug] = want
            added.append(slug)
        elif servers[slug] != want:
            servers[slug] = want
            updated.append(slug)
        else:
            unchanged.append(slug)
    return {"added": added, "updated": updated, "unchanged": unchanged,
            "removed": removed, "_cfg": cfg}


def write_toml(path: Path, entries: dict, restore: bool) -> dict:
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    lines = text.splitlines()
    added, updated, unchanged, removed = [], [], [], []
    for slug, entry in entries.items():
        head = f"[mcp_servers.{slug}]"
        block = _toml_block(slug, entry)
        idx = _block_range(lines, head)
        present = idx is not None
        if restore:
            if present:
                a, b = idx
                lines = lines[:a] + lines[b:]
                removed.append(slug)
            continue
        if not present:
            if lines and lines[-1].strip():
                lines.append("")
            lines += block
            added.append(slug)
        else:
            a, b = idx
            if lines[a:b] == block:
                unchanged.append(slug)
            else:
                lines = lines[:a] + block + lines[b:]
                updated.append(slug)
    return {"added": added, "updated": updated, "unchanged": unchanged,
            "removed": removed, "_text": "\n".join(lines) + "\n"}


def _toml_block(slug: str, entry: dict) -> list[str]:
    # json.dumps per le stringhe: le regole di escape di TOML basic-string sono le
    # stesse di JSON per `\` e `"`, e i percorsi Windows sono pieni di `\`.
    q = lambda s: json.dumps(s, ensure_ascii=False)
    args = ", ".join(q(a) for a in entry["args"])
    return [f"[mcp_servers.{slug}]", f"command = {q(entry['command'])}",
            f"args = [{args}]"]


def _block_range(lines: list[str], head: str) -> tuple[int, int] | None:
    """Intervallo [a,b) della tabella TOML `head` (fino alla prossima tabella)."""
    start = None
    for i, line in enumerate(lines):
        if line.strip() == head:
            start = i
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].lstrip().startswith("["):
            end = j
            break
    return start, end


def write_yaml(path: Path, entries: dict, restore: bool) -> dict:
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    lines = text.splitlines()
    added, updated, unchanged, removed = [], [], [], []
    for slug, entry in entries.items():
        marker = f"{MARKER}-{slug}"
        idx = _yaml_item_range(lines, marker)
        block = _yaml_block(slug, entry)
        present = idx is not None
        if restore:
            if present:
                a, b = idx
                lines = lines[:a] + lines[b:]
                removed.append(slug)
            continue
        if not present:
            if lines and lines[-1].strip():
                lines.append("")
            lines += block
            added.append(slug)
        else:
            a, b = idx
            if lines[a:b] == block:
                unchanged.append(slug)
            else:
                lines = lines[:a] + block + lines[b:]
                updated.append(slug)
    return {"added": added, "updated": updated, "unchanged": unchanged,
            "removed": removed, "_text": "\n".join(lines) + "\n"}


def _yaml_item_range(lines: list[str], marker: str) -> tuple[int, int] | None:
    """Intervallo [a,b) della voce di lista top-level che contiene `marker`."""
    owner = None
    for i, line in enumerate(lines):
        if line.startswith("- ") and marker in "\n".join(lines[i:i + 12]):
            owner = i
            break
    if owner is None:
        return None
    end = len(lines)
    for j in range(owner + 1, len(lines)):
        if lines[j].startswith("- "):
            end = j
            break
    return owner, end


def _yaml_block(slug: str, entry: dict) -> list[str]:
    # YAML single-quoted: i `\` sono letterali e l'unico escape e' `''`. I percorsi
    # Windows non contengono apici, quindi l'id e il percorso restano leggibili.
    q = lambda s: "'" + str(s).replace("'", "''") + "'"
    args = ", ".join(q(a) for a in entry["args"])
    return [
        "- insert:",
        f"    - id: {MARKER}-{slug}",
        "      name: '@deepseek-ai/dsh-mcp-client'",
        "      config:",
        f"        serverName: {slug}",
        "        transport: stdio",
        f"        command: {q(entry['command'])}",
        f"        args: [{args}]",
    ]


def write_cli(client: dict, entries: dict, restore: bool, dry: bool) -> dict:
    """Claude Code: la config si tocca solo dalla sua CLI (`claude mcp add`)."""
    exe = shutil.which(client["command"])
    if not exe:
        return {"absent": True, "added": [], "updated": [], "unchanged": [],
                "removed": [], "why": f"CLI '{client['command']}' non trovata"}
    present = _cli_present(exe)
    added, updated, unchanged, removed, failed = [], [], [], [], []
    for slug, entry in entries.items():
        if restore:
            if slug in present:
                if dry or _cli_run(exe, "remove", slug):
                    removed.append(slug)
                else:
                    failed.append(slug)
            continue
        if slug not in present:
            if dry or _cli_add(exe, slug, entry):
                added.append(slug)
            else:
                failed.append(slug)
        elif present[slug] == [entry["command"]] + list(entry["args"]):
            unchanged.append(slug)
        else:
            if dry:
                updated.append(slug)
                continue
            _cli_run(exe, "remove", slug)
            if _cli_add(exe, slug, entry):
                updated.append(slug)
            else:
                failed.append(slug)
    return {"added": added, "updated": updated, "unchanged": unchanged,
            "removed": removed, "failed": failed}


def _cli_present(exe: str) -> dict:
    out = subprocess.run([exe, "mcp", "list"], capture_output=True, text=True,
                         encoding="utf-8", errors="replace").stdout or ""
    return {m.group(1): [] for m in re.finditer(r"(?m)^\s*(\S+):\s*$", out)}


def _cli_add(exe: str, slug: str, entry: dict) -> bool:
    cmd = [exe, "mcp", "add", "--scope", "user", slug, "--", entry["command"]] + list(entry["args"])
    return subprocess.run(cmd, capture_output=True, text=True).returncode == 0


def _cli_run(exe: str, verb: str, slug: str) -> bool:
    return subprocess.run([exe, "mcp", verb, slug, "-s", "user"],
                          capture_output=True, text=True).returncode == 0


# ---------------------------------------------------------------------------------
# Applicazione per client
# ---------------------------------------------------------------------------------

def apply_client(client: dict, entries: dict, restore: bool, dry: bool, path: Path | None) -> dict:
    kind = client["kind"]
    row = {"id": client["id"], "title": client["title"], "kind": kind,
           "path": str(path) if path else None}
    if kind == "cli":
        if dry:
            row.update({"present": True, "dry": True})
            # contare le entry senza scrivere: l'unico modo e' `mcp add`, quindi qui si
            # dichiara quanti server toccherebbe, non lo stato puntuale di ognuno.
            row.update({"plan": len(entries)})
            return row
        try:
            row.update(write_cli(client, entries, restore, dry=False))
        except OSError as exc:
            row.update({"error": str(exc)})
        return row

    if path is None:
        row.update({"absent": True, "why": client.get("note") or "percorso non indicato"})
        return row
    if not path.parent.is_dir():
        row.update({"absent": True, "why": "client non installato (cartella assente)"})
        return row

    try:
        if kind in ("json", "vscode", "zed"):
            key = {"vscode": "servers", "zed": "context_servers"}.get(kind, "mcpServers")
            res = write_json(path, key, kind, entries, restore)
        elif kind == "toml":
            res = write_toml(path, entries, restore)
        elif kind == "yaml":
            res = write_yaml(path, entries, restore)
        else:
            row.update({"absent": True, "why": f"forma non gestita: {kind}"})
            return row
    except (OSError, json.JSONDecodeError) as exc:
        row.update({"error": f"{type(exc).__name__}: {exc}"})
        return row

    cfg = res.pop("_cfg", None)
    text = res.pop("_text", None)
    row.update(res)
    row["present"] = True
    changed = bool(res["added"] or res["updated"] or res["removed"])
    if not dry and changed:
        bak = _backup(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if cfg is not None:
            path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        else:
            path.write_text(text, encoding="utf-8")
        row["backup"] = str(bak) if bak else None
        row["wrote"] = True
    return row


# ---------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------

def default_paths(overrides: dict) -> dict:
    return {c["id"]: c["path"] for c in clients()}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser()
    parser.add_argument("--client", action="append", default=[], metavar="ID",
                        help="limita a un client (ripetibile); default: tutti")
    parser.add_argument("--client-path", action="append", default=[], metavar="ID=FILE",
                        help="percorso diverso per un client (ripetibile); serve ai test")
    parser.add_argument("--apps", help="slug separati da virgola (default: tutte le app del ponte)")
    parser.add_argument("--install-dir", default=str(CONFIG.DEFAULT_INSTALL_DIR))
    parser.add_argument("--token-file",
                        default=str(home() / ".craft-bridge" / "photocraft.token"))
    parser.add_argument("--control-file",
                        default=str(home() / ".craft-bridge" / "pdfcraft-control.json"))
    parser.add_argument("--port", action="append", default=[], help="slug=porta (ripetibile)")
    parser.add_argument("--restore", action="store_true",
                        help="toglie le entry del ponte invece di scriverle")
    parser.add_argument("--apply", action="store_true", help="scrive (default: dry-run)")
    parser.add_argument("--list", action="store_true", help="mostra i client, non pianifica nulla")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    overrides = dict(p.split("=", 1) for p in args.port)
    path_over = dict(p.split("=", 1) for p in args.client_path)
    slugs = set(s.strip() for s in args.apps.split(",")) if args.apps else None

    wanted = args.client or [c["id"] for c in clients()]
    for cid in wanted + list(path_over):
        if client_by_id(cid) is None:
            print(f"client sconosciuto: {cid}", file=sys.stderr)
            return 2

    if args.list:
        rows = []
        for c in clients():
            if c["id"] not in wanted:
                continue
            path = Path(path_over[c["id"]]) if c["id"] in path_over else c["path"]
            rows.append({"id": c["id"], "title": c["title"], "kind": c["kind"],
                         "path": str(path) if path else None,
                         "present": bool(path and path.parent.is_dir())})
        if args.json:
            print(json.dumps({"clients": rows}, indent=2, ensure_ascii=False))
            return 0
        print("client MCP e dove leggono:")
        for r in rows:
            mark = "si " if r["present"] else "no "
            print(f"  {mark} {r['id']:<17} {r['kind']:<5} {r['path'] or '-'}")
        print("\n(si/no = la cartella del client esiste su questa macchina)")
        return 0

    entries = plan(Path(args.install_dir), args.token_file, args.control_file,
                   overrides=overrides, slugs=slugs)
    dry = not args.apply
    results = []
    for c in clients():
        if c["id"] not in wanted:
            continue
        path = Path(path_over[c["id"]]) if c["id"] in path_over else c["path"]
        results.append(apply_client(c, entries, args.restore, dry, path))

    if args.json:
        print(json.dumps({"dry_run": dry, "restore": args.restore,
                          "entries": sorted(entries), "clients": results},
                         indent=2, ensure_ascii=False))
        return 1 if any(r.get("error") for r in results) else 0

    verb = "toglierebbe" if args.restore else "registrerebbe"
    print(f"craft-bridge connect - {len(entries)} entry "
          f"({'toglierebbe' if args.restore else 'scrive' if args.apply else 'dry-run'})")
    print(f"  entry: {', '.join(sorted(entries))}\n")
    problems = 0
    for r in results:
        if r.get("error"):
            problems += 1
            print(f"  FAIL {r['id']:<17} {r['error']}")
            continue
        if r.get("absent"):
            print(f"  --   {r['id']:<17} {r.get('why') or 'assente'}")
            continue
        if r["kind"] == "cli" and r.get("dry"):
            print(f"  --   {r['id']:<17} (via CLI: userebbe {r['plan']} server, --apply per scrivere)")
            continue
        n = {k: len(r.get(k) or []) for k in ("added", "updated", "unchanged", "removed")}
        tag = "scritto" if r.get("wrote") else "pianificato" if dry else "invariato"
        print(f"  ok   {r['id']:<17} +{n['added']} ~{n['updated']} "
              f"={n['unchanged']} -{n['removed']}  [{tag}] {r['path']}")
    if dry:
        print("\n(dry-run: usa --apply per scrivere; ogni scrittura fa un backup .bak-<data>)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
