---
type: Finding
title: "Bridged fell back in silence onto a mute peer"
description: "With a socket that accepts and stays mute, the shim declared bridged and the CLI answered 25 tools with no error: a headless in disguise, indistinguishable from the tool list."
resource: ../../tools/craft-bridge-mcp.py
tags: [defect, shim, handshake]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-mcp.py
  title: the fixed code
- resource: ../../docs/architecture/shim-modes.md
  title: the current decision
- resource: ../../docs/reference/craft-bridge.md
  title: complete technical manual
---

# Symptom

In place of the app, a socket that **accepts the connection and then stays mute**. The shim
declared `modalita' bridged`, and the app's CLI answered `25 tool, nessun errore`. Nobody
noticed by looking at the tool list.

# Cause

The mode was not verified: it was enough for the port to be open. A mute peer was treated
as a live peer.

# Fix

The decision is taken with the **handshake**: `peer=silent` or `peer=foreign` lead to
**headless**, and the shim writes it on stderr. The launcher exits 1, `ident` gives the
verdict. `--require-bridge` turns the fallback into exit 3, for whoever wants certainty.

# How it is covered today

The *closed port* case and the cases with a mute/foreign peer in the
[fault suite](../tools/craft-bridge-tests.md).

# Relations

- **current rule in** [Shim modes](../architecture/shim-modes.md)
- **measured with** [craft-bridge-ident](../tools/craft-bridge-ident.md)
- **narrated in** [Technical manual](../reference/craft-bridge.md)
