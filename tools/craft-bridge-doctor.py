#!/usr/bin/env python3
"""Guarda tutto l'assieme in un colpo solo e da' **un verdetto con le azioni**.

I controlli che tengono in piedi il bridge sono quattro, e finora ognuno viveva nel
suo strumento: lo shim installato deve essere quello del repo (altrimenti i client
eseguono codice vecchio), le entry di `~/.agents/mcp.json` devono essere quelle che
l'installer scriverebbe (altrimenti un'app resta headless senza che nessuno lo dica),
gli eseguibili devono esserci, e quello che *gira* sulla porta deve essere la build
configurata (il catalogo identifica l'app, non la versione). Due controlli in piu' non
nascondono guasti ma li prevengono: **dove sta l'app** lo dice il sistema (`App Paths`,
scritto dall'installer) e la tabella scritta a mano lo conferma, cosi' un percorso
cablato che invecchia non passa in silenzio; e quello che il launcher di ArtCraft
**pubblica** viene confrontato con quello che risulta installato (feed letto da
`craft-bridge-feed.py`). Questo comando li interroga tutti e risponde in fondo con una
riga sola:

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
    python craft-bridge-doctor.py --feed-dir <cartella>   # feed del launcher di prova

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
import subprocess
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
# La tabella delle app e il flag di aggancio stanno nello shim: qui si chiede a lui,
# invece di tenere una seconda copia di quello che serve per guidare una finestra.
SHIM = _load("craft_bridge_mcp", "craft-bridge-mcp.py")
# Il confronto con la release pubblicata e' un'informazione in piu': se lo strumento
# che la legge non c'e', la diagnosi lo dice e continua, invece di morire.
try:
    FEED = _load("craft_bridge_feed", "craft-bridge-feed.py")
except SystemExit as exc:
    FEED = None
    FEED_WHY = str(exc)

# Cosa deve esserci nel repo perche' l'assieme funzioni.
REQUIRED = ("craft-bridge-mcp.py", "craft-bridge-ident.py", "craft-bridge-config.py",
            "craft-bridge-feed.py", "craft-bridge-ui.py")
# Cosa deve esserci **installato** accanto allo shim: lo shim delega a ident la
# domanda sulla build, quindi senza quel file il controllo non si puo' fare.
# (Le posizioni delle app non stanno qui: le risolve il sistema, e la tabella dello
# shim ne resta la conferma — vedi `check_locations`.)
INSTALLED = ("craft-bridge-mcp.py", "craft-bridge-ident.py", "craft-bridge-ui.py")


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
                 token_file: str, control_file: str) -> list[dict]:
    """La config e' quella che l'installer scriverebbe? E i file che cita esistono?"""
    try:
        live = CONFIG.load_config(config_path).get("mcpServers", {})
    except (OSError, json.JSONDecodeError) as exc:
        return [result("config", "fail", f"illeggibile: {exc}", f"controlla {config_path}")]
    plan = CONFIG.planned_entries(table, install_dir / IDENT.WRAPPER.name, token_file,
                                  install_dir=install_dir, control_file=control_file)
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


def check_apps(table: dict, file_facts: dict | None = None) -> list[dict]:
    """Gli eseguibili che la config userebbe: CLI installata ed eseguibile dell'app."""
    missing = [f"{slug} cli" for slug, spec in table.items() if not Path(spec["cli"]).is_file()]
    missing += [f"{slug} app" for slug, spec in table.items()
                if not IDENT.configured_exe(spec["cli"]).is_file()]
    if missing:
        return [result("eseguibili", "fail", f"mancano: {', '.join(sorted(missing))}",
                       "installa l'app, o correggi la tabella in craft-bridge-mcp.py")]
    versions = file_facts if file_facts is not None else \
        IDENT.file_versions([str(IDENT.configured_exe(s["cli"])) for s in table.values()])
    listed = ", ".join(sorted({str(v.get("version") or "?") for v in versions.values()}))
    return [result("eseguibili", "ok",
                   f"{len(table)} CLI e {len(table)} app presenti (versioni: {listed})")]


def check_locations(table: dict) -> list[dict]:
    """Chi dice dove sta l'app: il sistema o la tabella?

    La tabella si scrive a mano; `App Paths` lo aggiorna l'installer dell'app, ed e' la
    risposta che usa l'interfaccia di sistema quando apri l'app per nome. Il confronto e'
    fra la cartella che il **sistema** registra per l'app e quella che la tabella dichiara
    per la sua CLI: se divergono, la riga dice quale delle due si sta usando (il sistema
    quando la CLI sta accanto all'app, la tabella quando li' non c'e') — un percorso
    cablato che invecchia in silenzio e' il modo piu' facile per eseguire l'app sbagliata
    senza che nessuno se ne accorga.
    """
    drift = []
    for slug, spec in sorted(table.items()):
        declared, used = str(spec.get("declared_cli") or ""), str(spec.get("cli") or "")
        app = str(spec.get("app_exe") or "")
        if not (declared and app) or Path(app).parent == Path(declared).parent:
            continue
        in_use = ("si usa quella del sistema" if used and Path(used).parent == Path(app).parent
                  else "nessuna CLI accanto all'app: si usa quella della tabella")
        drift.append(f"{slug}: sistema -> {Path(app).parent}, "
                     f"tabella -> {Path(declared).parent} ({in_use})")
    if drift:
        return [result("posizione app", "nota",
                       "il sistema e la tabella non concordano: " + "; ".join(drift),
                       "allinea la tabella in craft-bridge-mcp.py (il percorso usato e' "
                       "quello del sistema quando la CLI sta accanto all'app)")]
    resolved = [slug for slug, spec in table.items()
                if str(spec.get("cli_source") or "").startswith("registro")]
    if resolved and len(resolved) == len(table):
        return [result("posizione app", "ok",
                       f"{len(resolved)} percorsi su {len(table)} dal registro App Paths: "
                       f"la tabella conferma, non decide")]
    if resolved:
        rest = sorted(set(table) - set(resolved))
        return [result("posizione app", "nota",
                       f"{len(resolved)} di {len(table)} percorsi dal registro App Paths "
                       f"(per {', '.join(rest)} vale la tabella)",
                       "quelle app non si registrano da sole: la tabella resta la fonte")]
    reason = ("questo sistema non ha un registro" if sys.platform != "win32"
              else "nessuna app risulta registrata in App Paths")
    return [result("posizione app", "nota",
                   f"nessun percorso dal registro ({reason}): la tabella e' l'unica fonte",
                   "su Windows le app installate si registrano da sole: se non c'e', "
                   "l'app e' installata in modo diverso")]


def check_translator(install_dir: Path, control_file: str) -> list[dict]:
    """Le app servite dal traduttore: la finestra risponde, e con quali metodi?

    Non e' un guasto che la finestra sia chiusa: la entry ripiega sul server headless
    del fornitore, quindi il verdetto resta `nota` con l'azione per aprirla. E' invece
    un guasto se il traduttore non risponde affatto, perche' allora l'entry non parte.
    Il confronto del catalogo e' la parte che nessun altro puo' fare: la tabella dei
    metodi e' una **copia** di quello che l'app dichiara, e quando l'app cambia idea
    la differenza si vede qui invece di manifestarsi come un tool che non esiste.
    """
    rows = []
    for slug in CONFIG.TRANSLATED:
        translator = install_dir / "craft-bridge-ui.py"
        if not translator.is_file():
            translator = HERE / "craft-bridge-ui.py"
        proc = subprocess.run(
            [sys.executable, str(translator), "--slug", slug, "--control", control_file,
             "--list", "--json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        if proc.returncode != 0 or not (proc.stdout or "").strip():
            rows.append(result(f"finestra {slug}", "fail",
                               f"il traduttore non risponde: {(proc.stderr or '').strip()[:120]}",
                               "python craft-bridge-config.py --apply"))
            continue
        try:
            report = json.loads(proc.stdout)
        except json.JSONDecodeError:
            rows.append(result(f"finestra {slug}", "fail", "uscita del traduttore non JSON",
                               "python craft-bridge-config.py --apply"))
            continue
        if report.get("mode") != "bridged":
            rows.append(result(f"finestra {slug}", "nota",
                               f"non guidabile ora ({report.get('mode_why')}): l'entry "
                               f"parla col server headless del fornitore",
                               f"avvia l'app con --control {control_file}"))
            continue
        window = report.get("window") or {}
        detail = (f"bridged sulla porta {report.get('port')} (pid {report.get('pid')}), "
                  f"finestra {window.get('width')}x{window.get('height')} punti")
        drift = report.get("drift") or {}
        if drift.get("checked") and not drift.get("same"):
            extra = []
            if drift.get("only_theirs"):
                extra.append(f"l'app ha in piu': {', '.join(drift['only_theirs'])}")
            if drift.get("only_ours"):
                extra.append(f"noi abbiamo in piu': {', '.join(drift['only_ours'])}")
            rows.append(result(f"finestra {slug}", "nota",
                               f"{detail}; il catalogo dei metodi diverge ({'; '.join(extra)})",
                               "allinea METHODS in craft-bridge-ui.py a quello che l'app "
                               "dichiara"))
        elif drift.get("checked"):
            rows.append(result(f"finestra {slug}", "ok",
                               f"{detail}; {drift.get('ours')} metodi, gli stessi che "
                               f"dichiara l'app"))
        else:
            rows.append(result(f"finestra {slug}", "nota",
                               f"{detail}; catalogo non confrontabile "
                               f"({drift.get('why')})",
                               "l'app non elenca i metodi quando ne riceve uno "
                               "sconosciuto: la tabella resta la fonte"))
    return rows


def check_bridge_flags(table: dict, timeout: float = 20.0) -> list[dict]:
    """Il flag di aggancio **verificato**, non dichiarato: lo dice l'help di ogni CLI.

    La tabella promette un'opzione per guidare la finestra (`--connect`/`--bridge`), e
    per le app del traduttore promette che quell'opzione **non** c'e'. Sono promesse su
    una interfaccia che non e' la nostra, quindi si chiedono alla CLI stessa: se l'help
    non nomina il flag dichiarato, la tabella sta affermando qualcosa che la CLI non
    conferma, e il guasto si vedrebbe solo alla prima connessione. Una CLI che non da'
    un help non e' un ok: e' una lacuna, e questa riga lo dice.
    """
    report = SHIM.flag_report(table, timeout=timeout)
    total, confirmed = report["total"], len(report["ok"])
    diverging = report["diverging"]
    unreadable = report["unreadable"]
    if diverging:
        detail = "; ".join(f"{r['check']}: {r['detail']}" for r in report["rows"]
                          if r["state"] == "diverge")
        return [result("flag di aggancio", "fail", detail,
                       "allinea il flag nella tabella dello shim a quello che l'help "
                       "della CLI documenta; per vedere la tabella: "
                       "`python craft-bridge-mcp.py --flags`")]
    if unreadable:
        return [result("flag di aggancio", "nota",
                       f"{confirmed}/{total} confermati dall'help della CLI; "
                       f"non leggibile per {', '.join(unreadable)}: li' il flag resta "
                       f"una dichiarazione della tabella",
                       "lancia la CLI di quelle app con --help: se non lo stampa, la "
                       "tabella e' l'unica fonte")]
    return [result("flag di aggancio", "ok",
                   f"{confirmed}/{total} app: l'help della CLI documenta il flag che la "
                   f"tabella usa (11 agganci, 1 per traduzione)")]


def check_published(table: dict, feed_dir: Path, file_facts: dict | None = None) -> list[dict]:
    """La build installata contro quella che il fornitore ha **pubblicato**.

    La versione di un eseguibile dice cosa dichiara di essere, non se e' la release
    che il launcher distribuisce: sono due domande diverse, e finora il ponte ne
    sapeva porre solo la prima. Il feed del launcher (`craft-bridge-feed.py`) porta
    la seconda, con il repository di provenienza e lo sha256 dei pacchetti.

    Un launcher assente **non** e' un guasto: senza feed non c'e' un termine di
    paragone, e il ponte funziona lo stesso. Un'app indietro e' una nota, non un
    guasto del ponte: si aggiorna dal launcher.
    """
    if FEED is None:
        return [result("pubblicato", "nota", f"nessun confronto: manca lo strumento che "
                                                    f"legge il feed ({FEED_WHY})", "")]
    try:
        feed = FEED.load(feed_dir)
    except FEED.FeedError as exc:
        return [result("pubblicato", "nota", f"nessun confronto: {exc}", "")]
    facts = file_facts if file_facts is not None else \
        IDENT.file_versions([str(IDENT.configured_exe(s["cli"])) for s in table.values()])
    installed = {slug: {"version": build.get("version"), "source": build.get("source")}
                 for slug, spec in table.items()
                 for build in [IDENT.configured_build(slug, spec["cli"], file_facts=facts)]}
    rows = FEED.rows(table, feed, installed)
    behind = [r for r in rows if r.get("kind") == "behind"]
    ahead = [r for r in rows if r.get("kind") == "ahead"]
    unknown = [r for r in rows if r.get("kind") == "unknown"]
    when = feed.get("fetched_at") or "?"
    if behind or ahead:
        listed = ", ".join(f"{r['check']} {r['detail'].split(' (')[0]}"
                           for r in behind + ahead)
        return [result("pubblicato", "nota",
                       f"il launcher pubblica altro: {listed} (feed del {when})",
                       "aggiorna dal launcher; poi `python craft-bridge-feed.py`")]
    if unknown:
        return [result("pubblicato", "nota",
                       f"versione installata non leggibile per "
                       f"{', '.join(r['check'] for r in unknown)} (feed del {when})",
                       "avvia l'app dalla sua entry una volta")]
    return [result("pubblicato", "ok",
                   f"{len(table)} app allineate alla release pubblicata (feed del {when})")]


def check_live(table: dict, entries: dict, file_facts: dict | None = None) -> list[dict]:
    """Chi c'e' davvero sulle porte: peer, app e build che gira."""
    ports = {slug: int((entries.get(slug) or {}).get("port") or table[slug]["port"])
             for slug in table}
    pids = IDENT.listening_pids(list(ports.values()))
    facts = IDENT.process_facts(sorted(set(pids.values())))
    files = file_facts if file_facts is not None else \
        IDENT.file_versions([str(IDENT.configured_exe(table[s]["cli"])) for s in table])
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
    parser.add_argument("--control-file",
                        default=str(Path.home() / ".craft-bridge" / "pdfcraft-control.json"),
                        help="file di controllo dell'app servita dal traduttore")
    parser.add_argument("--no-live", action="store_true",
                        help="salta le porte: solo repo, shim, config, eseguibili")
    parser.add_argument("--flag-timeout", type=float, default=20.0,
                        help="secondi per l'help di una CLI (default 20)")
    parser.add_argument("--feed-dir", default=str(FEED.default_feed_dir()),
                        help="cartella del feed del launcher (default: quella di questo sistema)")
    parser.add_argument("--apps-file",
                        help="tabella delle app da un file, invece che dallo shim: serve a "
                             "provare la diagnosi su una tabella di prova")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    config_path, install_dir = Path(args.config), Path(args.install_dir)
    try:
        table = CONFIG.apps_table(args.apps_file)
    except SystemExit as exc:
        print(f"tabella delle app illeggibile: {exc}", file=sys.stderr)
        return 3

    rows = check_repo() + check_installed(install_dir)
    try:
        entries = IDENT.shim_entries(config_path)
    except (SystemExit, json.JSONDecodeError):
        entries = {}
    # Le versioni degli eseguibili si leggono una volta sola: ogni giro costa una
    # chiamata a PowerShell, e la chiedono due controlli.
    try:
        exe_facts = IDENT.file_versions([str(IDENT.configured_exe(s["cli"]))
                                        for s in table.values()])
    except (SystemExit, OSError):
        exe_facts = {}
    # La tabella delle app **servite dal ponte**: quelle dello shim piu' quella del
    # traduttore. La usano due controlli: la si legge una volta sola.
    bridge_apps = CONFIG.bridge_table(args.apps_file)
    rows += check_config(config_path, table, install_dir, args.token_file, args.control_file)
    rows += check_apps(table, exe_facts)
    rows += check_locations(table)
    rows += check_bridge_flags(bridge_apps, timeout=args.flag_timeout)
    rows += check_translator(install_dir, args.control_file)
    rows += check_published(bridge_apps, Path(args.feed_dir), exe_facts)
    if not args.no_live:
        rows += check_live(table, entries, exe_facts)

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
