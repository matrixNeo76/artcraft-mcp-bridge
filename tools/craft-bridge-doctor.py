#!/usr/bin/env python3
"""Guarda tutto l'assieme in un colpo solo e da' **un verdetto con le azioni**.

I controlli che tengono in piedi il bridge sono quattro, e finora ognuno viveva nel
suo strumento: lo shim installato deve essere quello del repo (altrimenti i client
eseguono codice vecchio), le entry di `~/.agents/mcp.json` devono essere quelle che
l'installer scriverebbe (altrimenti un'app resta headless senza che nessuno lo dica),
gli eseguibili devono esserci, e quello che *gira* sulla porta deve essere la build
configurata (il catalogo identifica l'app, non la versione). Questo comando li
interroga tutti e risponde in fondo con una riga sola:

    VERDETTO: tutto in ordine (nessuna azione)

oppure

    VERDETTO: 2 cose da sistemare
      1. shim installato: non e' quello del repo: ...
         -> python craft-bridge-config.py --apply
      2. porta 7990: gridcraft: gira 0.5.0 (...) invece di 0.6.1 (...)
         -> chiudi l'istanza e riapri l'app dall'apposita entry

Non duplica niente: le entry attese vengono da `craft-bridge-config.py` (la stessa
funzione che scrive) e la domanda sulla build da `craft-bridge-ident.py` (le stesse
funzioni che usa la diagnosi). Se i due strumenti cambiano, cambia anche questo.

Uso:
    python craft-bridge-doctor.py                 # tutto, comprese le app aperte
    python craft-bridge-doctor.py --no-live       # solo repo, shim, config, eseguibili
    python craft-bridge-doctor.py --json

Esito:
    0  niente da sistemare
    1  almeno una cosa da sistemare (le azioni sono in fondo)
    2  errore d'uso
    3  config o tabella delle app illeggibili
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name: str, filename: str):
    """Carica uno strumento accanto a questo (i nomi hanno trattini: niente import)."""
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    if spec is None or spec.loader is None:
        raise SystemExit(f"strumento non caricabile: {HERE / filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


IDENT = _load("craft_bridge_ident", "craft-bridge-ident.py")
CONFIG = _load("craft_bridge_config", "craft-bridge-config.py")

# Cosa deve esserci nel repo perche' l'assieme funzioni.
REQUIRED = ("craft-bridge-mcp.py", "craft-bridge-ident.py", "craft-bridge-config.py")
# Cosa deve esserci **installato** accanto allo shim: lo shim delega a ident la
# domanda sulla build, quindi senza quel file il controllo non si puo' fare.
INSTALLED = ("craft-bridge-mcp.py", "craft-bridge-ident.py")


def sha12(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def result(check: str, state: str, detail: str, action: str = "") -> dict:
    """state: ok | fail | nota. Solo `fail` conta nel verdetto."""
    return {"check": check, "state": state, "detail": detail, "action": action}


def check_repo() -> list[dict]:
    missing = [n for n in REQUIRED if not (HERE / n).is_file()]
    if missing:
        return [result("repo", "fail", f"strumenti mancanti: {', '.join(missing)}",
                       "sei nella cartella giusta? (gli strumenti stanno insieme)")]
    hashes = ", ".join(f"{n.replace('craft-bridge-', '').replace('.py', '')} {sha12(HERE / n)}"
                       for n in REQUIRED)
    return [result("repo", "ok", f"{len(REQUIRED)} strumenti presenti ({hashes})")]


def check_installed(install_dir: Path) -> list[dict]:
    """Lo shim installato e' quello del repo? E' lui che i client eseguono davvero."""
    rows, stale = [], []
    for name in INSTALLED:
        src, dst = HERE / name, install_dir / name
        if not src.is_file():
            continue
        if not dst.is_file():
            stale.append(f"{name} assente")
            continue
        a, b = sha12(src), sha12(dst)
        if a == b:
            rows.append(f"{name} {a}")
        else:
            stale.append(f"{name} {a} != {b}")
    if stale:
        return [result("shim installato", "fail",
                       f"non e' quello del repo: {'; '.join(stale)}",
                       "python craft-bridge-config.py --apply")]
    if not rows:
        return [result("shim installato", "fail", "nessun file installato",
                       "python craft-bridge-config.py --apply")]
    return [result("shim installato", "ok",
                   f"{len(rows)} file identici al repo ({', '.join(rows)})")]


def entry_paths(entry: dict) -> dict:
    """I percorsi che una entry cita: comando, wrapper e file della credenziale."""
    args = [str(a) for a in (entry.get("args") or [])]
    token = args[args.index("--token-file") + 1] if "--token-file" in args else None
    wrapper = next((a for a in args if a.endswith(".py")), None)
    return {"command": entry.get("command"), "wrapper": wrapper, "token": token}


def check_config(config_path: Path, table: dict, install_dir: Path,
                 token_file: str) -> list[dict]:
    """La config e' quella che l'installer scriverebbe? E i file che cita esistono?"""
    try:
        live = CONFIG.load_config(config_path).get("mcpServers", {})
    except (OSError, json.JSONDecodeError) as exc:
        return [result("config", "fail", f"illeggibile: {exc}", f"controlla {config_path}")]
    plan = CONFIG.planned_entries(table, install_dir / IDENT.WRAPPER.name, token_file)
    to_fix = sorted(s for s in plan if live.get(s) != plan[s])
    out = [result("config", "fail",
                  f"{len(to_fix)} di {len(plan)} entry non sono quelle attese: {', '.join(to_fix)}",
                  "python craft-bridge-config.py --apply")] if to_fix else \
          [result("config", "ok", f"{len(plan)} entry come le scriverebbe l'installer")]

    broken, missing_tokens = [], []
    for slug, entry in sorted(live.items()):
        paths = entry_paths(entry)
        for kind in ("command", "wrapper"):
            if paths[kind] and not Path(paths[kind]).exists():
                broken.append(f"{slug}.{kind}")
        if paths["token"] and not Path(paths["token"]).exists():
            missing_tokens.append(f"{slug} ({Path(paths['token']).name})")
    if broken:
        out.append(result("percorsi", "fail",
                          f"le entry citano file che non esistono: {', '.join(broken)}",
                          "python craft-bridge-config.py --apply (o reinstalla Python)"))
    else:
        out.append(result("percorsi", "ok", "tutti i file citati dalle entry esistono"))
    if missing_tokens:
        # Non e' un guasto: il token lo scrive l'app al primo avvio con quel flag.
        out.append(result("credenziale", "nota",
                          f"token non ancora scritto per {', '.join(missing_tokens)}",
                          "si crea al primo avvio dell'app con --control-token-file"))
    return out


def check_apps(table: dict) -> list[dict]:
    """Gli eseguibili che la config userebbe: CLI installata ed eseguibile dell'app."""
    missing = [f"{slug} cli" for slug, spec in table.items() if not Path(spec["cli"]).is_file()]
    missing += [f"{slug} app" for slug, spec in table.items()
                if not IDENT.configured_exe(spec["cli"]).is_file()]
    if missing:
        return [result("eseguibili", "fail", f"mancano: {', '.join(sorted(missing))}",
                       "installa l'app, o correggi la tabella in craft-bridge-mcp.py")]
    versions = IDENT.file_versions([str(IDENT.configured_exe(s["cli"])) for s in table.values()])
    listed = ", ".join(sorted({str(v.get("version") or "?") for v in versions.values()}))
    return [result("eseguibili", "ok",
                   f"{len(table)} CLI e {len(table)} app presenti (versioni: {listed})")]


def check_live(table: dict, entries: dict) -> list[dict]:
    """Chi c'e' davvero sulle porte: peer, app e build che gira."""
    ports = {slug: int((entries.get(slug) or {}).get("port") or table[slug]["port"])
             for slug in table}
    pids = IDENT.listening_pids(list(ports.values()))
    facts = IDENT.process_facts(sorted(set(pids.values())))
    files = IDENT.file_versions([str(IDENT.configured_exe(table[s]["cli"])) for s in table])
    builds = IDENT.load_builds()
    out = []
    for slug, port in sorted(ports.items()):
        pid = pids.get(port)
        if pid is None:
            continue  # nessuno in ascolto: lo dice la riga in fondo, non undici righe
        token_file = (entries.get(slug) or {}).get("token_file")
        token = IDENT.read_token(token_file)
        field = "token"
        if slug == "wordcraft" and not token:
            token, field = IDENT.wordcraft_key(port), "key"
        verdict = IDENT.identify(port, timeout=3.0, token=token, token_field=field)
        if verdict["peer"] != "craft":
            out.append(result(f"porta {port}", "fail",
                              f"{slug}: la porta risponde ma non col canale di controllo "
                              f"(peer={verdict['peer']}), quindi lo shim va headless",
                              "chiudi cio' che occupa la porta, o cambia la porta nella entry"))
            continue
        if verdict["authenticated"] is False:
            # Il token della config non e' quello con cui gira l'app: il canale risponde
            # ma le chiamate del bridge vengono rifiutate. Il valore non si stampa mai.
            out.append(result(f"porta {port}", "fail",
                              f"{slug}: l'app ha rifiutato la credenziale della config "
                              f"({Path(token_file).name if token_file else 'nessun file'})",
                              "allinea il file del token (o la chiave di WordCraft) a quello "
                              "con cui l'app e' avviata, poi riprova"))
            continue
        # Quale app e' davvero: il catalogo del canale contro quello del CLI atteso.
        own = IDENT.cli_catalog(table[slug]["cli"])
        theirs = IDENT.channel_catalog(port, token, field, 6.0)
        coverage = len(own & theirs) / len(own) if own and theirs else None
        if coverage is not None and coverage < IDENT.MATCH:
            out.append(result(f"porta {port}", "fail",
                              f"{slug}: sulla porta risponde un'altra app "
                              f"(copre {coverage:.2f} dei suoi comandi, sotto la soglia "
                              f"{IDENT.MATCH})",
                              "chiudi l'istanza sbagliata: lo shim andra' headless"))
            continue
        running = IDENT.running_build(slug, port, pid=pid, facts=facts.get(pid, {}))
        recorded = builds.get(slug)
        configured = ({"version": str(recorded["version"]), "revision": recorded.get("revision"),
                       "exe": recorded.get("exe"),
                       "source": f"impronta registrata ({recorded.get('verified_at') or '?'})"}
                      if isinstance(recorded, dict) and recorded.get("version")
                      else IDENT.configured_build(slug, table[slug]["cli"], file_facts=files))
        shape = IDENT.build_verdict(running, configured)
        if shape["build"] == "different":
            out.append(result(f"porta {port}", "fail",
                              f"{slug}: gira {running.get('version')} ({running.get('exe') or '?'}) "
                              f"invece di {configured.get('version')} ({configured.get('source')})",
                              "chiudi l'istanza e riapri l'app dalla sua entry, "
                              "o allinea l'eseguibile"))
        elif shape["build"] == "same":
            out.append(result(f"porta {port}", "ok",
                              f"{slug} {running.get('version')} = config "
                              f"({configured.get('source')})"))
        else:
            out.append(result(f"porta {port}", "nota",
                              f"{slug}: build non verificabile ({shape['why']})",
                              "avvia l'app dalla sua entry e riprova"))
    opened = len([r for r in out if r["check"].startswith("porta ")])
    out.append(result("app aperte", "ok" if not opened else "nota",
                      f"{opened} su {len(ports)} porte in ascolto"
                      + ("" if opened else ": tutte headless, nessuna app aperta")))
    unrecorded = sorted(s for s in table
                        if not (isinstance(builds.get(s), dict) and builds[s].get("version")))
    if unrecorded:
        out.append(result("impronte", "nota",
                          f"build non registrate: {', '.join(unrecorded)}",
                          "craft-bridge-ident.py --all --record (con le app aperte)"))
    return out


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(CONFIG.DEFAULT_CONFIG))
    parser.add_argument("--install-dir", default=str(CONFIG.DEFAULT_INSTALL_DIR))
    parser.add_argument("--token-file",
                        default=str(Path.home() / ".craft-bridge" / "photocraft.token"))
    parser.add_argument("--no-live", action="store_true",
                        help="salta le porte: solo repo, shim, config, eseguibili")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    config_path, install_dir = Path(args.config), Path(args.install_dir)
    try:
        table = CONFIG.apps_table()
    except SystemExit as exc:
        print(f"tabella delle app illeggibile: {exc}", file=sys.stderr)
        return 3

    rows = check_repo() + check_installed(install_dir)
    try:
        entries = IDENT.shim_entries(config_path)
    except (SystemExit, json.JSONDecodeError):
        entries = {}
    rows += check_config(config_path, table, install_dir, args.token_file)
    rows += check_apps(table)
    if not args.no_live:
        rows += check_live(table, entries)

    todo = [r for r in rows if r["state"] == "fail"]
    report = {"checks": rows, "problems": len(todo), "ok": not todo,
              "actions": [f"{r['check']}: {r['detail']} -> {r['action']}" for r in todo]}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("craft-bridge doctor")
        for row in rows:
            mark = {"ok": "ok  ", "fail": "FIX ", "nota": "nota"}[row["state"]]
            print(f"  {mark} {row['check']:<15} {row['detail']}")
        if todo:
            print(f"\nVERDETTO: {len(todo)} "
                  + ("cosa da sistemare" if len(todo) == 1 else "cose da sistemare"))
            for i, row in enumerate(todo, 1):
                print(f"  {i}. {row['check']}: {row['detail']}")
                if row["action"]:
                    print(f"     -> {row['action']}")
        else:
            print("\nVERDETTO: tutto in ordine (nessuna azione)")
    return 1 if todo else 0


if __name__ == "__main__":
    sys.exit(main())
