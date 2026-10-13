---
type: Protocol
title: "Control channel of the Crafting Apps"
description: "The JSON-lines protocol the apps open with --control: messages, credential, expected ports and measured pitfalls."
resource: ../../tools/craft-bridge-ident.py
tags: [protocol, ports, control-channel]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-ident.py
  title: implementation of the handshake
- resource: ../../tools/craft-bridge-mcp.py
  title: the shim that uses it
- resource: ../../docs/reference/craft-bridge.md
  title: complete technical manual
---

# What it looks like

An app started with `--control <port>` opens a TCP socket on `127.0.0.1:port` and speaks
**JSON-lines**: one JSON line per message, with `id`, `method`, `params`, and a `result`
or `error` reply.

Before asking anything, a **handshake** is performed: it is what tells whether behind the
port there is an app speaking this protocol, a stranger (an HTTP server, for instance) or
silence. That is why the shim no longer falls back silently on a mute peer.

# Credential

PhotoCraft requires a token: the app **writes it itself** into
`~/.craft-bridge/photocraft.token`, and the config passes it with
`--control-token-file`. The value is never printed by the tools: only the outcome of the
`auth` call is read.

# Expected ports

| App | Port | App | Port |
|---|---|---|---|
| cadcraft | 7971 | soundcraft | 7977 |
| deckcraft | 7972 | wordcraft | 7978 |
| designcraft | 7973 | vectorcraft | 7979 |
| filmcraft | 7974 | lightcraft | 7980 |
| gridcraft | 7975 | effectcraft | 9877 |
| photocraft | 7976 | | |

The last three are the defaults documented by the respective CLIs; the others come from
the shim table, which is a **single source** for config and diagnosis (`--dump-apps`).

# Measured pitfalls

* The end of a message must be recognised by **parsing**, not by looking for a newline:
  the apps leave a stray `\n` after the previous reply, and stopping there made the code
  read an empty byte instead of the catalogue (identity "unknown" at intervals).
* The command catalogue is a large body (100-120 KB measured): with the lean handshake
  timeout, under load the reply did not arrive in time. For the catalogue the deadline is
  wider.
* A refused credential makes the app **close the connection**: the next write raises
  `ConnectionAbortedError` - see [the defect](../findings/auth-refused-crash.md).

# Relations

- **used by** [Shim modes](shim-modes.md) - to decide the mode and to talk with the app
- **queried by** [craft-bridge-ident](../tools/craft-bridge-ident.md) - identity and build
- **proved by** [craft-bridge-tests](../tools/craft-bridge-tests.md) - mute peer, foreign peer, refused credential
