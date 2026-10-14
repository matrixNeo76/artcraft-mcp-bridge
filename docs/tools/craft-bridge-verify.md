---
type: Tool
title: "craft-bridge-verify - every entry with its real command"
description: "Reads the config and queries every entry by running exactly the command written there - shim included - and reports the mode, the available tools and the outcome of a call."
resource: ../../tools/craft-bridge-verify.py
tags: [tool, verification, entries]
generated: { by: process:freebuff-buffy, at: 2026-10-14T10:40:00Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-verify.py
  title: source
- resource: ../../docs/reference/craft-bridge.md
  title: complete technical manual
---

# What it does

It does not trust the config: it **runs** it. For every entry it launches the command
written in the file, performs the MCP handshake, asks `tools/list` and - if requested -
calls a tool.

It is the proof that the real path (Freebuff starting the shim) works: 14/14 entries
verified last time, **13 with a bridge** (12 through the shim, `pdfcraft` through the
[translator](craft-bridge-ui.md)).

# The mode is read, for PdfCraft too

The stderr of the entries that choose between window and headless is read to say in which
mode they started: this holds for the shim **and** for the PdfCraft translator, which
writes the same line. Measured: with the window open `pdfcraft modo=bridged tool=15`; with
an `--expect headless` the same line becomes a KO, so the mode is verifiable there too.
The entries that have no mode (`artcraft`, protocol proxy) stay `modo=n/a` and `--expect`
does not concern them.

# Interface

```
python tools/craft-bridge-verify.py                       # every entry
python tools/craft-bridge-verify.py --expect bridged      # demands the bridge
python tools/craft-bridge-verify.py --only gridcraft,photocraft
python tools/craft-bridge-verify.py --skip soundcraft
python tools/craft-bridge-verify.py --tool ui_screenshot --tool-args '{"max_side":512}'
```

`--config FILE` reads the file the way the **client** writes it: `mcpServers` for most,
`servers` for VS Code (editor and workspace). So the entries of a client file can be
proven, not only those of `~/.agents/mcp.json`: measured on `cadcraft`, `figcraft` and
`pdfcraft` taken from the Cursor file, from `%APPDATA%\Code\User\mcp.json` and from
`~/.claude.json` — 3/3, 3/3 and 2/2 `OK`, all through the bridge. A file with neither key
says which keys it has, instead of dying with a `KeyError`.

# Exit codes

| Exit | Meaning |
|---|---|
| 0 | every verified entry answered |
| 1 | at least one entry does not answer or is not in the expected mode |
| 3 | the config cannot be read, or it holds no `mcpServers`/`servers` key |

# Relations

- **it verifies** [craft-bridge-mcp](craft-bridge-mcp.md) through the real config
- **and the translator** [craft-bridge-ui](craft-bridge-ui.md) - it reads its mode as it does for the shim
- **complementary to** [craft-bridge-doctor](craft-bridge-doctor.md) (the assembly) and to [craft-bridge-sweep](craft-bridge-sweep.md) (per app)
- **in the runbook** [Diagnosis and verification](../operations/diagnosis.md)
