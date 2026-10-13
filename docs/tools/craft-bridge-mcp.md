---
type: Tool
title: "craft-bridge-mcp - the stdio shim"
description: "The MCP server Freebuff starts: it chooses bridged or headless with the handshake and forwards the requests to the live app."
resource: ../../tools/craft-bridge-mcp.py
tags: [tool, shim, stdio]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-mcp.py
  title: source
- resource: ../../docs/reference/craft-bridge.md
  title: complete technical manual
- resource: ../../docs/architecture/shim-modes.md
  title: the bridged/headless decision
---

# What it does

It is the voice registered in `~/.agents/mcp.json` for every app. It speaks MCP on stdio
and forwards to the app when the bridge is there, otherwise it runs the headless CLI.

# Interface

```
python tools/craft-bridge-mcp.py --slug gridcraft --port 7975
python tools/craft-bridge-mcp.py --slug photocraft --port 7976 --token-file ~/.craft-bridge/photocraft.token
python tools/craft-bridge-mcp.py --dump-apps      # app table (JSON), paths resolved by the system
python tools/craft-bridge-mcp.py --flags          # the attach flag, asked of every CLI
python tools/craft-bridge-mcp.py --slug gridcraft --require-bridge
```

| Option | Meaning |
|---|---|
| `--slug` | app to serve (chosen from the internal table) |
| `--port` | control channel port |
| `--token-file` | control-token file (PhotoCraft only) |
| `--host` | host of the probe (default `127.0.0.1`) |
| `--require-bridge` | exits 3 if the bridge is not there, instead of falling back |
| `--dump-apps` | prints the app table and exits |
| `--flags` | compares the table's attach flag with every CLI help, and exits (`1` if one diverges) |
| `--flag-timeout` | seconds for one CLI help (default 20) |

# The table: it declares, it does not decide

`--dump-apps` does not merely print what is written in the file: for every app it resolves
the CLI path from what **the system** registers (`App Paths`, written by the app's
installer) and uses the table as a confirmation. Every entry carries where the path comes
from, so a divergence is visible instead of staying hidden:

| Field | Meaning |
|---|---|
| `cli` | the CLI to use |
| `cli_source` | `registro App Paths (utente|macchina)`, `tabella`, or `tabella (assente sul disco)` |
| `declared_cli` | what the table declares |
| `app_exe` | the app executable as the system registers it (`null` if there is none) |
| `app_hive` | which hive `app_exe` comes from: `utente` (`HKCU`) or `macchina` (`HKLM`) |

The full rule and the reasoning are in [Where the app is](../architecture/app-locations.md).

# The attach flag, asked of the CLI

The bridge **flag** is a declaration too: the table says `--connect` or `--bridge`, and for
the app served by the translator it says there is no flag at all. It is what the bridge
executes at every start (`<cli> mcp --connect PORT`), so it is worth asking the party
concerned instead of remembering it: `--flags` launches each CLI's `--help` and compares.

| Outcome | Meaning |
|---|---|
| `ok` | the CLI help names the flag the table uses (or, for the app with no attach, names none and documents the channel used instead) |
| `diverge` | the table claims an option the help does not name - or the help names one the table does not use: the app changed, or the table is old |
| `non leggibile` | the CLI prints no help: the flag stays a declaration, and it is written down as one |

# Declared limit of this proof

The question is put to the **help**, not by trying the command: it is a reading, not a
connection. Two consequences, stated rather than hidden:

* a CLI that accepts the flag but does not document it would come out as `diverge`;
* the flag is looked for in the **whole** help, not only in the `mcp` line: for LightCraft
  that is the only way (it prints `mcp [OPTIONS]` and documents `--connect` in the options
  section), but a flag documented for another subcommand would count as a confirmation.

This is why the verdict is one diagnosis line and not a proof of operation: the proof that
the bridge works remains a successful call on the window. Measured on 13 October 2026:
**11/11** CLIs document the declared flag (seven `--connect`, four `--bridge`), and
`pdfcraft` names neither but documents `ui --control FILE` - that is, the same thing the
table claims, and the reason its window goes through the
[translator](craft-bridge-ui.md) instead of an attach. The complete verdict is a line of
the [doctor](craft-bridge-doctor.md), which repeats it: a table not confirmed by the CLI
is a `FIX`, not a silence.

# Rule about faults

A network error **does not raise**: what was read is returned and the verdict arrives all
the same. The opposite scheme (letting the exception through) could have lost the MCP
server at startup - see [refused credential](../findings/auth-refused-crash.md).

# Relations

- **it decides according to** [Shim modes](../architecture/shim-modes.md)
- **the attach flag is verified by** [craft-bridge-doctor](craft-bridge-doctor.md) - against the help of every CLI
- **it talks with** [Control channel](../architecture/control-channel.md)
- **it resolves paths according to** [Where the app is](../architecture/app-locations.md)
- **installed by** [craft-bridge-config](craft-bridge-config.md)
- **declared by** [craft-bridge-verify](craft-bridge-verify.md)
