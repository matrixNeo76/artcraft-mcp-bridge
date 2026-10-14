#!/usr/bin/env python3
"""Avvia una o più Crafting Apps col canale di controllo già attivo.

Un solo comando per il passo manuale del §7: aprire le app in **bridged** invece
di doverle lanciare a mano una per una con `--control <porta>`.

Le porte non sono scritte qui: si leggono dalla **config dello shim**
(`~\\.agents\\mcp.json`), cioe' dal valore `--port` che

    craft-bridge-mcp.py --slug <app> --port <porta>

sondera' all'avvio. Cosi' l'app ascolta esattamente dove lo shim guarda, e se un
domani si cambia porta nella config il comando segue senza modifiche. La tabella
delle app arriva dal wrapper stesso (`--dump-apps`), quindi anche i percorsi degli
eseguibili hanno una sola fonte — e quella fonte e' il **sistema**: l'eseguibile da
avviare e' quello che il registro `App Paths` registra per quell'app, cioe' la
stessa voce che Windows usa per aprirla per nome. La tabella scritta a mano resta
come conferma e come ripiego dove il registro non c'e'.

Uso:
    python craft-bridge-launch.py                       # tutte le app config
    python craft-bridge-launch.py --apps gridcraft,lightcraft
    python craft-bridge-launch.py --list                # tabella e stato, non avvia
    python craft-bridge-launch.py --dry-run             # mostra i comandi
    python craft-bridge-launch.py --verify              # pretende lo shim in bridged
    python craft-bridge-launch.py --wait 60 --json

    # porta diversa per una sola app (deve restare allineata alla config)
    python craft-bridge-launch.py --apps gridcraft --port gridcraft=7985

Esito:
    0  ogni app richiesta ha il canale attivo (e verificato, con --verify)
    1  almeno una app non e' a posto: canale assente, oppure porta occupata da altro
    2  errore d'uso (slug sconosciuto, porta duplicata)
    3  config o tabella delle app illeggibili

Cosa prova e cosa no. Una porta in ascolto non dice chi c'e' dietro: la conferma
arriva da due prove. La prima e' la riga che l'app scrive nel suo log quando apre
il canale (`control ... listening on 127.0.0.1:<porta>`), letta **solo** dal log di
questo avvio, perche' un log vecchio confermerebbe un peer estraneo. Se quel log
non c'e' (app gia' aperta da prima), il comando fa l'**handshake** col peer
(`craft-bridge-ident.py`): il canale e' JSON-lines e risponde a un metodo che non
conosce, quindi `peer=craft` prova che parla il protocollo; `silent`/`foreign`
provano il contrario e il comando esce 1 — perche' su un peer muto lo shim
dichiarava bridged e la CLI ripiegava in headless **senza dirlo** (misurato). Dove
c'e' una credenziale (`--token-file`, o la chiave che WordCraft scrive da sola)
l'handshake la usa: `autenticato` significa che il peer non e' solo "un canale
Craft", e' il nostro. `--verify` aggiunge la prova lato client: interroga lo shim
e pretende `modalita' bridged`.

Le app vengono staccate dalla shell (DETACHED_PROCESS): il comando ritorna
appena i canali sono su, le finestre restano aperte.

PdfCraft ha un trasporto diverso e per questo una strada diversa: il suo `--control`
vuole un **file**, non una porta, e la porta la sceglie l'app scrivendola li' dentro.
Si avvia anche lei da qui (l'app e' quella che il sistema registra, il file di
controllo e' quello che cita la sua entry), ma la domanda "e' guidabile adesso?" non
la risponde una porta fissa: la risponde il **traduttore**
(`craft-bridge-ui.py --list`), che autentica col token del file e dice
`bridged` o `headless`. Le app servite dal traduttore si riconoscono dalla entry:
sono quelle che lo nominano.
"""
from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
WRAPPER = HERE / "craft-bridge-mcp.py"
PROBE = HERE / "craft-bridge-probe.py"
IDENT = HERE / "craft-bridge-ident.py"
DEFAULT_CONFIG = Path.home() / ".agents" / "mcp.json"
LOGDIR = Path.home() / ".craft-bridge" / "launch-logs"
SHIM = HERE / "craft-bridge-mcp.py"
TRANSLATOR = "craft-bridge-ui.py"                # le app servite da lui, non dallo shim

# Windows: il processo figlio non eredita la console e sopravvive alla shell.
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200

POLL = 0.5


def app_table() -> dict:
    """Tabella slug -> (CLI, flag, porta default) dal wrapper: una sola fonte."""
    proc = subprocess.run([sys.executable, str(WRAPPER), "--dump-apps"],
                          capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise SystemExit(f"impossibile leggere la tabella delle app: {proc.stderr}")
    return json.loads(proc.stdout)


def shim_entries(config_path: Path, table: dict) -> dict:
    """slug -> entry della config, per le sole entry che passano dallo shim.

    E' da qui che viene la porta: quella che lo shim sondera' davvero. Un'app la
    cui entry e' tornata headless (`<cli> mcp`, senza `--port`) non ha una porta
    attesa, quindi non e' avviabile in modo utile: la si segnala.
    """
    if not config_path.is_file():
        raise SystemExit(f"config assente: {config_path}")
    servers = json.loads(config_path.read_text(encoding="utf-8-sig")).get("mcpServers", {})
    entries = {}
    for slug, entry in servers.items():
        if slug not in table:
            continue
        args = [str(a) for a in (entry.get("args") or [])]
        if not any(Path(a).name == WRAPPER.name for a in args):
            continue  # entry non shimmed (headless puro): nessuna porta attesa
        if "--slug" not in args or "--port" not in args:
            continue
        entries[slug] = {
            "command": str(entry.get("command") or ""),
            "args": args,
            "port": int(args[args.index("--port") + 1]),
            "port_from_config": True,
            "token_file": args[args.index("--token-file") + 1] if "--token-file" in args else None,
            "entry": [str(entry.get("command") or "")] + args,
        }
    return entries


def translated_entries(config_path: Path) -> dict:
    """slug -> entry delle app che passano dal traduttore (non dallo shim).

    Il criterio e' la entry stessa: nomina `craft-bridge-ui.py`. Cosi' l'elenco non e'
    una seconda copia scritta a mano, ma quello che la config fa davvero.
    """
    servers = json.loads(config_path.read_text(encoding="utf-8-sig")).get("mcpServers", {})
    out = {}
    for slug, entry in servers.items():
        args = [str(a) for a in (entry.get("args") or [])]
        script = next((a for a in args if Path(a).name == TRANSLATOR), None)
        if not script:
            continue
        out[slug] = {
            "translator": script,
            "control": args[args.index("--control") + 1] if "--control" in args else None,
            "entry": [str(entry.get("command") or "")] + args,
        }
    return out


def translator_state(item: dict, timeout: float = 90.0) -> dict:
    """Chiede al **traduttore** se la finestra risponde: e' lui che sa la risposta.

    Non si replica qui la domanda (file di controllo, porta, token, autenticazione):
    sarebbe la seconda implementazione della stessa cosa. Il report del traduttore
    contiene il modo, la porta, il pid e il catalogo dei metodi.
    """
    argv = [sys.executable, str(item["translator"]), "--slug", item["slug"],
            "--list", "--json"]
    if item.get("control"):
        argv += ["--control", str(item["control"])]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout)
        return json.loads(proc.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
        return {"mode": "?", "mode_why": f"traduttore non interrogabile: {exc}"}


def control_port(control: str | None) -> int | None:
    """La porta che l'app ha scritto nel file di controllo (o None se non c'e' ancora).

    Serve ad aspettare **poco**: leggere il file e provare la porta costa microsecondi,
    mentre chiedere al traduttore vuol dire un processo CLI ogni volta. Al traduttore si
    chiede una volta sola, quando la porta risponde.
    """
    if not control:
        return None
    try:
        return int(json.loads(Path(control).read_text(encoding="utf-8-sig"))["port"])
    except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError):
        return None


def app_executable(item: dict) -> str:
    """L'eseguibile dell'app, dal **sistema**: lo risolve il traduttore, e lo dice lui.

    Chiedere a lui evita due cose: una seconda copia della logica del registro, e un
    percorso scritto a mano che invecchia in silenzio (l'app sta dove l'installer l'ha
    registrata, non dove ce la ricordiamo).
    """
    proc = subprocess.run([sys.executable, str(item["translator"]), "--slug", item["slug"],
                           "--where", "--json"], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=60)
    try:
        cli = str(json.loads(proc.stdout)["cli"])
    except (json.JSONDecodeError, KeyError, OSError, TypeError):
        return ""
    return str(Path(cli).with_name(Path(cli).name.replace("-cli.exe", ".exe")))


def port_open(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


def process_running(name: str) -> bool:
    """L'app e' gia' aperta? (senza il canale, un secondo avvio non lo apre)."""
    try:
        out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {name}", "/NH"],
                             capture_output=True, text=True, timeout=20)
        return name.lower() in (out.stdout or "").lower()
    except (OSError, subprocess.SubprocessError):
        return False


def listening_line(log: Path, port: int) -> str:
    """La riga con cui l'app annuncia il canale, se la scrive nel log."""
    try:
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    hits = [l.strip() for l in lines
            if "listening" in l.lower() and ("control" in l.lower() or "channel" in l.lower())]
    return next((l for l in hits if str(port) in l), hits[-1] if hits else "")[:220]


def ascii_safe(text: str) -> str:
    """Il testo che arriva dalle app puo' avere byte fuori dalla tabella della console.

    Senza questo, una riga di log con un trattino tipografico fa uscire dal comando
    byte cp1252 e chi legge stdout come UTF-8 riceve un errore di decodifica.
    """
    return text.encode("ascii", "replace").decode("ascii")


def tail_lines(log: Path, count: int) -> list[str]:
    """Ultime righe utili del log dell'app: e' li' che sta il motivo del fallimento."""
    try:
        lines = [l.strip() for l in log.read_text(encoding="utf-8", errors="replace").splitlines()]
    except OSError:
        return []
    return [l for l in lines if l][-count:]


def app_exe_of(spec: dict) -> Path:
    """L'eseguibile dell'app da avviare: quello che **il sistema** registra.

    La tabella dichiara la CLI; dove sta l'app lo dice l'installer (le app sono
    pacchetti MSI per macchina, e la voce `App Paths` e' quella che Windows usa per
    aprirle per nome). Derivare il nome con una sostituzione di stringa era la
    seconda copia della stessa informazione: se il registro dice dove sta l'app, si
    avvia quella. La derivazione resta solo come ripiego per un sistema senza
    registro, dove l'unica fonte e' la tabella.
    """
    registered = spec.get("app_exe")
    if registered:
        return Path(str(registered))
    return Path(str(spec["cli"]).replace("-cli.exe", ".exe"))


def plan_app(slug: str, spec: dict, entry: dict, overrides: dict,
             logdir: Path) -> dict:
    app_exe = app_exe_of(spec)
    port = int(overrides.get(slug, entry["port"]))
    launch = [str(app_exe), "--control", str(port)]
    token_file = entry["token_file"] or str(Path.home() / ".craft-bridge" / f"{slug}.token")
    if spec.get("needs_token") or entry.get("token_file"):
        # L'app e lo shim devono leggere lo **stesso** file: se divergono, il
        # bridge autentica male. Il file lo scrive l'app se non esiste.
        launch += ["--control-token-file", token_file]
    return {
        "slug": slug,
        "app": str(app_exe),
        "app_source": str(spec.get("cli_source") or "tabella"),
        "port": port,
        "port_matches_config": port == entry["port"],
        "config_port": entry["port"],
        "entry_from_config": bool(entry.get("port_from_config")),
        "launch": launch,
        "log": logdir / f"{slug}.log",
        "entry": entry["entry"],
        "needs_token": bool(spec.get("needs_token")),
        "token_file": token_file if (spec.get("needs_token") or entry.get("token_file")) else None,
    }


def spawn(item: dict) -> int:
    item["log"].parent.mkdir(parents=True, exist_ok=True)
    with item["log"].open("w", encoding="utf-8", errors="replace") as fh:
        child = subprocess.Popen(
            item["launch"],
            stdin=subprocess.DEVNULL,
            stdout=fh,
            stderr=subprocess.STDOUT,
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
        )
    return child.pid


def identify(port: int, timeout: float, slug: str | None = None,
             token_file: str | None = None, record: bool = False) -> dict:
    """Chiede al peer dietro la porta **chi e'**: e' cosi' che si distingue un canale
    vero da qualcosa che si limita ad ascoltare (vedi craft-bridge-ident.py).

    Una porta aperta non e' una prova: con un peer muto lo shim diceva bridged e la
    CLI ripiegava in headless senza dirlo. L'handshake lo rende impossibile. Lo stesso
    comando dice anche **quale build** gira su quella porta: il catalogo identifica
    l'app, non la versione, quindi due build della stessa app si assomigliano finche'
    non si guarda la versione dell'eseguibile in ascolto.
    """
    cmd = [sys.executable, str(IDENT), "--port", str(port), "--timeout", str(timeout),
           "--json"]
    if slug:
        cmd += ["--slug", slug]
    if token_file and Path(token_file).is_file():
        cmd += ["--token-file", token_file]
    if record:
        cmd.append("--record")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout * 4 + 20)
        report = json.loads(proc.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
        return {"peer": "sconosciuto", "error": f"identificazione non eseguita: {exc}"}
    return next(iter(report.get("checks", {}).values()), {"peer": "sconosciuto"})


def probe_shim(entry: list[str], timeout: float) -> dict:
    """Interroga lo shim **esattamente come fara' l'agente** e legge il modo."""
    cmd = [sys.executable, str(PROBE), "--cmd", entry[0], "--timeout", str(timeout)]
    for a in entry[1:]:
        cmd.append(f"--args={a}")
    cmd.append("--json")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              timeout=timeout + 60)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"la sonda non ha risposto entro {timeout + 60}s"}
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": "uscita non JSON", "raw": proc.stdout[-400:]}
    text = (result.get("stderr") or "").lower()
    result["mode"] = ("bridged" if "modalita' bridged" in text
                      else "headless" if "modalita' headless" in text else "?")
    result["ok"] = bool(result.get("ok")) and result["mode"] == "bridged"
    return result


def main() -> int:
    # La console di Windows e' cp1252: un carattere fuori tabella non deve far
    # cadere il comando a fine lavoro (successo stampato, poi traceback ed exit 1).
    # Uscita in UTF-8, cosi' chi legge stdout (una pipe, un altro script) non trova
    # byte cp1252 in mezzo e non riceve un errore di decodifica.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--apps", help="slug separati da virgola (default: tutte le app config)")
    parser.add_argument("--port", action="append", default=[], help="slug=porta (ripetibile)")
    parser.add_argument("--wait", type=int, default=45, help="secondi di attesa per canale")
    parser.add_argument("--list", action="store_true", help="tabella e stato, non avvia")
    parser.add_argument("--dry-run", action="store_true", help="mostra i comandi, non avvia")
    parser.add_argument("--verify", action="store_true",
                        help="dopo l'avvio pretende che lo shim risponda in bridged")
    parser.add_argument("--ident-timeout", type=float, default=3.0,
                        help="secondi per l'handshake con il peer")
    parser.add_argument("--record-builds", action="store_true",
                        help="registra la build verificata di ogni app (come ident --record)")
    parser.add_argument("--json", action="store_true", help="report JSON")
    args = parser.parse_args()

    table = app_table()
    try:
        entries = shim_entries(Path(args.config), table)
        translated = translated_entries(Path(args.config))
    except (SystemExit, json.JSONDecodeError) as exc:
        print(f"config illeggibile: {exc}", file=sys.stderr)
        return 3
    for slug, item in translated.items():
        item["slug"] = slug

    overrides = {}
    for item in args.port:
        if "=" not in item:
            print(f"--port vuole slug=porta, ricevuto: {item}", file=sys.stderr)
            return 2
        slug, port = item.split("=", 1)
        if slug in translated:
            print(f"{slug} non ha una porta da impostare: la sceglie l'app e la scrive "
                  f"nel file di controllo ({translated[slug].get('control')})", file=sys.stderr)
            return 2
        if slug not in table:
            print(f"slug sconosciuto in --port: {slug}", file=sys.stderr)
            return 2
        overrides[slug] = int(port)

    if args.list:
        rows = []
        for slug, item in sorted(translated.items()):
            state = translator_state(item)
            rows.append({
                "slug": slug, "transport": "traduttore", "mode": state.get("mode"),
                "port": state.get("port"), "pid": state.get("pid"),
                "mode_why": state.get("mode_why"),
                "app": str(app_executable(item)),
                "app_running": process_running(Path(str(app_executable(item))).name),
            })
        for slug, spec in sorted(table.items()):
            entry = entries.get(slug)
            port = int(overrides.get(slug, (entry or {}).get("port", spec["port"])))
            rows.append({
                "slug": slug, "port": port, "bridged_in_config": entry is not None,
                "channel": port_open(port),
                "app": str(app_exe_of(spec)),
                "app_source": str(spec.get("cli_source") or "tabella"),
                "app_running": process_running(app_exe_of(spec).name),
            })
        if args.json:
            print(json.dumps(rows, indent=2))
        else:
            translated_rows = [x for x in rows if x.get("transport") == "traduttore"]
            if translated_rows:
                # Intestazione propria: le colonne non sono quelle della tabella shim
                # (qui la porta la sceglie l'app, e il modo lo dice il traduttore).
                print(f"{'slug':<12}{'porta':>6}  {'trasporto':<11}{'modo':<10}"
                      "app aperta  perche'")
                for r in translated_rows:
                    print(f"{r['slug']:<12}{str(r.get('port') or '-'):>6}  {'traduttore':<11}"
                          f"{str(r.get('mode') or '?'):<10}"
                          f"{'si' if r['app_running'] else 'no':<12}{r.get('mode_why') or ''}")
            shim_rows = [x for x in rows if x.get("transport") != "traduttore"]
            if shim_rows:
                print(f"{'slug':<12}{'porta':>6}  {'entry shim':<11}{'canale':<10}"
                      "app aperta  percorso")
                for r in shim_rows:
                    print(f"{r['slug']:<12}{r['port']:>6}  "
                          f"{'si' if r['bridged_in_config'] else 'NO':<11}"
                          f"{'in ascolto' if r['channel'] else 'chiusa':<10}"
                          f"{'si' if r['app_running'] else 'no':<12}{r['app_source']}")
                print("(per sapere *chi* ascolta: craft-bridge-ident.py --all)")
        return 0

    known = sorted(set(table) | set(translated))
    if args.apps:
        asked = [s.strip() for s in args.apps.split(",") if s.strip()]
    else:
        asked = sorted(set(entries) | set(translated))
    unknown = [s for s in asked if s not in known]
    if unknown:
        print(f"slug sconosciuto: {', '.join(unknown)} (noti: {', '.join(known)})",
              file=sys.stderr)
        return 2
    wanted = [s for s in asked if s in table]
    wanted_t = [s for s in asked if s in translated]

    logdir = LOGDIR
    missing_entry = [s for s in wanted if s not in entries]
    if missing_entry:
        # Senza entry shim non c'e' una porta attesa: si usa il default della tabella,
        # dichiarandolo, perche' a sondarla non ci sarebbe comunque nessuno.
        print(f"[!] senza entry shim in config: {', '.join(missing_entry)} - uso la porta "
              f"default della tabella; per allinearle: craft-bridge-config.py --apply",
              file=sys.stderr)

    plan = [plan_app(slug, table[slug], entries.get(slug) or {"port": table[slug]["port"],
                 "port_from_config": False, "token_file": None,
                 "entry": [sys.executable, str(WRAPPER), "--slug", slug,
                           "--port", str(table[slug]["port"])]},
                 overrides, logdir)
            for slug in wanted]

    seen: dict[int, str] = {}
    for item in plan:
        if item["port"] in seen:
            print(f"porta duplicata {item['port']}: {seen[item['port']]} e {item['slug']} - "
                  f"due app non possono condividere un canale", file=sys.stderr)
            return 2
        seen[item["port"]] = item["slug"]
        if not item["port_matches_config"]:
            # Una porta diversa da quella in config rende l'app sorda allo shim:
            # il canale ci sarebbe, ma nessuno lo interrogherebbe.
            print(f"[!] {item['slug']}: porta {item['port']} diversa da quella in config "
                  f"({item['config_port']}): lo shim cerchera' quest'ultima", file=sys.stderr)

    # 1) Avvia solo cio' che manca: se il canale e' gia' su, l'app e' gia' bridged.
    for item in plan:
        item["already"] = port_open(item["port"])
        item["exe_ok"] = Path(item["app"]).is_file()
        item["running_before"] = process_running(Path(item["app"]).name)
        if item["already"] or args.dry_run:
            item["pid"] = None
            if not item["already"] and not args.json:
                print(f"=== {item['slug']} (porta {item['port']}) ===\n"
                      f"  avvio      : {' '.join(item['launch'])}\n"
                      f"  app        : da {item['app_source']}")
            continue
        if not item["exe_ok"]:
            item["pid"] = None
            item["error"] = f"eseguibile assente: {item['app']}"
            continue
        item["pid"] = spawn(item)
        if not args.json:
            print(f"=== {item['slug']} (porta {item['port']}) ===\n"
                  f"  avvio      : {' '.join(item['launch'])}\n"
                  f"  pid        : {item['pid']}  | log: {item['log']}")

    # 1b) Le app del traduttore: un altro trasporto, quindi un altro piano.
    plan_t: list[dict] = []
    for slug in wanted_t:
        item = dict(translated[slug])
        item["slug"] = slug
        item["transport"] = "traduttore"
        item["app"] = app_executable(item)
        item["log"] = logdir / f"{slug}.log"
        item["launch"] = [item["app"], "--control", str(item["control"])]
        state = translator_state(item)
        item["mode_before"] = state.get("mode")
        item["already"] = state.get("mode") == "bridged"
        item["exe_ok"] = bool(item["app"]) and Path(item["app"]).is_file()
        item["port"] = state.get("port")
        plan_t.append(item)
        if item["already"] or args.dry_run:
            item["pid"] = None
            if not args.json:
                print(f"=== {item['slug']} (traduttore) ===\n"
                      f"  avvio      : {' '.join(item['launch'])}\n"
                      f"  stato      : {state.get('mode')} ({state.get('mode_why')})")
            continue
        if not item["exe_ok"]:
            item["pid"] = None
            item["error"] = f"eseguibile assente: {item['app']}"
            continue
        item["pid"] = spawn(item)
        if not args.json:
            print(f"=== {item['slug']} (traduttore) ===\n"
                  f"  avvio      : {' '.join(item['launch'])}\n"
                  f"  pid        : {item['pid']}  | log: {item['log']}")

    if args.dry_run:
        print(f"\n(dry-run: {len(plan) + len(plan_t)} app, nessuna avviata)")
        return 0

    # 2) Attesa unica, in parallelo: le app partono insieme, non in fila.
    deadline = time.time() + args.wait
    pending = [i for i in plan if not i["already"]]
    while pending and time.time() < deadline:
        pending = [i for i in pending if not port_open(i["port"])]
        if pending:
            time.sleep(POLL)
    for item in plan:
        item["channel"] = item["already"] or port_open(item["port"])
        # La riga si legge solo dal log di **questo** avvio (che viene troncato prima
        # di partire): un log vecchio confermerebbe un peer estraneo che occupa la porta.
        fresh = bool(item.get("pid"))
        item["channel_log"] = listening_line(item["log"], item["port"]) if (item["channel"] and fresh) else ""

    # La riga di log puo' arrivare un istante dopo il listen(): le si da' un margine
    # (con 12 app avviate insieme il log e' piu' lento della porta).
    log_deadline = time.time() + 3.0
    while time.time() < log_deadline:
        waiting = [i for i in plan if i["channel"] and i.get("pid") and not i["channel_log"]]
        if not waiting:
            break
        time.sleep(0.3)
        for item in waiting:
            item["channel_log"] = listening_line(item["log"], item["port"])

    # 3) Chi c'e' dietro la porta (handshake), poi la prova end-to-end dello shim.
    for item in plan:
        if item["channel"]:
            item["ident"] = identify(item["port"], timeout=args.ident_timeout,
                                     slug=item["slug"], token_file=item.get("token_file"),
                                     record=args.record_builds)
    if args.verify:
        for item in plan:
            if item["channel"]:
                item["verify"] = probe_shim(item["entry"], timeout=min(args.wait, 60))

    active = 0
    for item in plan:
        item.pop("entry", None)
        v = item.get("verify")
        # `confirmed` = l'app dice lei di aver aperto il canale (riga nel suo log).
        # Una porta aperta non lo prova: puo' essere occupata da altro, e con un
        # peer muto la CLI risponde in headless **senza dirlo** (misurato: 25 tool,
        # nessun errore). Il check dello shim e' un'altra cosa, e resta a parte.
        ident = item.get("ident")
        # La conferma viene da una prova: la riga di log dell'app (se l'abbiamo
        # avviata noi) oppure l'handshake, che dice se il peer parla il protocollo.
        item["confirmed"] = bool(item.get("channel_log")) or bool(ident and ident.get("peer") == "craft")
        item["foreign"] = bool(item["channel"]) and ident is not None and ident.get("peer") != "craft"
        # Una credenziale rifiutata non e' un canale utilizzabile, anche se il peer e'
        # quello giusto: la config ha un token diverso da quello dell'app.
        item["auth_rejected"] = bool(ident) and ident.get("authenticated") is False
        # Un peer che parla il protocollo ma non ha i comandi di questa app e' l'app
        # sbagliata: la CLI ripiegherebbe in headless senza dirlo (misurato), quindi
        # non e' un successo nemmeno se la porta risponde.
        item["wrong_app"] = bool(ident) and ident.get("identity") == "mismatch"
        # Stessa app ma **altra build**: il catalogo non lo distingue (copertura 1.0),
        # quindi senza questo confronto la porta sembra a posto mentre l'eseguibile in
        # ascolto non e' quello che l'entry avvierebbe. Il canale resta utilizzabile
        # (lo shim procede bridged), ma la config non e' quella verificata.
        item["build_drift"] = bool(ident) and ident.get("build") == "different"
        item["active"] = (bool(item["channel"]) and not item["foreign"]
                          and not item["auth_rejected"] and not item["wrong_app"]
                          and (v is None or bool(v.get("ok"))))
        item["state"] = "attivo" if item["active"] else "assente"
        if item["active"]:
            active += 1
        if args.json:
            continue
        if item.get("error"):
            print(f"=== {item['slug']} (porta {item['port']}) ===\n  esito      : {item['error']}")
            continue
        if item["foreign"]:
            label = f"occupata da altro (handshake: {ident.get('peer')})"
        elif not item["channel"]:
            label = "NON attivo"
        elif item["confirmed"]:
            label = "attivo"
        elif item.get("already"):
            label = "attivo (era gia' su, nessuna conferma fresca)"
        else:
            label = "attivo, nessuna conferma nel log"
        detail = f" | {ascii_safe(item['channel_log'])}" if item["channel_log"] else ""
        print(f"  canale     : {label}{detail}")
        if ident is not None:
            auth = ("autenticato" if ident.get("authenticated") else
                    "auth rifiutata" if ident.get("authenticated") is False else "senza credenziale")
            who = (f" | app={ident.get('app')} (copertura {ident.get('coverage')})"
                   f" | cli {ident.get('version') or '?'}" if ident.get("app") else
                   f" | app non identificata ({ident.get('identity_why')})")
            print(f"  handshake  : peer={ident.get('peer')} ({auth}){who}"
                  + (f" | {ascii_safe(str(ident.get('error')))[:110]}" if ident.get("error") else ""))
            running = ident.get("build_running") or {}
            configured = ident.get("build_configured") or {}
            if ident.get("build") == "same":
                print(f"  build      : {running.get('version')} in esecuzione = config "
                      f"({configured.get('source')}, {running.get('exe') or '?'})"
                      + (" | registrata" if ident.get("recorded") else ""))
            elif ident.get("build") == "different":
                print(f"  build      : NON e' quella configurata: gira {running.get('version')}"
                      f" ({running.get('exe') or '?'}) invece di {configured.get('version')}"
                      f" ({configured.get('source')})")
            elif ident.get("build") is not None:
                print(f"  build      : non verificabile ({ident.get('build_why')})")
        if v is not None:
            shim = ascii_safe(str(v.get("error") or v.get("raw") or ""))[:120]
            print(f"  shim       : modo={v.get('mode')} tool={v.get('tool_count')} "
                  f"{'OK' if v.get('ok') else 'KO ' + shim}")
        if item.get("wrong_app"):
            print(f"  diagnosi   : sulla porta risponde un'altra app "
                  f"({ident.get('app')}, copertura {ident.get('coverage')}): il canale e' di "
                  f"un'app, ma non di {item['slug']}. Lo shim la riconosce e va headless; "
                  "controlla che non ci siano due app sulla stessa porta.")
        elif item.get("build_drift"):
            print(f"  diagnosi   : sulla porta c'e' **la stessa app ma un'altra build**: "
                  f"il catalogo coincide (copertura {ident.get('coverage')}), l'eseguibile no "
                  f"({ident.get('build_running', {}).get('exe')}). Lo shim procede bridged e "
                  "avvisa, ma questa non e' la build con cui la config e' stata verificata: "
                  "chiudi l'istanza e riapri l'app dall'entry, o allinea l'eseguibile.")
        elif item.get("auth_rejected"):
            print(f"  diagnosi   : l'app ha rifiutato la credenziale: il token in config "
                  f"({Path(item.get('token_file') or '').name or 'nessuno'}) non e' quello con cui "
                  "e' avviata. Allinea i due file e riprova.")
        elif item["foreign"]:
            print(f"  diagnosi   : sulla porta non risponde il canale di {item['slug']} "
                  f"(handshake: {ident.get('peer')}). Un peer muto faceva dichiarare bridged "
                  "allo shim, e la CLI ripiegava in headless **senza dirlo** (misurato: 25 "
                  "tool, nessun errore). Ora lo shim va headless e questo comando esce 1.")
        elif not item["active"]:
            if item["channel"] and v is not None:
                print("  diagnosi   : la porta risponde ma lo shim non arriva in bridged: "
                      "l'app ha rifiutato la connessione (token/versione/istanza). "
                      "Rilancia senza --verify per il dettaglio, o guarda la coda del log.")
            else:
                print("  diagnosi   : canale assente dopo l'attesa; la causa sta in coda al log"
                      + (" (l'app era gia' aperta prima del comando: una seconda istanza puo' "
                         "non aprire il canale, chiudila e riprova)"
                         if item["running_before"] else ""))
                for line in tail_lines(item["log"], 4):
                    print(f"    | {ascii_safe(line)[:200]}")
        elif not item["confirmed"]:
            if item.get("already"):
                print("  nota       : il canale era gia' su (lo ha aperto un avvio precedente, non "
                      "questo), quindi non ho una riga di log fresca che lo confermi; con --verify "
                      "si interroga lo shim in bridged")
            else:
                print("  nota       : l'app non annuncia l'ascolto nel suo log, quindi la porta da "
                      "sola non dice chi ascolta; con --verify si interroga lo shim in bridged")

    # 4) Le app del traduttore: si aspetta la porta **scritta nel file**, poi si chiede
    # al traduttore la conferma (autenticata): la porta da sola non dice chi risponde.
    active_t = 0
    for item in plan_t:
        if not item.get("already") and not item.get("error"):
            deadline_t = time.time() + args.wait
            port = control_port(item.get("control"))
            while time.time() < deadline_t and not (port and port_open(port)):
                time.sleep(POLL)
                port = control_port(item.get("control"))
            item["wait_port"] = port
        state = translator_state(item) if not item.get("error") else {"mode": "?"}
        item["mode_after"] = state.get("mode")
        item["mode_why"] = state.get("mode_why")
        item["port"] = state.get("port") or item.get("port")
        item["pid_remote"] = state.get("pid")
        item["window"] = state.get("window")
        item["drift"] = state.get("drift")
        item["active"] = item["mode_after"] == "bridged"
        if item["active"]:
            active_t += 1
        if args.json:
            continue
        if item.get("error"):
            print(f"  esito      : {item['error']}")
            continue
        print(f"  canale     : {'attivo' if item['active'] else 'NON attivo'}"
              f" (traduttore: {item['mode_after']}, porta {item.get('port')})")
        if item.get("window"):
            w = item["window"]
            print(f"  finestra   : {w.get('width')}x{w.get('height')} punti (pid {item['pid_remote']})")
        drift_t = item.get("drift") or {}
        if drift_t.get("checked"):
            print(f"  catalogo   : {drift_t.get('ours')} metodi"
                  + (" , gli stessi che dichiara l'app" if drift_t.get("same")
                     else f" , l'app ne dichiara {drift_t.get('theirs')}"))
        if not item["active"]:
            print(f"  diagnosi   : la finestra non risponde ({item.get('mode_why')}); "
                  f"l'entry resta valida e va headless. La causa sta in coda al log:")
            for line in tail_lines(item["log"], 4):
                print(f"    | {ascii_safe(line)[:200]}")

    report = {
        "config": str(Path(args.config)),
        "requested": asked,
        "active": active + active_t,
        "apps": {**{i["slug"]: {k: (str(v) if isinstance(v, Path) else v)
                                 for k, v in i.items() if k != "entry"} for i in plan},
                 **{i["slug"]: {k: (str(v) if isinstance(v, Path) else v)
                                for k, v in i.items() if k != "entry"} for i in plan_t}},
        "ok": (active + active_t) == (len(plan) + len(plan_t)),
    }
    total = len(plan) + len(plan_t)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        drift = [i["slug"] for i in plan if i.get("build_drift")]
        print(f"\n{active + active_t}/{total} app col canale di controllo attivo"
              f"{' (in bridged verificato)' if args.verify else ''}"
              + (f" · {len(drift)} con un'altra build ({', '.join(drift)})" if drift else ""))
        print("in Freebuff: Connectors -> Refresh, poi usa l'app normalmente")
        if not args.verify and any(i["channel"] and not i["confirmed"] for i in plan):
            print("riprova con --verify per la prova end-to-end attraverso lo shim")
    return 0 if (active + active_t) == total and not any(i.get("build_drift")
                                                        for i in plan) else 1


if __name__ == "__main__":
    sys.exit(main())
