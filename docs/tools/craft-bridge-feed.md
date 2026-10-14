---
type: Tool
title: "craft-bridge-feed - what the vendor publishes, against what is installed"
description: "Reads the ArtCraft launcher feed (releases, source repository, package sha256) and compares it with the installed build; with --bytes it compares the installed executable with the one inside the published package, byte for byte."
resource: ../../tools/craft-bridge-feed.py
tags: [tool, releases, comparison, launcher]
generated: { by: process:freebuff-buffy, at: 2026-10-13T18:10:00Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-feed.py
  title: source
- resource: ../../tools/craft-bridge-ident.py
  title: where the installed build comes from
- resource: ../../tools/craft-bridge-doctor.py
  title: who queries it inside the verdict
---

# The problem

The version of an executable says what that executable **claims** to be. It does not say
whether it is the release the vendor distributes: two builds with the same version number
are indistinguishable, and that is a declared limit of the bridge. The ArtCraft launcher,
though, keeps the list it uses to update the apps on disk, and the answer is in that list.

# Where the two answers come from

| Side | Where it is | What it says |
|---|---|---|
| **published** | `%LOCALAPPDATA%\ArtCraft Launcher\feed.json`, with `releases.json` beside it | source repository, latest release (version, tag, date), and per artifact system, architecture, package type and **sha256** |
| **installed** | the shim table, read by [craft-bridge-ident](craft-bridge-ident.md) | version declared by the config executable, or the fingerprint recorded the first time the app was seen running |

The comparison is a pure function: table, feed and installed versions go in, lines come
out. The tests exercise it with a fake feed, so with no network and no apps.

# Interface

```
python tools/craft-bridge-feed.py                 # installed against published
python tools/craft-bridge-feed.py --packages      # the packages for this system too
python tools/craft-bridge-feed.py --downloads     # and the bytes of the packages already downloaded
python tools/craft-bridge-feed.py --bytes         # the installed CLI against the one in the package
python tools/craft-bridge-feed.py --download soundcraft   # downloads that package and compares
python tools/craft-bridge-feed.py --json
python tools/craft-bridge-feed.py --feed-dir <folder>   # test feed, or another disk
```

# The question the version cannot answer

`--bytes` compares the installed `<slug>-cli.exe` with the file of the same name inside the
published package. They are three questions in a row, and each one can stop the others:

| Step | If it does not add up |
|---|---|
| is the archive on disk the published one? (`sha256` from the feed) | `FIX byte <slug>`: the archive is not the published one, delete it and download it again |
| is the installed CLI there? | `nota`: nothing to compare, and the reason is written |
| is the file inside the archive identical to the installed one? | `FIX byte <slug>`: the installed executable is not the published one — **this is the only answer that says "this is the release" instead of "it claims to be it"** |

The archives are looked for in `~/.craft-bridge/releases` and in the launcher's downloads
folder. If they are not there, the line says **which** file is missing, **how big** it is
and the exact command to fetch it: downloading them all together would be hundreds of MB,
and one app at a time is a choice, not a technical limitation.

# What can be opened

| Package type | Can it be read? |
|---|---|
| `cli_zip` (archive of the CLI alone) | yes, and it is the first one chosen when present — but it is published **for macOS only** |
| `portable_zip`, `tar_gz` | yes: on Windows the CLI sits **inside** the portable package, so it is the only one that answers |
| `msi`, `dmg`, `deb`, `rpm`, `flatpak`, `app_image` | no: they need external tools, and the tool **says so** instead of pretending it compared them |

# What it distinguishes, concretely

| Line | Meaning |
|---|---|
| `0.8.2 = 0.8.2 (storytold/photocraft, installata da eseguibile di config)` | aligned, and the source of the installed version is declared |
| `0.6.2 < 0.6.3 (storytold/cadcraft, ...)` | the installed app is behind the published one |
| `0.6.2 > 0.6.3` | the bridge is ahead: a test build, or an old feed |
| `installata non leggibile` | the feed answers, the executable does not: start the app once |
| `download <file>: byte diversi da quelli pubblicati` | the downloaded file does not match its sha256 |
| `byte <slug>: <cli> e' <membro> dentro <archivio>, byte per byte` | the installed executable **is** the published one |
| `byte <slug>: <a> != <b> dentro <archivio>` | the installed executable is not the published one |
| `feed coerente` | `feed.json` and `releases.json` disagree about the same app |

# Exit codes

| Exit | Meaning |
|---|---|
| 0 | no divergence |
| 1 | at least one divergence: an app behind or ahead, a downloaded archive that does not match its sha256, or an installed CLI that is not the one inside the package |
| 2 | usage error (for instance `--download` on an app outside the table) |
| 3 | feed missing or unreadable, or a failed download |

# Cost

~0.9 s with no archives to read, almost all of it in reading the executable versions (a
single PowerShell round). `doctor --no-live`, which includes this comparison, stays under
a second: reading the versions was needed anyway and is not repeated. With `--bytes` the
reading of every archive present is added (one `sha256` over 14-120 MB) plus opening it for
the single member: measured on a 14.3 MB archive, a few tenths of a second. With
`--download` the download is added: 14.3 MB in 2 s on this machine's network.

# Measurement of 13 October 2026

* 12 of 13 apps compared with the published release, with the version read from the
  executable (GridCraft from the recorded fingerprint). `figcraft` is installed and the
  launcher's `releases.json` names its repository, but the feed does **not** list it yet:
  for it the line is an `absent`, not an "aligned".
* **Byte for byte**: SoundCraft 0.6.1 — the installed `soundcraft-cli.exe` and the one
  inside `soundcraft-0.6.1-windows-x64-portable.zip` have the same `sha256`
  (`915ee3abb121b7b9...`), and the downloaded archive matches its published digest
  (`cd5f8d98257f7711...`). The other 11 apps have no archive on disk: they are a `nota`
  with the command to fetch it, not a missed comparison.
* **Negative test**: one extra byte in the cached archive → `FIX byte soundcraft: non e'
  quello pubblicato: a4228f8080b2... != cd5f8d98257f...`, exit 1.
* 12 of 13 apps compared: `pdfcraft` 0.7.1 too, since the bridge serves it with the
  [translator](craft-bridge-ui.md) — the translator's apps are not in the shim table, so
  the table compared with the feed is the one of the apps **served by the bridge**
  (`CONFIG.bridge_table()`).
* 1 feed entry outside the bridge: `artcraft-launcher` 0.3.2 (it is the launcher, not an
  app to drive).
* Downloads folder empty: no bytes to compare, and this is **not** a success, it is a
  declared gap.

# What it does not do

* It downloads nothing on its own: only with `--download <slug>`, one app at a time, from
  the feed hosts (GitHub) and over `https`. The published `sha256` is verified **before**
  the file is used, and it stays `.parte` until it matches.
* It does not apply to every container: an MSI, a .dmg, a .deb, an .rpm or an AppImage
  cannot be opened with the standard library, so for those apps the bytes stay
  uncompared and the line says so. On Windows this means the answer comes from the
  **portable** package, which is always published.
* It does not decide whether an update should happen now: it says one is available. Inside
  [craft-bridge-doctor](craft-bridge-doctor.md) an app behind is a `nota`, not a `FIX`,
  because the bridge works with the previous version too.
* The other feed paths (macOS, Linux) are the ones **expected** by those platforms, not
  measured on this machine: elsewhere use `--feed-dir`.

# Relations

- **uses** [craft-bridge-ident](craft-bridge-ident.md) for the installed build
- **used by** [craft-bridge-doctor](craft-bridge-doctor.md) - the `pubblicato` line of the verdict
- **proved by** [craft-bridge-tests](craft-bridge-tests.md) - three cases: comparison with a fake feed, bytes against fake archives, exit 3 on feed errors
- **it downloads according to** [Safety rules](../operations/safety-rules.md) - hosts, digest, cache
- **same app table as** [craft-bridge-mcp](craft-bridge-mcp.md) - no second table
