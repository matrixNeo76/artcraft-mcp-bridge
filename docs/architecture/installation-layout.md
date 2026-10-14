---
type: Mechanism
title: "Installed, source and global MCP"
description: "The global MCP does not point at this repo but at copies installed in %LOCALAPPDATA%: that is why reorganising or moving the project does not break the connectors."
resource: ../../tools/craft-bridge-config.py
tags: [installation, global-mcp, drift]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-config.py
  title: the installer
- resource: ../../tools/craft-bridge-doctor.py
  title: what detects the drift
- resource: ../../docs/reference/craft-bridge.md
  title: complete technical manual
---

# Two places, two roles

| Where | What | Who uses it |
|---|---|---|
| this repo | source: tools, documentation, reports | whoever develops and verifies |
| `%LOCALAPPDATA%\Programs\craft-bridge` | installed copies of the shim, of `ident` and of the translator | Freebuff, at every MCP server start |
| `%LOCALAPPDATA%\Programs\artcraft-mcp` | ArtCraft generative MCP and conformance proxy | Freebuff |
| `~/.agents/mcp.json` | the 14 connector entries | Freebuff (Connectors panel) |

The config entries point **at the installed copies**, never at the repo. That is why
reorganising or moving this project leaves the connectors untouched: the global MCP keeps
working exactly the same.

# Align, do not duplicate

`craft-bridge-config.py --apply` installs the copies and rewrites the entries (with a
backup). It compares the **files**, not just the entries: if the source changes, it
realigns the copies - see
[installed files not aligned](../findings/stale-installed-files.md).

`craft-bridge-doctor.py` is the drift guard: it says whether the installed copies are
identical to the source and which entries do not match.

# Practical consequence

Whoever changes the shim, `ident` or the translator in the repo must then run
`python tools/craft-bridge-config.py --apply`; otherwise the diagnosis reports - rightly -
that the installed copy is behind.

# Relations

- **managed by** [craft-bridge-config](../tools/craft-bridge-config.md)
- **checked by** [craft-bridge-doctor](../tools/craft-bridge-doctor.md)
- **operating rule in** [Safety rules](../operations/safety-rules.md)
- **install from scratch in** [Install and repair](../operations/install-and-repair.md)
