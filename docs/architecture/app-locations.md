---
type: Mechanism
title: "Where the app is: the system says it, not the table"
description: "The path of app and CLI is resolved from the App Paths registry (written by the app's installer) and the hand-written table remains as a confirmation; when the two diverge, the diagnosis shows it. Includes what the ArtCraft launcher knows (the releases) and what it does not offer (starting an app)."
resource: ../../tools/craft-bridge-mcp.py
tags: [architecture, paths, registry, launcher]
generated: { by: process:freebuff-buffy, at: 2026-10-13T18:50:00Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-mcp.py
  title: the resolution and the table
- resource: ../../docs/reference/craft-bridge.md
  title: complete technical manual
- resource: ../../tools/craft-bridge-feed.py
  title: the launcher's release side
---

# The problem

The app table declared `C:\Program Files\<App>\<app>-cli.exe` by hand for each of the
twelve apps. The installed configuration contains the app **name**, not its path, so
updating those strings broke no connector: they aged in silence, and nobody would have
noticed until an app moved.

# Who knows what

| Piece | What it knows | Where it says it |
|---|---|---|
| the **system** | where the executable of every installed app is | `...\CurrentVersion\App Paths\<app>.exe`, written by the app's installer: `HKLM` if for everyone, `HKCU` if for the user only |
| the **table** | the CLI, the attach flag, the expected port for each app | `craft-bridge-mcp.py`, written by hand |
| the **launcher** | which releases exist, with which packages and digests | `%LOCALAPPDATA%\ArtCraft Launcher\feed.json`, read by [craft-bridge-feed](../tools/craft-bridge-feed.md) |

None of the three knows what the others know, and none is complete on its own: the system
does not know which app the bridge must drive, the table does not know where the app
ended up, the launcher does not know where it is installed (and does not say it because
that is not its job).

The apps ship as **MSI packages** (the uninstall keys say so: `MsiExec.exe /X{GUID}`, with
the installer writing the `App Paths` entry), so it is the app's package that registers
the path — not the launcher, which merely downloads and runs that installer. Today the
packages are per-machine (`HKLM`), but this ecosystem also knows **per-user** installs:
the launcher itself sits in `%LOCALAPPDATA%` and registers in `HKCU`. That is why both
hives are read, **user before machine**, following the order Windows uses to resolve a
program name: looking only at `HKLM` would hide a per-user install, that is, one more old
path in place of the real one.

# The rule

`app_table()` in [craft-bridge-mcp](../tools/craft-bridge-mcp.md) resolves each slug with
three outcomes, in order of trust, and declares which one it used:

1. the CLI **next to the app the system registers** → `App Paths registry (user|machine)`;
2. the CLI **declared** in the table → `table`;
3. the declared one, which however does not exist → `table (missing on disk)`.

The third case is information, not silence: whoever reads that line knows that the path
leads nowhere. The read uses `winreg`, not PowerShell: this code runs at every MCP
session start, and an extra process would cost as much as the handshake.

# Why we do not start *from* the launcher

The ArtCraft launcher is a graphical application, and on the command line it offers no way
to start a specific app: the only argument it accepts is `--hidden` (start at login
without a window), no URL scheme is registered, and there is no `--install`/`--launch`.
Upstream requests are open — *install cli apps* (#128) and *per-app headless MCP-server
start* (#148): the second asks for exactly what this bridge already does.

And even if that command existed, the path would not come from there anyway: the
launcher's local state is the window and the preferences
(`%APPDATA%\ai.storyteller.artcraft-launcher\data\app.ron`: `window`, `settings`, `egui`
and nothing else) plus the release catalogue cache (`feed.json`, `releases.json`). It does
not keep a list of what is installed and where: it puts that question to the system,
exactly as we do.

So starting stays the app's job, and nothing is duplicated: the table does not dictate the
paths, the system resolves them. The launcher contributes the other half of the question —
*which* release exists and with which digest — which is what
[craft-bridge-feed](../tools/craft-bridge-feed.md) needs to say whether the installed app
is the published one.

# What you see when the two disagree

[craft-bridge-doctor](../tools/craft-bridge-doctor.md) has the `app location` check:

| Outcome | When |
|---|---|
| `ok` | every path comes from the registry: the table confirms, it does not decide |
| `nota` | the system and the table point to different folders, and the line says which: the system wins, and the table must be aligned |
| `nota` | no path from the registry (non-Windows system, or apps installed without registering): the table remains the source |

# Limits

* The registry is Windows-only: elsewhere the table is the only source, and the check
  **says so** instead of staying silent. It is one of the few points porting will have to
  change.
* Both registry views (64 and 32 bit) are tried, but the order is fixed: **user, then
  machine**. If an app were installed for everyone *and* for one user in two different
  folders, the user's wins — the same choice Windows would make, and `cli_source` declares
  it.
* The registry says **where** the app is, not which version is running: the version is
  told by [craft-bridge-ident](../tools/craft-bridge-ident.md) (what is running) and
  [craft-bridge-feed](../tools/craft-bridge-feed.md) (what is published).
* Two installations of the same app, one registered and one not: the registered one wins.
  If the table pointed at the other, the difference shows in the `app location` line; if
  the table never mentioned it at all, there is nothing to compare.

# Relations

- **resolved by** [craft-bridge-mcp](../tools/craft-bridge-mcp.md) - `--dump-apps` carries `cli`, `cli_source`, `declared_cli`, `app_exe`
- **verified by** [craft-bridge-doctor](../tools/craft-bridge-doctor.md) - the `app location` check
- **used by** [craft-bridge-launch](../tools/craft-bridge-launch.md) - the executable to start, not just the CLI
- **proved by** [craft-bridge-tests](../tools/craft-bridge-tests.md) - the three outcomes of the choice, the real paths on this machine and the launcher's per-user hive
- **the other half** [craft-bridge-feed](../tools/craft-bridge-feed.md) - the releases published by the launcher
- **why moving the repo breaks nothing** [Installed, source and global MCP](installation-layout.md)
