---
type: Design Decision
title: "Bridged or headless: how the shim chooses"
description: "The shim does not pretend: it performs the handshake and decides. Absent, mute or foreign peer lead to headless, and it says so on stderr."
resource: ../../tools/craft-bridge-mcp.py
tags: [shim, bridged, headless, decision]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-mcp.py
  title: the stdio shim
- resource: ../../docs/reference/craft-bridge.md
  title: complete technical manual
- resource: ../../tools/craft-bridge-tests.py
  title: the suite that exercises the tools
---

# The choice

At every start of an MCP server the shim:

1. tries the handshake on the port expected for that app and, where needed, with the
   token file;
2. if the peer speaks the protocol **and is the right app** (command catalogue), it goes
   **bridged**: it forwards the requests to the live app;
3. otherwise it goes **headless**, launching `<app>-cli.exe mcp`, and **writes it on
   stderr** instead of staying silent.

`--require-bridge` changes the rule: if the bridge is not there, it exits 3 instead of
falling back. It is for whoever wants the certainty of really driving the window.

The window translator does the same for PdfCraft, whose MCP server has no attach flag at
all: window answering → the 15 window methods; otherwise it delegates to the vendor's
headless server - see [craft-bridge-ui](../tools/craft-bridge-ui.md).

# Why it matters

It is the most insidious defect in the project: with a socket that **accepts the
connection and then stays mute** in place of the app, the shim declared
`modalita' bridged` and the CLI answered `25 tool, nessun errore`. A headless in disguise,
indistinguishable by looking at the tool list. See
[Silent fallback on a mute peer](../findings/silent-fallback.md).

# Cost

The handshake adds one request at startup: milliseconds with the live app, up to ~4.5 s
with a mute peer before declaring headless (doubled timeout).

# Relations

- **decides using** [Control channel](control-channel.md) - the handshake on the protocol
- **recognises the app with** [Identity and build](identity.md) - the catalogue coverage
- **verified by** [craft-bridge-tests](../tools/craft-bridge-tests.md) - mute peer, wrong app, different build
- **declared in** [craft-bridge-verify](../tools/craft-bridge-verify.md) - the real mode of every entry
- **same rule, other app** [craft-bridge-ui](../tools/craft-bridge-ui.md) - the translator for PdfCraft
