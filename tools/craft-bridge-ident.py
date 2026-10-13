#!/usr/bin/env python3
"""Chi risponde sulla porta di controllo? Identifica il peer, non solo la porta.

Il buco che questo chiude (misurato il 13 ott): la modalita' **bridged** dello
shim si decideva con una `connect()` TCP. Se sulla porta rispondeva qualcosa che
*accetta la connessione e poi tace*, lo shim dichiarava bridged e alcune CLI
(DeckCraft) proseguivano in **headless senza dirlo** — 25 tool, nessun errore:
indistinguibile da una finestra guidata. Una porta in ascolto non dice chi c'e'
dietro.

Il protocollo di controllo e' JSON-lines, e ogni app della famiglia risponde a
**qualsiasi** richiesta ben formata, anche a un metodo che non conosce:

    -> {"id":1,"method":"__craft_bridge_ident__","params":{}}
    <- {"error":"unknown method `__craft_bridge_ident__`","id":1,"ok":false}

Quel `id` ripetuto e la forma `ok`/`error`/`result` sono la firma del peer. Un
processo estraneo o muto non risponde niente; qualcos'altro (HTTP, un altro
protocollo) risponde con byte che non sono quella firma. Ecco la differenza fra
«la porta e' occupata» e «l'app e' li'»:

    peer=craft     l'app ha risposto al protocollo
    peer=silent    nessun byte entro il timeout
    peer=foreign   ha risposto, ma non con la firma del canale
    peer=unreachable  connessione rifiutata / host irraggiungibile

Per le due app che verificano una credenziale, con `--token-file` si aggiunge un
secondo, piu' forte passo: `auth` con quel token. Se l'app risponde `ok`, il peer
non e' solo "un canale Craft", e' **il nostro** canale. Il valore del token non
viene mai stampato.

**Quale build.** Il catalogo dice *quale app*, non *quale versione*: due build
diverse della stessa app hanno lo stesso nome sui comandi e coprono lo stesso
catalogo, quindi l'app risulta giusta anche quando sulla porta c'e' un'altra
versione. Qui si guarda anche **chi esegue** quella porta: il PID in ascolto, il
suo eseguibile e la versione di quell'eseguibile, piu' la versione che il processo
stesso ha stampato avviandosi (`<slug>: <Nome> 0.6.1 (00c7613f…)` nel proprio log,
legata a quella porta dalla riga `listening on …`). Il confronto e' con la build
di riferimento, in quest'ordine: `--expect-version`, l'impronta registrata
(`~/.craft-bridge/builds.json`, scritta da `--record`), l'eseguibile accanto alla
CLI di config. Divergenza -> `build=different`, stampata e contata come guasto.

Uso:
    python craft-bridge-ident.py --port 7975
    python craft-bridge-ident.py --slug photocraft --token-file ~/.craft-bridge/photocraft.token
    python craft-bridge-ident.py --all --json           # ogni app della config
    python craft-bridge-ident.py --all --wait 30        # aspetta che l'app risponda
    python craft-bridge-ident.py --all --record         # registra la build verificata
    python craft-bridge-ident.py --port 7975 --build-only   # solo la build, senza handshake
    python craft-bridge-ident.py --port 7975 --expect-version 0.6.1

Esito:
    0  ogni porta richiesta ha un peer Craft (autenticato, dove serve un token)
       e la build attesa
    1  almeno una no (silent, foreign, unreachable, auth rifiutata, o build diversa)
    2  errore d'uso
    3  config/tabella illeggibili
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
WRAPPER = HERE / "craft-bridge-mcp.py"
DEFAULT_CONFIG = Path.home() / ".agents" / "mcp.json"

# Deliberatamente inesistente: la risposta attesa e' proprio l'errore "unknown
# method", che prova che il peer parla il protocollo senza dipendere da un metodo
# che ogni app dovrebbe avere.
IDENT_METHOD = "__craft_bridge_ident__"


def shim_entries(config_path: Path) -> dict:
    """slug -> porta e file del token, per le entry che passano dallo shim."""
    if not config_path.is_file():
        raise SystemExit(f"config assente: {config_path}")
    servers = json.loads(config_path.read_text(encoding="utf-8-sig")).get("mcpServers", {})
    entries = {}
    for slug, entry in servers.items():
        args = [str(a) for a in (entry.get("args") or [])]
        if not any(Path(a).name == WRAPPER.name for a in args):
            continue
        if "--port" not in args:
            continue
        entries[slug] = {
            "port": int(args[args.index("--port") + 1]),
            "token_file": args[args.index("--token-file") + 1] if "--token-file" in args else None,
        }
    return entries


def app_table() -> dict:
    proc = subprocess.run([sys.executable, str(WRAPPER), "--dump-apps"],
                          capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise SystemExit(f"tabella delle app illeggibile: {proc.stderr}")
    return json.loads(proc.stdout)


def _exchange(sock: socket.socket, request: dict, timeout: float) -> bytes:
    """Invia una richiesta e raccoglie la risposta, fino a quando e' JSON completo.

    La fine del messaggio si riconosce **parsando**, non cercando un `\\n`: le app
    lasciano un a capo isolato dopo la risposta precedente, e fermarsi al primo a
    capo significa leggere un byte vuoto al posto di un catalogo di 47 KB (misurato).

    Un errore di rete non solleva: si torna quello che si e' letto (di solito niente).
    **Un peer che chiude la connessione e' un verdetto, non un'eccezione** — misurato:
    con un token sbagliato l'app chiude la connessione dopo il rifiuto, e la
    `sendall` successiva alzava `ConnectionAbortedError`, facendo morire lo strumento
    con un traceback e **nessun verdetto** (uscita 1, stdout vuoto).
    """
    deadline = time.time() + timeout
    buffer = b""
    try:
        sock.sendall(json.dumps(request).encode() + b"\n")
    except OSError:
        return buffer
    while time.time() < deadline:
        try:
            sock.settimeout(max(0.1, min(0.5, deadline - time.time())))
            chunk = sock.recv(1 << 16)
        except socket.timeout:
            continue  # riprova finche' la scadenza lo consente
        except OSError:
            break
        if not chunk:
            break
        buffer += chunk
        try:
            json.loads(buffer.decode("utf-8", "replace"))
        except json.JSONDecodeError:
            continue  # risposta incompleta: continua a leggere
        break
    return buffer


def authenticate(port: int, token: str, token_field: str = "token",
                timeout: float = 3.0, host: str = "127.0.0.1") -> tuple[bool | None, str]:
    """Prova la credenziale su una connessione **sua**, come prima richiesta.

    Su una connessione gia' rifiutata (`authentication required`) l'app puo' non
    ascoltare piu': l'auth va mandata per prima, quindi su un socket nuovo, altrimenti
    un token giusto risulta rifiutato — misurato.
    """
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
    except OSError as exc:
        return None, f"{type(exc).__name__}: {exc}"
    try:
        raw = _exchange(sock, {"id": 1, "method": "auth",
                               "params": {token_field: token}}, timeout)
    finally:
        sock.close()
    if not raw.strip():
        return None, "nessuna risposta ad auth"
    try:
        reply = json.loads(raw.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        return None, "auth: risposta non JSON"
    return bool(isinstance(reply, dict) and reply.get("ok")), \
        str((reply or {}).get("error") or "")[:120]


def identify(port: int, timeout: float = 3.0, token: str | None = None,
             token_field: str = "token", host: str = "127.0.0.1") -> dict:
    """Interroga il peer. Restituisce un verdetto, mai un'eccezione."""
    result: dict = {"host": host, "port": port, "peer": "unreachable", "reply": None,
                    "error": None, "authenticated": None, "token_field": token_field}
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
    except OSError as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result

    try:
        raw = _exchange(sock, {"id": 1, "method": IDENT_METHOD, "params": {}}, timeout)
        result["raw_bytes"] = len(raw)
        if not raw.strip():
            result["peer"] = "silent"
            result["error"] = f"nessun byte entro {timeout}s"
        else:
            text = raw.decode("utf-8", "replace").strip()
            try:
                reply = json.loads(text)
            except json.JSONDecodeError:
                result["peer"] = "foreign"
                result["error"] = "risposta non JSON"
                result["reply_text"] = text[:200]
            else:
                signed = (isinstance(reply, dict) and reply.get("id") == 1
                          and any(k in reply for k in ("ok", "error", "result")))
                result["peer"] = "craft" if signed else "foreign"
                result["reply"] = reply
                if not signed:
                    result["error"] = "JSON senza la firma del canale (id/ok|error|result)"
    finally:
        sock.close()

    if result["peer"] == "craft" and token:
        ok, detail = authenticate(port, token, token_field, timeout, host)
        result["authenticated"] = ok
        if ok is not True:
            result["error"] = f"auth: {detail or 'rifiutata'}"
    return result


def read_token(path: str | None) -> str | None:
    if not path:
        return None
    try:
        return Path(path).read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def wordcraft_key(port: int) -> str | None:
    """WordCraft scrive la chiave da sola: `control-key.local-<porta>`."""
    base = Path.home() / "AppData" / "Roaming" / "WordCraft"
    candidate = base / f"control-key.local-{port}"
    return candidate.read_text(encoding="utf-8").strip() if candidate.is_file() else None


ID_IN_TEXT = re.compile(r"^[A-Za-z][A-Za-z0-9_]*\.[A-Za-z0-9_.]+")


def ids_from_text(text: str) -> set[str]:
    """Id di comando da un catalogo in forma di tabella stampata.

    SoundCraft non ha `commands --json`: stampa una tabella e basta, e senza questa
    lettura la sua identita' restava "non identificata" pur essendo verificabile.
    """
    ids = set()
    for line in text.splitlines():
        head = line.strip().split(None, 1)[0] if line.strip() else ""
        if ID_IN_TEXT.match(head):
            ids.add(head)
    return ids


def cli_catalog(cli: str) -> set[str] | None:
    """Il catalogo dei comandi che il CLI installato dichiara (riferimento locale).

    Non avvia l'app e non tocca il canale: e' il listino statico della stessa
    installazione, quindi dice quali id di comando appartengono a *questa* app.
    """
    for args in (["commands", "--json"], ["commands"]):
        try:
            proc = subprocess.run([cli, *args], capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=60)
        except (OSError, subprocess.SubprocessError):
            return None
        text = (proc.stdout or "").strip()
        if not text:
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None
        if data is not None:
            items = data if isinstance(data, list) else data.get("commands", data)
            if isinstance(items, list):
                ids = {str(i.get("id") or i.get("name")) for i in items if isinstance(i, dict)}
                if ids:
                    return ids
        ids = ids_from_text(text)
        if len(ids) >= 20:  # una tabella vera, non l'uso di un comando
            return ids
    return None


def binary_version(cli: str) -> str:
    """Versione del binario installato: il canale non espone una versione."""
    for args in (["version"], ["--version"]):
        try:
            proc = subprocess.run([cli, *args], capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=30)
        except (OSError, subprocess.SubprocessError):
            return ""
        line = (proc.stdout or "").splitlines()[:1]
        first = line[0].strip() if line else ""
        if first and "usage" not in first.lower() and "unknown" not in first.lower():
            return first[:80]
    return ""


def channel_catalog(port: int, token: str | None, token_field: str,
                    timeout: float, host: str = "127.0.0.1") -> set[str] | None:
    """Gli id di comando che il peer dietro la porta dichiara di avere.

    Il catalogo e' un corpo grosso (100-120 KB misurati): con lo stesso timeout
    snello dell'handshake, sotto carico la risposta non arrivava in tempo e
    l'identita' risultava "sconosciuta" a intermittenza. Per questo qui la scadenza
    e' piu' larga: nel caso normale la risposta arriva in millisecondi.
    """
    bulk = max(timeout, 15.0)
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
    except OSError:
        return None
    try:
        if token:
            _exchange(sock, {"id": 1, "method": "auth", "params": {token_field: token}}, timeout)
        for method in ("app.commands", "engine.commands"):
            raw = _exchange(sock, {"id": 2, "method": method, "params": {}}, bulk)
            try:
                reply = json.loads(raw.decode("utf-8", "replace"))
            except json.JSONDecodeError:
                continue
            result = reply.get("result") if isinstance(reply, dict) else None
            if isinstance(result, list):
                ids = {str(c.get("id")) for c in result if isinstance(c, dict)}
                if ids:
                    return ids
    finally:
        sock.close()
    return None


def name_the_peer(channel: set[str] | None, catalogs: dict[str, set[str]],
                  expected: str | None = None) -> dict:
    """Quale app e' quella che risponde.

    Il canale non dichiara nome ne' versione (nessun metodo lo fa: misurato su 40
    nomi candidati). Dichiara per\u00f2 il proprio catalogo di comandi, che e' specifico
    dell'app: coprendo il catalogo locale di un'app si identifica il peer. Le
    coperture fra app diverse stanno sotto 0.15, quella giusta e' 1.00.
    """
    if not channel:
        return {"app": None, "why": "il canale non ha risposto con un catalogo"}
    scores = {slug: len(ids & channel) / len(ids) for slug, ids in catalogs.items() if ids}
    if expected and expected in scores and scores[expected] >= MATCH:
        return {"app": expected, "coverage": round(scores[expected], 2),
                "second": None, "why": "copertura del catalogo locale"}
    if not scores:
        return {"app": None, "why": "nessun catalogo locale con cui confrontare"}
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best, best_cov = ranked[0]
    second, second_cov = ranked[1] if len(ranked) > 1 else (None, 0.0)
    if best_cov >= MATCH and second_cov <= best_cov / 2:
        return {"app": best, "coverage": round(best_cov, 2),
                "second": round(second_cov, 2), "why": "copertura del catalogo locale"}
    return {"app": None, "coverage": round(best_cov, 2),
            "second": round(second_cov, 2), "why": "nessun catalogo copre il peer"}


MATCH = 0.9

# ---------------------------------------------------------------------------------
# La build: il catalogo dice quale app, non quale versione.
# ---------------------------------------------------------------------------------

BUILDS_FILE = Path.home() / ".craft-bridge" / "builds.json"

# La versione dell'app in esecuzione esiste in due posti soli: la risorsa di versione
# dell'eseguibile da cui il processo e' partito, e la prima riga del log che l'app
# scrive avviandosi (`gridcraft: GridCraft 0.6.1, log file …`; alcune build aggiungono
# la revisione, `cadcraft 0.6.2 (00c7613f…)`). Il canale non ne espone nessuna: su 40
# nomi di metodo candidati nessuno risponde con una versione.
BOOT_RE = r"\[main\]\s+{slug}:\s+[A-Za-z]+\s+(?P<ver>\d+\.\d+\.\d+)(?:\s*\((?P<rev>[0-9a-fA-F]{{7,40}})\))?"


def configured_exe(cli: str) -> Path:
    """L'eseguibile dell'app che la config avvia, accanto alla CLI installata."""
    return Path(cli.replace("-cli.exe", ".exe"))


def _epoch(text: str) -> int | None:
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        return None


def _powershell(script: str, timeout: float = 40.0) -> str:
    """Un giro di PowerShell, in UTF-8. Stringa vuota se non e' disponibile.

    Le informazioni di versione di un eseguibile su Windows si leggono solo cosi'
    (senza dipendenze): un giro costa ~0.5 s, quindi tutto cio' che serve a una
    chiamata viene chiesto in una sola.
    """
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "try{[Console]::OutputEncoding=[Text.Encoding]::UTF8}catch{}; " + script],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return ""
    return (proc.stdout or "").strip()


def listening_pids(ports: list[int]) -> dict[int, int]:
    """porta -> PID del processo che la ascolta, da `netstat -ano`.

    Una porta in ascolto non dice chi la esegue; il PID lo dice, e da li' si arriva
    all'eseguibile. Se la stessa porta compare su piu' indirizzi, `127.0.0.1` batte
    `0.0.0.0` (le app si legano al loopback).
    """
    want = {int(p) for p in ports}
    found: dict[int, tuple[int, int]] = {}
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.SubprocessError):
        return {}
    for line in (out.stdout or "").splitlines():
        cols = line.split()
        if len(cols) < 5 or cols[0].upper() != "TCP" or cols[3].upper() != "LISTENING":
            continue
        host, _, port = cols[1].rpartition(":")
        if not port.isdigit() or int(port) not in want or not cols[4].isdigit():
            continue
        rank = 0 if host == "127.0.0.1" else 1
        if int(port) not in found or rank < found[int(port)][0]:
            found[int(port)] = (rank, int(cols[4]))
    return {port: pid for port, (_, pid) in found.items()}


def process_facts(pids: list[int]) -> dict[int, dict]:
    """Per ogni PID: eseguibile, versione di quel file, avvio, mtime. Un solo giro."""
    pids = [int(p) for p in pids if p]
    if not pids:
        return {}
    ids = ",".join(str(p) for p in pids)
    # Ogni istruzione resta su una riga sola: in PowerShell un accesso a membro non
    # puo' cominciare dopo un'espressione chiusa (`.ToUnixTimeSeconds()` a capo fa
    # fallire il parser, e il comando torna vuoto senza dire perche').
    script = (
        "foreach ($n in @(" + ids + ")) {"
        "$p = Get-Process -Id $n -ErrorAction SilentlyContinue; if (-not $p) { continue };"
        "$f = ''; try { $f = $p.Path } catch {};"
        "$v = ''; $d = ''; $m = ''; $s = '';"
        "if ($f -and (Test-Path -LiteralPath $f)) {"
        "try { $i = (Get-Item -LiteralPath $f).VersionInfo; $v = $i.ProductVersion; $d = $i.FileDescription } catch {};"
        "try { $m = ([int]([DateTimeOffset](Get-Item -LiteralPath $f).LastWriteTime).ToUnixTimeSeconds()).ToString() } catch {} };"
        "try { $s = ([int]([DateTimeOffset]$p.StartTime).ToUnixTimeSeconds()).ToString() } catch {};"
        "\"$n|$f|$v|$d|$s|$m\" }")
    facts: dict[int, dict] = {}
    for line in _powershell(script).splitlines():
        parts = line.split("|")
        if len(parts) == 6 and parts[0].strip().isdigit():
            facts[int(parts[0])] = {"exe": parts[1] or None, "version": parts[2] or None,
                                    "description": parts[3] or None,
                                    "started": _epoch(parts[4]), "mtime": _epoch(parts[5])}
    return facts


def file_versions(paths: list[str]) -> dict[str, dict]:
    """Versione (e mtime) di piu' file, in un solo giro di PowerShell."""
    paths = [p for p in paths if p]
    if not paths:
        return {}
    items = ",".join("'" + p.replace("'", "''") + "'" for p in paths)
    script = (
        "foreach ($f in @(" + items + ")) {"
        "$i = $null; $m = '';"
        "try { $i = (Get-Item -LiteralPath $f).VersionInfo } catch {};"
        "try { $m = ([int]([DateTimeOffset](Get-Item -LiteralPath $f).LastWriteTime).ToUnixTimeSeconds()).ToString() } catch {};"
        "\"$f|$($i.ProductVersion)|$($i.FileDescription)|$m\" }")
    out: dict[str, dict] = {}
    for line in _powershell(script).splitlines():
        parts = line.split("|")
        if len(parts) == 4 and parts[0].strip():
            out[parts[0]] = {"version": parts[1] or None, "description": parts[2] or None,
                             "mtime": _epoch(parts[3])}
    return out


def app_logs(slug: str) -> list[Path]:
    """I log che l'app scrive da sola, sotto %APPDATA%, dal piu' recente.

    Il log e' uno per app ma **ruota**: due istanze della stessa app scrivono in file
    diversi, quindi la dichiarazione di un processo puo' stare in una rotazione.
    """
    base = os.environ.get("APPDATA")
    if not base:
        return []
    found = [p for p in Path(base).glob(f"*/logs/{slug}*.log") if p.is_file()]
    return sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)


def claimed_build(slug: str, port: int) -> dict | None:
    """Versione (e revisione) che il processo **su quella porta** dichiara di essere.

    La riga di avvio vale per questa porta solo perche' la segue, nello stesso file,
    la riga `listening on …:<porta>`: e' quello che lega la dichiarazione a *questo*
    processo invece che a un avvio precedente.
    """
    boot = re.compile(BOOT_RE.format(slug=re.escape(slug))) if slug else None
    if boot is None:
        return None
    for log in app_logs(slug):
        try:
            lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        opened = [i for i, l in enumerate(lines)
                  if "listening" in l.lower() and f":{port}" in l
                  and ("control" in l.lower() or "channel" in l.lower())]
        if not opened:
            continue
        for i in range(opened[-1], max(-1, opened[-1] - 200), -1):
            match = boot.search(lines[i])
            if match:
                return {"version": match.group("ver"), "revision": match.group("rev") or None,
                        "ts": lines[i][:24], "line": lines[i].strip()[:200],
                        "log": str(log)}
    return None


def _ts_epoch(ts: str | None) -> int | None:
    """`2026-10-13T13:10:49.345Z` -> epoch. La riga di log e' in UTC."""
    if not ts or len(ts) < 19:
        return None
    try:
        return int(datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")
                   .replace(tzinfo=timezone.utc).timestamp())
    except ValueError:
        return None


def running_build(slug: str, port: int, *, pid: int | None = None, facts: dict | None = None,
                  claim: dict | None = None) -> dict:
    """La build che *esegue* quella porta: processo, eseguibile, versione.

    Due fonti, e la seconda conta piu' della prima: la versione dell'eseguibile del
    processo in ascolto (il file su disco) e la versione che il processo ha stampato
    avviandosi. Se divergono, il file e' stato **aggiornato sotto** il processo: la
    build in esecuzione e' quella che il processo ha dichiarato, non quella sul disco.
    """
    claim = claimed_build(slug, port) if claim is None else claim
    facts = facts or {}
    out = {"pid": pid, "exe": facts.get("exe"), "exe_version": facts.get("version"),
           "started": facts.get("started"), "exe_mtime": facts.get("mtime"),
           "self_version": (claim or {}).get("version"),
           "revision": (claim or {}).get("revision"),
           "logged_at": (claim or {}).get("ts"), "log": (claim or {}).get("log"),
           "notes": []}
    if not out["pid"]:
        # Nessun processo: la riga di avvio nel log resta li' anche quando l'app e'
        # stata chiusa, e prenderla per buona dichiarerebbe "stessa build" su una
        # porta morta (misurato: build-only su una porta chiusa diceva `same`).
        out["notes"].append("nessun processo in ascolto su quella porta: nessuna build da leggere")
        out["self_version"] = None
        out["revision"] = None
    if claim and out["started"] and _ts_epoch(claim["ts"]) is not None \
            and _ts_epoch(claim["ts"]) < out["started"] - 5:
        out["notes"].append(f"la riga di avvio nel log ({claim['ts']}) precede il processo "
                            f"in ascolto: la dichiarazione non e' di questa esecuzione")
        out["self_version"] = None
        out["revision"] = None
    if out["self_version"] and out["exe_version"] and out["self_version"] != out["exe_version"]:
        out["notes"].append(f"il processo dichiara {out['self_version']} ma l'eseguibile su "
                            f"disco ora dichiara {out['exe_version']}: aggiornato sotto il processo")
    out["version"] = out["self_version"] or out["exe_version"]
    if not out["version"] and out["pid"]:
        out["notes"].append("nessuna versione leggibile: ne' dal processo ne' dal suo eseguibile")
    return out


def configured_build(slug: str, cli: str | None, *, expect: str | None = None,
                     file_facts: dict | None = None) -> dict:
    """La build che la config si aspetta: attesa a mano, registrata, o sul disco."""
    if expect:
        return {"version": expect, "revision": None, "exe": None,
                "source": "attesa sulla riga di comando"}
    recorded = load_builds().get(slug)
    if isinstance(recorded, dict) and recorded.get("version"):
        return {"version": str(recorded["version"]), "revision": recorded.get("revision"),
                "exe": recorded.get("exe"),
                "source": f"impronta registrata ({recorded.get('verified_at') or '?'})"}
    if not cli:
        return {"version": None, "revision": None, "exe": None, "source": "nessun riferimento"}
    exe = configured_exe(cli)
    facts = (file_facts or {}).get(str(exe))
    if facts is None:
        facts = file_versions([str(exe)]).get(str(exe)) or {}
    return {"version": facts.get("version"), "revision": None, "exe": str(exe),
            "source": "eseguibile di config",
            "why": None if facts.get("version") else "eseguibile di config illeggibile"}


def load_builds() -> dict:
    try:
        data = json.loads(BUILDS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_build(slug: str, record: dict) -> None:
    builds = load_builds()
    builds[slug] = record
    try:
        BUILDS_FILE.parent.mkdir(parents=True, exist_ok=True)
        BUILDS_FILE.write_text(json.dumps(builds, indent=2, sort_keys=True), encoding="utf-8")
    except OSError as exc:
        print(f"impronta non scritta ({BUILDS_FILE}): {exc}", file=sys.stderr)


def build_verdict(running: dict, configured: dict) -> dict:
    """Stessa build o no? Il verdetto si regge sulla versione, non sul catalogo."""
    rv, cv = running.get("version"), configured.get("version")
    if not rv:
        notes = running.get("notes") or []
        return {"build": "unknown",
                "why": notes[-1] if notes else "la build in esecuzione non e' leggibile"}
    if not cv:
        why = f"nessuna build di riferimento ({configured.get('source')}"
        if configured.get("why"):
            why += f": {configured['why']}"
        return {"build": "unknown", "why": why + ")"}
    if rv == cv:
        if running.get("revision") and configured.get("revision") \
                and running["revision"] != configured["revision"]:
            return {"build": "different",
                    "why": f"versione {rv} ma revisione diversa ({running['revision']} "
                           f"in esecuzione, {configured['revision']} di riferimento)"}
        installed = str(configured.get("exe") or "").lower()
        launched = str(running.get("exe") or "").lower()
        if installed and launched and installed != launched:
            return {"build": "same", "why": f"stessa build {rv}, ma eseguita da un altro file: "
                           f"{running['exe']} invece di {configured['exe']}"}
        return {"build": "same", "why": f"stessa build {rv} ({configured.get('source')})"}
    return {"build": "different", "why": f"in esecuzione {rv}, di riferimento {cv} "
            f"({configured.get('source')})"}


def build_only(slug: str | None, port: int, expect: str | None = None) -> dict:
    """La build senza handshake: nessun byte al canale, solo PID e file."""
    pid = listening_pids([port]).get(port)
    facts = process_facts([pid]).get(pid, {}) if pid else {}
    running = running_build(slug or "", port, pid=pid, facts=facts)
    cli = None
    if slug:
        try:
            cli = (app_table().get(slug) or {}).get("cli")
        except SystemExit:
            cli = None
    configured = configured_build(slug or "", cli, expect=expect)
    verdict = build_verdict(running, configured)
    return {"port": port, "slug": slug, "running": running, "configured": configured, **verdict}


def main() -> int:
    # La console di Windows e' cp1252: uscita in UTF-8 e testi ASCII, cosi' chi
    # legge stdout da una pipe non trova byte fuori tabella.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--slug", help="slug dell'app (per dedurre porta e token)")
    parser.add_argument("--port", type=int)
    parser.add_argument("--all", action="store_true", help="tutte le app della config")
    parser.add_argument("--token-file", help="control-token (PhotoCraft) o chiave (WordCraft)")
    parser.add_argument("--token-field", default="token", choices=["token", "key"],
                        help="nome del campo nella richiesta auth (WordCraft usa key)")
    parser.add_argument("--timeout", type=float, default=3.0, help="secondi per la risposta")
    parser.add_argument("--wait", type=int, default=0,
                        help="riprova fino a N secondi finche' il peer non risponde")
    parser.add_argument("--no-identity", action="store_true",
                        help="salta il confronto dei cataloghi (piu' veloce)")
    parser.add_argument("--no-build", action="store_true",
                        help="salta il confronto delle build (non tocca PID ne' PowerShell)")
    parser.add_argument("--build-only", action="store_true",
                        help="solo la build, senza handshake col canale")
    parser.add_argument("--expect-version", help="la versione che deve avere l'app in esecuzione")
    parser.add_argument("--record", action="store_true",
                        help="registra la build verificata in ~/.craft-bridge/builds.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.build_only:
        if not args.port:
            parser.error("--build-only vuole --port")
        verdict = build_only(args.slug, args.port, expect=args.expect_version)
        if args.json:
            print(json.dumps(verdict, indent=2))
        else:
            running, configured = verdict["running"], verdict["configured"]
            print(f"porta {verdict['port']}: esegue {running.get('version') or '?'}"
                  f" (pid {running.get('pid') or '?'}, {running.get('exe') or '?'})"
                  f" | riferimento {configured.get('version') or '?'} "
                  f"({configured.get('source')})"
                  f" | build {verdict['build']}: {verdict['why']}")
        return 1 if verdict["build"] == "different" else 0

    try:
        entries = shim_entries(Path(args.config))
    except (SystemExit, json.JSONDecodeError) as exc:
        print(f"config illeggibile: {exc}", file=sys.stderr)
        return 3

    if args.all:
        if not entries:
            print("nessuna entry shim nella config", file=sys.stderr)
            return 2
        targets = sorted(entries)
    elif args.slug:
        if args.slug not in entries and not args.port:
            # `artcraft` e `pdfcraft` esistono nella config ma non passano dallo shim:
            # non hanno una porta di controllo che questo strumento possa interrogare.
            print(f"slug senza entry shim nella config: {args.slug} "
                  f"(con canale di controllo: {', '.join(sorted(entries))})", file=sys.stderr)
            return 2
        targets = [args.slug]
    elif args.port:
        targets = [None]
    else:
        parser.error("serve --all, oppure --slug, oppure --port")
        return 2

    # La tabella dello shim serve sia per le porte default sia per identificare il
    # peer (i cataloghi dei CLI installati) e per sapere quale eseguibile la config
    # avvia (la build di riferimento).
    table = app_table()

    # Il piano (slug, entry, porta) si costruisce prima del giro: cosi' PID e versioni
    # si chiedono **una volta per tutte le porte** (due giri di PowerShell in tutto)
    # invece di uno per app.
    plan = []
    for slug in targets:
        entry = entries.get(slug) if slug else {}
        port = args.port or (entry or {}).get("port") or (table or {}).get(slug, {}).get("port")
        if not port:
            print(f"{slug}: nessuna porta nota", file=sys.stderr)
            return 2
        plan.append((slug, entry or {}, int(port)))

    want_build = not args.no_build
    pid_map = listening_pids([p for _, _, p in plan]) if want_build else {}
    proc_facts = process_facts(sorted(set(pid_map.values()))) if want_build else {}
    file_facts = file_versions([str(configured_exe(table[s]["cli"])) for s, _, _ in plan
                                if s in table]) if want_build else {}

    report: dict = {"timeout": args.timeout, "checks": {}, "craft": 0, "total": 0}
    for slug, entry, port in plan:
        token = read_token(args.token_file or (entry or {}).get("token_file"))
        field = args.token_field
        if slug == "wordcraft" and not token:
            token, field = wordcraft_key(port), "key"
        deadline = time.time() + args.wait
        while True:
            verdict = identify(port, timeout=args.timeout, token=token, token_field=field)
            if verdict["peer"] != "silent" or time.time() >= deadline:
                break
            time.sleep(1.0)

        # Il canale non dice nome ne' versione: si deduce dai comandi che dichiara.
        if verdict["peer"] == "craft" and not args.no_identity:
            channel = channel_catalog(port, token, field, args.timeout)
            name = {"app": None, "why": "il canale non ha risposto con un catalogo"}
            if channel and slug and slug in table:
                ids = cli_catalog(table[slug]["cli"])
                if ids:
                    cov = len(ids & channel) / len(ids)
                    if cov >= MATCH:
                        name = {"app": slug, "coverage": round(cov, 2),
                                "why": "copertura del catalogo locale"}
            if channel and name["app"] is None:
                cataloghi = {s: cli_catalog(sp["cli"]) for s, sp in sorted(table.items())}
                name = name_the_peer(channel, {s: c for s, c in cataloghi.items() if c})
            verdict["app"] = name.get("app")
            verdict["coverage"] = name.get("coverage")
            verdict["second"] = name.get("second")
            verdict["identity_why"] = name.get("why")
            # Senza slug atteso non c'e' niente da contestare: si dice chi e'.
            verdict["identity"] = ("match" if slug and name.get("app") == slug
                                   else "mismatch" if (slug and name.get("app"))
                                   else "identified" if name.get("app") else "unknown")
            if name.get("app") in table:
                verdict["version"] = binary_version(table[name["app"]]["cli"])

        # La build: il catalogo ha appena detto *quale app*; qui si dice *quale
        # versione* gira su quella porta, confrontata con quella di riferimento.
        if verdict["peer"] == "craft" and want_build:
            pid = pid_map.get(port)
            running = running_build(slug or "", port, pid=pid,
                                    facts=proc_facts.get(pid or 0, {}))
            configured = configured_build(slug or "", (table.get(slug) or {}).get("cli"),
                                          expect=args.expect_version, file_facts=file_facts)
            shape = build_verdict(running, configured)
            verdict["build"], verdict["build_why"] = shape["build"], shape["why"]
            verdict["build_running"], verdict["build_configured"] = running, configured
            # Si registra solo cio' che si e' verificato uguale: un'impronta presa su
            # una build diversa fisserebbe il guasto come se fosse la norma.
            if args.record and slug and shape["build"] == "same" and running.get("version"):
                save_build(slug, {
                    "version": running["version"],
                    "revision": running.get("revision"),
                    "exe": configured.get("exe") or running.get("exe"),
                    "running_exe": running.get("exe"),
                    "cli_version": verdict.get("version"),
                    "port": port,
                    "verified_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                })
                verdict["recorded"] = True
            elif args.record and slug:
                print(f"{slug}: impronta non registrata ({shape['build']}: {shape['why']})",
                      file=sys.stderr)

        verdict["slug"] = slug or f"porta {port}"
        report["checks"][verdict["slug"]] = verdict
        report["total"] += 1
        if verdict["peer"] == "craft" and verdict["authenticated"] is not False:
            report["craft"] += 1
        if verdict.get("identity") == "mismatch":
            report["mismatch"] = report.get("mismatch", 0) + 1
        if verdict.get("build") == "different":
            report["drift"] = report.get("drift", 0) + 1
        if not args.json:
            if verdict["peer"] == "craft":
                auth = ("autenticato" if verdict["authenticated"] else
                        "auth rifiutata" if verdict["authenticated"] is False else "senza credenziale")
                if args.no_identity:
                    what = ""
                elif verdict.get("app"):
                    what = (f" | app={verdict['app']} (copertura {verdict['coverage']})"
                            f" | cli {verdict.get('version') or '?'}")
                    if verdict["identity"] == "mismatch":  # solo se uno slug era atteso
                        what += f" | NON e' l'app attesa ({slug})"
                else:
                    what = f" | app non identificata ({verdict.get('identity_why')})"
                if want_build:
                    shape = verdict.get("build")
                    running_exe = verdict["build_running"].get("exe") or ""
                    config_exe = verdict["build_configured"].get("exe") or ""
                    # Stessa build da un altro file: non e' un guasto, ma si dice.
                    else_where = (f" | da {running_exe}" if running_exe and config_exe
                                  and running_exe.lower() != config_exe.lower() else "")
                    if shape == "same":
                        what += (f" | build {verdict['build_running'].get('version')} = config"
                                 " (stessa build)" + else_where)
                    elif shape == "different":
                        what += (f" | build {verdict['build_running'].get('version') or '?'} != config "
                                 f"{verdict['build_configured'].get('version') or '?'}"
                                 " (NON e' la build configurata)" + else_where)
                    else:
                        what += f" | build non verificabile ({verdict.get('build_why')})"
                print(f"[craft] {verdict['slug']:<12} porta={port:<5} {auth}{what}")
            else:
                print(f"[{verdict['peer'].upper()}] {verdict['slug']:<12} porta={port:<5} "
                      f"{verdict['error']}")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"\n{report['craft']}/{report['total']} porte con un peer Craft"
              f"{' autenticato' if args.token_file else ''}"
              + (f" · {report['mismatch']} con l'app sbagliata" if report.get("mismatch") else "")
              + (f" · {report['drift']} con un'altra build" if report.get("drift") else ""))
        if report["craft"] != report["total"]:
            print("una porta senza peer Craft non e' un canale: lo shim la tratta come "
                  "headless (vedi craft-bridge-mcp.py)")
        if report.get("drift"):
            print("una build diversa non e' la build configurata: l'entry aprirebbe "
                  "quell'eseguibile, non questo (vedi craft-bridge.md §3.5)")
    return 0 if (report["craft"] == report["total"] and not report.get("mismatch")
                 and not report.get("drift")) else 1


if __name__ == "__main__":
    sys.exit(main())
