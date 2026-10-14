---
type: Runbook
title: "Diagnosis and verification of the bridge"
description: "The three levels of checks - one verdict (doctor), real entries (verify), injected faults (tests) - and how to read the reports over time."
resource: ../../tools/craft-bridge-doctor.py
tags: [runbook, diagnosis, verification, reports]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-doctor.py
  title: doctor
- resource: ../../tools/craft-bridge-verify.py
  title: verify
- resource: ../../tools/craft-bridge-tests.py
  title: the suite that exercises the tools
---

# The three levels

| Command | Answers | Cost |
|---|---|---|
| `python tools/craft-bridge-doctor.py` | is the assembly healthy? which actions are needed? | ~2.4 s (apps closed) |
| `python tools/craft-bridge-verify.py` | does every entry in the config really answer? | tens of seconds |
| `python tools/craft-bridge-tests.py` | do the tools see the faults when there are any, and has anything got worse than the baseline? | ~76 s (~36 s with `--static`, 25 of the 29 cases) |
| `python tools/craft-bridge-feed.py` | is the installed app the one the launcher publishes? | ~0.9 s |

# Recommended order

1. `doctor` - if it says `FIX`, run the action it names (often
   `craft-bridge-config.py --apply`), then run it again.
2. `verify` - if an entry does not answer, the problem is in the shim/app path, not in
   the config.
3. `tests` - if you touched shim, ident or doctor, the suite immediately says whether the
   behaviour changed.
4. `feed` - when you suspect the version running is not the published one: it compares the
   two and says which app and which package it is based on. With `--bytes` it goes beyond
   the declaration: it compares the executable with the one inside the published package,
   and `--download <app>` fetches the package (one app at a time).

# Reading the reports over time

The suite compares every run with the previous one: outcomes that changed, cases that
appeared or disappeared, fingerprints of the tools. Look at the *Comparison* section of
`reports/craft-bridge-tests.md`. See [Reports and baseline](../architecture/reports.md).

The section to read first is **Regressioni**: it answers one question - did the suite lose or
contradict something the baseline took for granted? - and the answer decides the exit code
(3). It says "cancello non applicato" with the reason when the comparison would not mean
anything (another host, another mode), which is not the same as "nothing got worse": the
first is *not measured*, the second is *measured and quiet*.

# Typical symptoms

| Symptom | First thing to look at |
|---|---|
| the MCP client sees few tools | the mode chosen by the shim: bridged or headless |
| `pdfcraft` shows 15 tools (or 161) | the mode of the [translator](../tools/craft-bridge-ui.md): window open → the window's 15 methods, closed → the vendor's headless server |
| `pdfcraft` does not appear among the entries verified with the mode | the translator is installed but does not answer: `craft-bridge-ui.py --where`, then reopen the app with the control file |
| `FIX shim installato` | the source is newer than the installed copy: `--apply` (it holds for the PdfCraft translator too) |
| `FIX client MCP: cursor 0/13` | a client present on the machine does not read the bridge (an entry left headless, or no entry at all): `python craft-bridge-connect.py --apply`, then reload the client (see [Connect a client](connect-a-client.md)) |
| `FIX flag di aggancio: fintocraft...` | the table declares a flag the CLI help does not name (or the other way round): look at `craft-bridge-mcp.py --flags`, then align the table (see [craft-bridge-mcp](../tools/craft-bridge-mcp.md)) |
| `nota flag di aggancio: non leggibile per ...` | that CLI prints no help: the flag stays a declaration of the table, not a proof |
| `nota posizione app: sistema e tabella non concordano` | the path used is the system's: align the table (see [Where the app is](../architecture/app-locations.md)) |
| `nota posizione app: nessun percorso dal registro` | a non-Windows system, or apps installed without registering: the table stays the source |
| `FIX porta N: gira una build diversa` | the installed executable is not the configured one |
| `nota pubblicato: il launcher pubblica altro` | there is an update: the bridge works all the same, update from the launcher |
| `nota pubblicato: nessun confronto` | the launcher is missing or its feed cannot be read: it is not a bridge fault |
| `FIX byte <app>: non e' quello pubblicato` | the cached archive does not match its sha256: delete it and download it again |
| `FIX byte <app>: <a> != <b> dentro <archivio>` | the installed executable is not the published one: reinstall the app from the launcher |
| `un'altra app` on the port | the port is taken by a different app: close it or change the port |
| `l'app ha rifiutato la credenziale` | the token in the config is not the app's |

# Relations

- **it uses** [craft-bridge-doctor](../tools/craft-bridge-doctor.md), [craft-bridge-verify](../tools/craft-bridge-verify.md), [craft-bridge-tests](../tools/craft-bridge-tests.md), [craft-bridge-feed](../tools/craft-bridge-feed.md)
- **what is never touched** [Safety rules](safety-rules.md)
- **context of the defects** [Defects found](../findings/silent-fallback.md)
