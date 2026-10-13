#!/usr/bin/env python3
"""Confronta quello che il ponte ha installato con quello che il launcher pubblica.

Il launcher di ArtCraft tiene accanto a se' l'elenco che usa per aggiornare le app:
`%LOCALAPPDATA%\\ArtCraft Launcher\\feed.json` (con `releases.json` nella stessa
cartella). Per ogni app dice il repository di provenienza, l'ultima release pubblicata
e, per ogni artefatto, sistema, architettura, tipo di pacchetto e **sha256**: sono i
byte che il fornitore ha pubblicato, non una dichiarazione.

Il ponte, dal canto suo, sa quale build **e' installata**: la versione dichiarata
dall'eseguibile di config, oppure l'impronta registrata la prima volta che l'app e'
stata vista girare. Le due cose non coincidono, e finora il ponte conosceva solo la
prima: un numero di versione dice cosa un eseguibile dichiara di essere, **non** se e'
la build che il fornitore ha pubblicato.

Questo strumento mette le due cose accanto. Non inventa: quello che il feed non dice
resta "non lo so", e quello che il feed non nomina resta "non lo so" invece di
diventare un guasto.

Uso:
    python craft-bridge-feed.py                 # installata contro pubblicata
    python craft-bridge-feed.py --packages      # anche i pacchetti pubblicati per questo sistema
    python craft-bridge-feed.py --downloads     # e i byte dei pacchetti gia' scaricati
    python craft-bridge-feed.py --json
    python craft-bridge-feed.py --feed-dir <cartella>   # feed di prova, o altro disco

Esito:
    0  nessuno scostamento
    1  almeno uno scostamento da segnalare: un'app indietro o avanti rispetto alla
       pubblicata, oppure un file scaricato che non corrisponde al suo sha256
    2  errore d'uso
    3  feed assente o illeggibile

Nota sui sistemi: la cartella del feed e' nota e verificata su Windows, che e' dove le
app sono installate su questa macchina. Gli altri percorsi sono quelli **attesi** dal
launcher sulle rispettive piattaforme, non misurati: su un sistema diverso si passa
`--feed-dir` invece di fidarsi del default.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

LAUNCHER_DIR = "ArtCraft Launcher"
FEED_FILE = "feed.json"
RELEASES_FILE = "releases.json"
DOWNLOADS_DIR = "downloads"

# Cosa vuol dire un esito, nelle parole del feed: il pacchetto che il launcher
# installerebbe su questo sistema.
PACKAGES = {"msi": "installer MSI", "portable_zip": "pacchetto portabile",
            "dmg": "immagine disco", "app_image": "AppImage", "deb": "pacchetto .deb",
            "rpm": "pacchetto .rpm", "flatpak": "Flatpak", "tar_gz": "archivio .tar.gz",
            "cli_zip": "archivio della CLI"}


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


class FeedError(Exception):
    """Il feed c'e' ma non si puo' leggere: l'unico caso in cui non c'e' un verdetto."""


def default_feed_dir() -> Path:
    """Dove il launcher tiene il feed, sul sistema in cui stiamo girando.

    Su Windows e' verificato (e' dove questa macchina l'ha scritto). Gli altri due
    percorsi sono quelli attesi sulle rispettive piattaforme: dichiararli e' meglio
    che non cercare affatto, ma non sono una misura.
    """
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        return (Path(base) if base else Path.home() / "AppData" / "Local") / LAUNCHER_DIR
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / LAUNCHER_DIR
    base = os.environ.get("XDG_DATA_HOME")
    return (Path(base) if base else Path.home() / ".local" / "share") / LAUNCHER_DIR


def this_platform() -> tuple[str | None, str | None]:
    """Il sistema e l'architettura nelle parole del feed (`windows`, `x64`, ...)."""
    systems = {"win32": "windows", "darwin": "macos", "linux": "linux"}
    machines = {"amd64": "x64", "x86_64": "x64", "x86": "x86", "i386": "x86",
                "arm64": "arm64", "aarch64": "arm64"}
    return systems.get(sys.platform), machines.get(platform.machine().lower())


def _normalized_app(slug: str, entry: dict) -> dict:
    release = entry.get("latest_release") or {}
    return {
        "slug": slug,
        "name": entry.get("name") or slug,
        "repo": entry.get("repo"),
        "version": release.get("version"),
        "tag": release.get("tag"),
        "published_at": release.get("published_at"),
        "html_url": release.get("html_url"),
        "prerelease": bool(release.get("prerelease")),
        "fetched_at": entry.get("app_last_fetched"),
        "assets": [a for a in (release.get("assets") or []) if isinstance(a, dict)],
    }


def load(feed_dir: Path) -> dict:
    """Il feed del launcher, normalizzato. Solleva `FeedError` se non si legge.

    `releases.json` e' opzionale: se c'e' si tiene la versione che dichiara, perche'
    un feed vecchio e uno nuovo che non concordano sono un'informazione (il launcher
    ha aggiornato una delle due liste e non l'altra), non un dettaglio interno.
    """
    feed_file = feed_dir / FEED_FILE
    try:
        raw = json.loads(feed_file.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise FeedError(f"feed assente: {feed_file}")
    except OSError as exc:
        raise FeedError(f"feed non leggibile: {feed_file} ({exc})")
    except json.JSONDecodeError as exc:
        raise FeedError(f"{FEED_FILE} illeggibile: {exc}")
    info = raw.get("release_info") if isinstance(raw, dict) else None
    apps_raw = (info or {}).get("apps")
    if not isinstance(apps_raw, dict) or not apps_raw:
        raise FeedError(f"{FEED_FILE} senza `release_info.apps`: non e' il feed del launcher")
    apps = {str(slug): _normalized_app(str(slug), entry if isinstance(entry, dict) else {})
            for slug, entry in apps_raw.items()}

    releases: dict[str, dict] = {}
    releases_file = feed_dir / RELEASES_FILE
    try:
        data = json.loads(releases_file.read_text(encoding="utf-8-sig"))
        entries = data.get("entries") if isinstance(data, dict) else None
        for repo, item in (entries or {}).items():
            release = (item or {}).get("release") or {}
            releases[str(repo)] = {"version": release.get("version"),
                                   "tag": release.get("tag")}
    except (OSError, json.JSONDecodeError, AttributeError):
        pass  # assente o illeggibile: si va avanti col solo feed.json
    return {"dir": str(feed_dir), "fetched_at": (info or {}).get("last_fetched"),
            "apps": apps, "releases": releases,
            "releases_file": str(releases_file) if releases else None}


def artefacts_for(app: dict, system: str | None, machine: str | None) -> list[dict]:
    """Gli artefatti pubblicati per questo sistema (e questa architettura)."""
    out = []
    for asset in app.get("assets") or []:
        where = asset.get("platform") or {}
        if system and where.get("os") != system:
            continue
        if machine and where.get("arch") not in (machine, "universal"):
            continue
        out.append(asset)
    return out


def _version_tuple(text: str | None) -> tuple[int, ...]:
    parts = re.findall(r"\d+", str(text or ""))
    return tuple(int(p) for p in parts[:4])


def _trim(version: tuple[int, ...]) -> tuple[int, ...]:
    """`0.8.2.0` e `0.8.2` sono la stessa versione: le code di zeri non contano."""
    while version and version[-1] == 0:
        version = version[:-1]
    return version


def compare(installed: str | None, published: str | None) -> str:
    """`same`, `behind`, `ahead` o `unknown`: la versione installata contro la pubblicata."""
    mine, theirs = _version_tuple(installed), _version_tuple(published)
    if not mine or not theirs:
        return "unknown"
    mine, theirs = _trim(mine), _trim(theirs)
    if mine == theirs:
        return "same"
    return "behind" if mine < theirs else "ahead"


def package_facts(app: dict, system: str | None, machine: str | None) -> list[dict]:
    """Gli artefatti che toccano a questo sistema, con l'impronta pubblicata."""
    out = []
    for asset in sorted(artefacts_for(app, system, machine), key=lambda a: str(a.get("name"))):
        where = asset.get("platform") or {}
        out.append({"name": asset.get("name"),
                    "kind": PACKAGES.get(str(where.get("package_type")),
                                         str(where.get("package_type"))),
                    "sha256": asset.get("sha256"),
                    "size": asset.get("size_bytes"),
                    "url": asset.get("download_url")})
    return out


def package_line(app: dict, system: str | None, machine: str | None) -> str:
    """Quale artefatto tocca a questo sistema, in una riga sola."""
    found = package_facts(app, system, machine)
    if not found:
        return (f"nessun pacchetto pubblicato per {system or '?'}/{machine or '?'}"
                if system else "sistema non riconosciuto: nessun pacchetto da indicare")
    shown = []
    for facts in found:
        digest = (str(facts.get("sha256")) or "")[:12]
        shown.append(f"{facts['name']} ({facts['kind']}"
                     + (f", sha256 {digest}..." if digest else ", senza impronta") + ")")
    return "; ".join(shown)


def sha256_file(path: Path, limit: int = 256 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def download_rows(feed: dict, downloads_dir: Path) -> list[dict]:
    """I pacchetti che il launcher ha gia' scaricato sono quelli pubblicati?

    E' l'unico controllo di **byte** che si puo' fare senza riscaricare niente: il
    feed pubblica lo sha256 di ogni artefatto, e la cartella dei download contiene i
    file cosi' come sono arrivati. Un file che c'e' ma non torna e' l'unico caso in
    cui questo strumento accusa.
    """
    by_name = {}
    for app in feed["apps"].values():
        for asset in app.get("assets") or []:
            if asset.get("name"):
                by_name[str(asset["name"])] = asset
    if not downloads_dir.is_dir():
        return [{"check": "download", "kind": "absent", "state": "nota",
                 "detail": f"cartella dei download assente ({downloads_dir})",
                 "action": ""}]
    files = sorted(p for p in downloads_dir.rglob("*") if p.is_file())
    if not files:
        return [{"check": "download", "kind": "absent", "state": "nota",
                 "detail": f"niente da confrontare: {downloads_dir} e' vuota",
                 "action": ""}]
    rows = []
    for path in files:
        asset = by_name.get(path.name)
        if asset is None:
            rows.append({"check": f"download {path.name}", "kind": "absent", "state": "nota",
                         "detail": "non e' un artefatto del feed: niente con cui confrontarlo",
                         "action": ""})
            continue
        digest = sha256_file(path)
        expected = str(asset.get("sha256") or "").lower()
        if not expected:
            rows.append({"check": f"download {path.name}", "kind": "unknown", "state": "nota",
                         "detail": "il feed non pubblica un'impronta per questo file",
                         "action": ""})
        elif digest.lower() == expected:
            rows.append({"check": f"download {path.name}", "kind": "same", "state": "ok",
                         "detail": f"byte come pubblicati (sha256 {digest[:12]}...)",
                         "action": ""})
        else:
            rows.append({"check": f"download {path.name}", "kind": "hash", "state": "fail",
                         "detail": f"byte diversi da quelli pubblicati: {digest[:12]} != "
                                   f"{expected[:12]}",
                         "action": "cancella il file e riscaricalo: il download e' "
                                   "incompleto o alterato"})
    return rows


def rows(table: dict, feed: dict, installed: dict, *,
         downloads_dir: Path | None = None, packages: bool = False,
         system: str | None = None, machine: str | None = None) -> list[dict]:
    """Il confronto app per app. Funzione pura: nessuna porta, nessun file, nessuna app.

    `installed` ha la forma `{slug: {"version": "0.8.2", "source": "eseguibile di config"}}`,
    cioe' quello che il ponte sa della build sul disco.
    """
    out: list[dict] = []
    for slug in sorted(table):
        app = feed["apps"].get(slug)
        known = installed.get(slug) or {}
        version, source = known.get("version"), known.get("source") or "?"
        if app is None:
            out.append({"check": slug, "kind": "absent", "state": "nota",
                        "detail": f"il feed del launcher non lo nomina (installata: "
                                  f"{version or '?'}, {source})",
                        "action": "aggiorna il feed dal launcher, o togli l'app dalla tabella"})
            continue
        repo = app.get("repo") or "?"
        shape = compare(version, app.get("version"))
        published = app.get("version") or "?"
        row = {"check": slug, "kind": shape, "state": "ok", "action": "",
               "packages": package_facts(app, system, machine)}
        if shape == "same":
            row["detail"] = f"{version} = {published} ({repo}, installata da {source})"
        elif shape in ("behind", "ahead"):
            mark = "<" if shape == "behind" else ">"
            row.update(state="nota",
                       detail=f"{version} {mark} {published} ({repo}, installata da {source})",
                       action="aggiorna dal launcher" if shape == "behind"
                              else "il ponte e' avanti alla pubblicata: e' una build di prova, "
                                   "o il feed e' vecchio")
        else:
            row.update(kind="unknown", state="nota",
                       detail=f"pubblicata {published} ({repo}), installata non leggibile "
                              f"({source})",
                       action="avvia l'app dalla sua entry una volta: la versione si legge "
                              "dall'eseguibile di config")
        out.append(row)
        if packages:
            out.append({"check": f"pacchetto {slug}", "kind": shape, "state": "ok",
                        "detail": package_line(app, system, machine), "action": ""})
    extra = sorted(slug for slug in feed["apps"] if slug not in table)
    if extra:
        names = ", ".join(f"{slug} ({feed['apps'][slug].get('version') or '?'})" for slug in extra)
        out.append({"check": "fuori dal ponte", "kind": "extra", "state": "nota",
                    "detail": f"{len(extra)} app nel feed che il ponte non guida: {names}",
                    "action": ""})
    stale = []
    for slug in sorted(table):
        app = feed["apps"].get(slug)
        if app is None or not app.get("repo"):
            continue
        other = (feed.get("releases") or {}).get(str(app["repo"]))
        if other and other.get("version") and app.get("version") \
                and str(other["version"]) != str(app["version"]):
            stale.append(f"{slug}: {app['version']} in {FEED_FILE}, {other['version']} "
                         f"in {RELEASES_FILE}")
    if stale:
        out.append({"check": "feed coerente", "kind": "feed", "state": "nota",
                    "detail": "le due liste del launcher non concordano: " + "; ".join(stale),
                    "action": "riapri il launcher: una delle due e' vecchia"})
    if downloads_dir is not None:
        out += download_rows(feed, downloads_dir)
    return out


def installed_versions(table: dict) -> dict:
    """Cosa il ponte sa della build installata, per ogni app della tabella.

    La versione si legge dall'eseguibile di config in **un solo giro**; se c'e' una
    impronta registrata, quella vince, perche' e' stata verificata con l'app viva.
    """
    facts = IDENT.file_versions([str(IDENT.configured_exe(spec["cli"])) for spec in table.values()])
    out = {}
    for slug, spec in table.items():
        build = IDENT.configured_build(slug, spec["cli"], file_facts=facts)
        out[slug] = {"version": build.get("version"), "source": build.get("source")}
    return out


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser(
        description="confronta le app installate con quelle pubblicate dal launcher")
    parser.add_argument("--feed-dir", default=str(default_feed_dir()),
                        help="cartella del feed del launcher (default: quella di questo sistema)")
    parser.add_argument("--packages", action="store_true",
                        help="mostra anche i pacchetti pubblicati per questo sistema")
    parser.add_argument("--downloads", action="store_true",
                        help="confronta anche i pacchetti gia' scaricati con lo sha256 pubblicato")
    parser.add_argument("--downloads-dir",
                        help="cartella dei pacchetti scaricati (default: <feed>/"
                             + DOWNLOADS_DIR + ")")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", help="scrivi il report JSON anche su file")
    args = parser.parse_args()

    try:
        table = CONFIG.apps_table()
    except SystemExit as exc:
        print(f"tabella delle app illeggibile: {exc}", file=sys.stderr)
        return 3

    feed_dir = Path(args.feed_dir)
    try:
        feed = load(feed_dir)
    except FeedError as exc:
        print(f"craft-bridge feed\n  FIX  feed            {exc}", file=sys.stderr)
        print("     -> il confronto si fa con le app che il launcher installa: "
              "senza il suo feed non c'e' un termine di paragone", file=sys.stderr)
        return 3

    downloads = None
    if args.downloads:
        downloads = Path(args.downloads_dir) if args.downloads_dir \
            else feed_dir / DOWNLOADS_DIR
    system, machine = this_platform()
    try:
        results = rows(table, feed, installed_versions(table), downloads_dir=downloads,
                       packages=args.packages, system=system, machine=machine)
    except OSError as exc:
        print(f"lettura fallita: {exc}", file=sys.stderr)
        return 3

    # Uno scostamento e' una differenza fra installato e pubblicato: le note (app che
    # il feed non nomina, download mai fatto, sistema non riconosciuto) sono lacune di
    # conoscenza, non guasti, e non fanno uscire con 1.
    stale = [r for r in results if r["state"] == "fail" or r.get("kind") in ("behind", "ahead")]
    notes = [r for r in results if r["state"] == "nota" and r not in stale]
    report = {"feed": {"dir": feed["dir"], "fetched_at": feed["fetched_at"],
                       "apps": len(feed["apps"])},
              "platform": {"system": system, "arch": machine},
              "checks": results, "stale": len(stale), "notes": len(notes), "ok": not stale}

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print("craft-bridge feed")
        print(f"  feed  {feed['dir']}"
              + (f"  (aggiornato {feed['fetched_at']})" if feed.get("fetched_at") else "")
              + f"  {len(feed['apps'])} app")
        print(f"  sistema  {system or '?'}/{machine or '?'}")
        for row in results:
            mark = {"ok": "ok  ", "fail": "FIX ", "nota": "nota"}[row["state"]]
            print(f"  {mark} {row['check']:<15} {row['detail']}")
            if row["action"] and row["state"] != "ok":
                print(f"       {' ' * len(row['check'])} -> {row['action']}")
        behind = [r for r in results if r.get("kind") == "behind"]
        ahead = [r for r in results if r.get("kind") == "ahead"]
        broken = [r for r in results if r["state"] == "fail"]
        if stale:
            parts = []
            if behind:
                parts.append(f"{len(behind)} " + ("app indietro" if len(behind) == 1
                                                   else "app indietro"))
            if ahead:
                parts.append(f"{len(ahead)} app avanti")
            if broken:
                parts.append(f"{len(broken)} file con byte diversi")
            noun = "cosa da segnalare" if len(stale) == 1 else "cose da segnalare"
            print(f"\nVERDETTO: {len(stale)} {noun}: " + ", ".join(parts))
        else:
            note_word = "nota" if len(notes) == 1 else "note"
            print(f"\nVERDETTO: installato e pubblicato coincidono ({len(notes)} {note_word})")

    if args.out:
        try:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                      encoding="utf-8")
        except OSError as exc:
            print(f"report non scritto ({args.out}): {exc}", file=sys.stderr)
        else:
            print(f"\nreport: {args.out}")

    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
