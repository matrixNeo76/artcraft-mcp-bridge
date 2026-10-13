---
type: Tool
title: "craft-bridge-launch - starts the apps with the channel active"
description: "Starts one or more apps detached from the shell, with --control on the port (or on the file, for PdfCraft) the config expects, waits for the channels in parallel and says who answers (and with which build). The executable to start is the one the system registers, not a path written by hand."
resource: ../../tools/craft-bridge-launch.py
tags: [tool, startup, launcher]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-launch.py
  title: source
- resource: ../../docs/reference/craft-bridge.md
  title: complete technical manual
- resource: ../../tools/craft-bridge-tests.py
  title: the suite that exercises the tools
---

# What it does

It skips the apps whose channel is already up, starts the others **detached from the
shell** (the windows stay open after the command returns) with `--control <port>` and
`--control-token-file` where needed, waits for all the channels in parallel, and asks the
peer who it is for each of them.

# Interface

```
python tools/craft-bridge-launch.py                     # every app in the config
python tools/craft-bridge-launch.py --apps gridcraft,photocraft
python tools/craft-bridge-launch.py --list              # table and state, starts nothing
python tools/craft-bridge-launch.py --dry-run           # shows the commands, starts nothing
python tools/craft-bridge-launch.py --apps gridcraft --verify
```

| Option | Meaning |
|---|---|
| `--apps` | comma-separated slugs (default: every app in the config) |
| `--port slug=port` | a port other than the expected one (repeatable; an app served by the translator has none) |
| `--wait` | seconds to wait per channel (default 45) |
| `--list` / `--dry-run` | start nothing |
| `--verify` | also asks the shim in which mode it would start |
| `--record-builds` | records the fingerprints of the builds encountered |
| `--json` | JSON report |

# Where the path comes from

The port comes from the config (the one the shim will probe), the **executable from the
system registration**: for every app it starts what the installer wrote in `App Paths`,
the same entry Windows uses to open it by name. The internal table stays as a
confirmation - and as a fallback where the registry has nothing. `--list` shows the
`percorso` column, so a divergence is visible at a glance instead of ageing away; the full
rule is in [Where the app is](../architecture/app-locations.md).

The ArtCraft launcher is **not** used to start apps, and not by choice: it offers no
command-line way to do it (no `--install`/`--launch`, no registered URL scheme; upstream
issues #128 and #148 ask for exactly this). The launcher knows which releases exist, not
where they are installed.

# PdfCraft: a different transport, the same question

PdfCraft starts from here too, but its `--control` wants a **file**, not a port: the port
is chosen by the app, which writes it inside the file. So "can it be driven right now?" is
not answered by a fixed port - it is answered by the
[translator](craft-bridge-ui.md), which authenticates with the file's token and says
`bridged` or `headless`. `--list` shows it in a section of its own (columns: slug, port,
transport, mode, app open, why), and `--verify` carries the same idea all the way:

```
python tools/craft-bridge-launch.py --apps pdfcraft --verify
  avvio      : C:\Program Files\PdfCraft\pdfcraft.exe --control C:\Users\...\pdfcraft-control.json
  stato      : bridged (la finestra risponde e autentica)
  canale     : attivo (traduttore: bridged, porta 48129)
  finestra   : 1440.0x920.0 punti (pid 42336)
  catalogo   : 15 metodi , gli stessi che dichiara l'app
```

The apps served by the translator are recognised from the **entry itself** (the one that
names `craft-bridge-ui.py`), not from a list written by hand: that way there is no second
copy of the same information to keep aligned.

# Exit codes

| Exit | Meaning |
|---|---|
| 0 | every requested app has the channel active **and the configured build** |
| 1 | at least one does not: the `diagnosi` line says why, with the tail of the log |
| 2 | usage error (unknown slug, duplicate port) |
| 3 | unreadable config or app table |

# Relations

- **the paths are resolved by** [Where the app is](../architecture/app-locations.md)
- **it starts, for PdfCraft, the app served by** [craft-bridge-ui](craft-bridge-ui.md)
- **it verifies with** [craft-bridge-ident](craft-bridge-ident.md)
- **the config it expects from** [craft-bridge-config](craft-bridge-config.md)
- **proved on every app in** [Technical manual](../reference/craft-bridge.md)
- **in the runbook** [Install and repair](../operations/install-and-repair.md)
