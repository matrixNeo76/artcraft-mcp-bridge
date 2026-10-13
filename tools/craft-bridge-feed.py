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

E c'e' una domanda che la versione non puo' rispondere: **l'eseguibile installato e'
quello pubblicato?** `--bytes` la risponde confrontando il `<slug>-cli.exe` installato
con il file omonimo dentro il pacchetto pubblicato, letto in memoria senza estrarre
niente e senza installare una seconda copia dell'app. Gli archivi si prendono da
`~/.craft-bridge/releases` o dalla cartella dei download del launcher; `--download
<slug>` li scarica (impronta del feed verificata **prima** di usarli, file `.parte`
rimosso se non torna), e i pacchetti veri vanno da 14 a 120 MB: per questo lo
scaricamento lo chiede un'app alla volta, non lo fa da solo.

Uso:
    python craft-bridge-feed.py                 # installata contro pubblicata
    python craft-bridge-feed.py --packages      # anche i pacchetti pubblicati per questo sistema
    python craft-bridge-feed.py --downloads     # e i byte dei pacchetti gia' scaricati
    python craft-bridge-feed.py --bytes         # la CLI installata contro quella nel pacchetto
    python craft-bridge-feed.py --download soundcraft   # scarica quel pacchetto e confronta
    python craft-bridge-feed.py --json
    python craft-bridge-feed.py --feed-dir <cartella>   # feed di prova, o altro disco

Esito:
    0  nessuno scostamento
    1  almeno uno scostamento da segnalare: un'app indietro o avanti rispetto alla
       pubblicata, un file scaricato che non corrisponde al suo sha256, oppure la CLI
       installata che non e' quella dentro il pacchetto pubblicato
    2  errore d'uso
    3  feed assente o illeggibile, o scaricamento fallito

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
import tarfile
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

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

# Gli unici artefatti che si aprono e si leggono senza strumenti esterni. Un MSI, un
# .deb, un .dmg o un AppImage restano fuori: dichiararlo e' meglio che fingere di
# poterli confrontare (e su Windows la CLI non e' pubblicata a parte: sta dentro il
# pacchetto portabile, quindi per gli altri c'e' solo il pacchetto grande).
CLI_ARCHIVES = ("cli_zip", "portable_zip", "tar_gz")

# Da dove si scarica: solo questi host, solo https. Il feed li indica, ma il feed e'
# un file locale che chiunque puo' riscrivere: prima di aprire una connessione si
# controlla a chi si sta parlando.
ARCHIVE_HOSTS = ("github.com", "objects.githubusercontent.com",
                 "release-assets.githubusercontent.com", "codeload.github.com")

# Massimo scaricato per artefatto: i pacchetti veri arrivano a ~120 MB, e un limite
# dieci volte tanto lascia spazio senza trasformare un errore del feed in un download
# infinito.
MAX_DOWNLOAD = 1 << 30


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


def cache_dir() -> Path:
    """Dove questo strumento tiene i pacchetti che scarica per guardarci dentro.

    Non e' la cartella del launcher: quella e' sua e cambia con le sue regole. Qui
    si accumula solo quello che serve al confronto dei byte, e si puo' cancellare
    quando si vuole (`--cache-dir` per spostarla).
    """
    return Path.home() / ".craft-bridge" / "releases"


def cli_name(slug: str) -> str:
    """Come si chiama la CLI dentro il pacchetto, su questo sistema.

    Su Windows `<slug>-cli.exe` e' quello che c'e' anche installato in
    `C:\\Program Files` (verificato). Fuori da Windows il nome atteso e' senza
    estensione: non misurato su questa macchina.
    """
    return f"{slug}-cli.exe" if sys.platform == "win32" else f"{slug}-cli"


def archive_for(app: dict, system: str | None, machine: str | None) -> dict | None:
    """L'archivio pubblicato che contiene la CLI per questo sistema, se c'e'.

    Prima l'archivio della sola CLI, poi il pacchetto portabile, poi il tar.gz: il
    piu' piccolo che risponde alla domanda e' anche il piu' onesto da scaricare.
    """
    order = {kind: i for i, kind in enumerate(CLI_ARCHIVES)}
    found = [asset for asset in artefacts_for(app, system, machine)
             if str((asset.get("platform") or {}).get("package_type")) in order]
    if not found:
        return None
    return sorted(found, key=lambda a: order[str((a["platform"] or {}).get("package_type"))])[0]


def find_archive(asset: dict, dirs: list[Path]) -> Path | None:
    """Il primo posto in cui quell'archivio c'e' gia': la nostra cache, o il launcher."""
    name = str(asset.get("name") or "")
    for folder in dirs:
        if name and (folder / name).is_file():
            return folder / name
    return None


def extract_member(archive: Path, wanted: str) -> tuple[str, bytes] | None:
    """Il file dentro l'archivio il cui nome e' quello cercato (zip o tar.gz).

    Si legge in memoria: non si estrae niente su disco. E' l'unico modo per dire se
    l'eseguibile installato sono i byte pubblicati, senza installare una seconda copia
    dell'app.
    """
    name = archive.name.lower()
    try:
        if name.endswith(".zip"):
            with zipfile.ZipFile(archive) as bundle:
                for member in bundle.namelist():
                    if PurePosixPath(member).name.lower() == wanted.lower():
                        return member, bundle.read(member)
        elif name.endswith((".tar.gz", ".tgz")):
            with tarfile.open(archive) as bundle:
                for member in bundle.getmembers():
                    if member.isfile() and PurePosixPath(member.name).name.lower() == wanted.lower():
                        handle = bundle.extractfile(member)
                        if handle is not None:
                            return member.name, handle.read()
    except (OSError, zipfile.BadZipFile, tarfile.TarError):
        return None
    return None


def compare_cli_bytes(archive: Path, asset: dict, slug: str, installed: Path) -> dict:
    """La CLI installata sono i byte pubblicati?

    Tre domande in fila, e ognuna puo' fermare le altre: l'archivio e' quello
    pubblicato (sha256 del feed)? la CLI installata c'e'? il file dentro l'archivio e'
    identico a quello installato? L'ultima e' la sola che risponde "questa e' la
    release" invece di "dichiara di esserla".
    """
    row = {"check": f"byte {slug}", "kind": "bytes", "state": "ok", "action": ""}
    published = str(asset.get("sha256") or "").lower()
    if not published:
        row.update(state="nota", kind="unknown",
                   detail=f"il feed non pubblica un'impronta per {archive.name}")
        return row
    actual = sha256_file(archive)
    if actual.lower() != published:
        row.update(state="fail", kind="hash",
                   detail=f"{archive.name} non e' quello pubblicato: {actual[:12]}... != "
                          f"{published[:12]}...",
                   action="cancella l'archivio e riscaricalo")
        return row
    if not installed.is_file():
        row.update(state="nota", kind="unknown",
                   detail=f"la CLI installata non c'e': {installed}")
        return row
    found = extract_member(archive, installed.name)
    if found is None:
        row.update(state="nota", kind="unknown",
                   detail=f"{installed.name} non c'e' dentro {archive.name}")
        return row
    member, published_bytes = found
    mine, theirs = sha256_file(installed), hashlib.sha256(published_bytes).hexdigest()
    if mine.lower() == theirs.lower():
        row.update(detail=f"{installed.name} e' {member} dentro {archive.name}, byte per byte "
                          f"(sha256 {mine[:12]}...)")
        return row
    row.update(state="fail", kind="bytes",
               detail=f"{installed.name} {mine[:12]}... != {member} dentro {archive.name} "
                      f"{theirs[:12]}... ({len(published_bytes)} byte pubblicati, "
                      f"{installed.stat().st_size} installati)",
               action="l'eseguibile installato non e' quello pubblicato: reinstalla l'app "
                      "dal launcher, o indaga su quella copia")
    return row


def download_asset(asset: dict, into: Path) -> Path:
    """Scarica un artefatto pubblicato e ne verifica l'impronta prima di usarlo.

    Si scrive su un file `.parte` e si rinomina solo a impronta verificata: un
    download interrotto non lascia in giro un archivio che sembra buono. Se l'impronta
    non torna il file viene cancellato e si solleva `FeedError`, cosi' l'errore arriva
    a chi ha chiesto il download invece di diventare un verdetto sui byte.
    """
    url = str(asset.get("download_url") or "")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ARCHIVE_HOSTS:
        raise FeedError(f"indirizzo non accettato per il download: {url or '(assente)'}")
    name, expected = str(asset.get("name") or "artefatto"), str(asset.get("sha256") or "").lower()
    into.mkdir(parents=True, exist_ok=True)
    target, partial = into / name, into / (name + ".parte")
    started = time.time()
    print(f"  scarico {name} ({int(asset.get('size_bytes') or 0) / 1e6:.1f} MB)...",
          file=sys.stderr)
    digest = hashlib.sha256()
    written = 0
    try:
        with urllib.request.urlopen(url, timeout=120) as reply, partial.open("wb") as handle:
            while chunk := reply.read(1 << 20):
                written += len(chunk)
                if written > MAX_DOWNLOAD:
                    raise FeedError(f"{name} supera il limite di scaricamento")
                digest.update(chunk)
                handle.write(chunk)
    except (OSError, urllib.error.URLError) as exc:
        partial.unlink(missing_ok=True)
        raise FeedError(f"scaricamento fallito ({name}): {exc}")
    if expected and digest.hexdigest() != expected:
        partial.unlink(missing_ok=True)
        raise FeedError(f"{name} non corrisponde all'impronta pubblicata: "
                        f"{digest.hexdigest()[:12]}... != {expected[:12]}...")
    partial.replace(target)
    print(f"  {name}: {written / 1e6:.1f} MB in {time.time() - started:.0f} s, impronta "
          f"verificata", file=sys.stderr)
    return target


def rows(table: dict, feed: dict, installed: dict, *,
         downloads_dir: Path | None = None, packages: bool = False,
         archive_dirs: list[Path] | None = None, cli_paths: dict | None = None,
         only: set[str] | None = None,
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
    if archive_dirs is not None:
        for slug in sorted(table):
            if only and slug not in only:
                continue
            app = feed["apps"].get(slug)
            if app is None:
                continue
            asset = archive_for(app, system, machine)
            cli = (cli_paths or {}).get(slug) or table[slug].get("cli")
            if asset is None:
                out.append({"check": f"byte {slug}", "kind": "unknown", "state": "nota",
                            "detail": "nessun archivio leggibile per "
                                      f"{system or '?'}/{machine or '?'}: la CLI sta in un "
                                      "contenitore che non si apre senza strumenti esterni",
                            "action": ""})
                continue
            found = find_archive(asset, archive_dirs)
            if found is None:
                size = int(asset.get("size_bytes") or 0) / 1e6
                out.append({"check": f"byte {slug}", "kind": "unknown", "state": "nota",
                            "detail": f"{asset.get('name')} non e' sul disco ({size:.1f} MB)",
                            "action": f"python craft-bridge-feed.py --download {slug}"})
                continue
            out.append(compare_cli_bytes(found, asset, slug, Path(str(cli))))
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
    parser.add_argument("--bytes", action="store_true",
                        help="confronta la CLI installata con quella dentro il pacchetto "
                             "pubblicato: gli archivi gia' sul disco, nessuno scaricamento")
    parser.add_argument("--download", action="append", default=[], metavar="SLUG",
                        help="scarica il pacchetto di quell'app (impronta verificata) e ne "
                             "confronta i byte; ripetibile")
    parser.add_argument("--cache-dir", default=str(cache_dir()),
                        help="dove tenere i pacchetti scaricati (default: ~/.craft-bridge/releases)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", help="scrivi il report JSON anche su file")
    args = parser.parse_args()

    try:
        # Le app **servite dal ponte**: quelle dello shim piu' quella del traduttore.
        # PdfCraft non ha un canale su porta nota, ma il ponte la serve, quindi la
        # domanda "e' la release pubblicata?" vale anche per lei.
        table = CONFIG.bridge_table()
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

    archive_dirs = [Path(args.cache_dir)]
    if downloads is not None:
        archive_dirs.append(downloads)
    elif (feed_dir / DOWNLOADS_DIR).is_dir():
        archive_dirs.append(feed_dir / DOWNLOADS_DIR)
    wanted = {str(s) for s in args.download}
    if wanted:
        unknown = sorted(wanted - set(table))
        if unknown:
            print(f"app fuori dalla tabella: {', '.join(unknown)}", file=sys.stderr)
            return 2
        for slug in sorted(wanted):
            asset = archive_for(feed["apps"].get(slug) or {}, system, machine)
            if asset is None:
                print(f"{slug}: nessun archivio pubblicato che si possa aprire per "
                      f"{system or '?'}/{machine or '?'}", file=sys.stderr)
                continue
            already = find_archive(asset, archive_dirs)
            if already is not None:
                print(f"  {slug}: {asset['name']} e' gia' in {already.parent}", file=sys.stderr)
                continue
            try:
                download_asset(asset, Path(args.cache_dir))
            except FeedError as exc:
                print(f"  {slug}: {exc}", file=sys.stderr)
                return 3

    want_bytes = args.bytes or bool(wanted)
    try:
        results = rows(table, feed, installed_versions(table), downloads_dir=downloads,
                       packages=args.packages, system=system, machine=machine,
                       archive_dirs=archive_dirs if want_bytes else None,
                       only=(None if args.bytes or not wanted else wanted),
                       cli_paths={slug: spec["cli"] for slug, spec in table.items()})
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
