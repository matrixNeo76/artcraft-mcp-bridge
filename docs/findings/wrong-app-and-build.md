---
type: Finding
title: "Wrong app and different build on the port"
description: "Opening the channel is not enough: the port may belong to another app or to another version. Identity is proved with the command catalogue, the version with the process that is listening."
resource: ../../tools/craft-bridge-ident.py
tags: [defect, identity, build]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-ident.py
  title: what detects it
- resource: ../../docs/architecture/identity.md
  title: the mechanism
---

# Wrong app

The expected port may be occupied by another Crafting App. Measured: the right app covers
**1.00** of its own command catalogue, any other stays **below 0.15**. With the wrong app
the shim goes headless and the launcher exits 1.

# Different build

Measured with a second real build of the same app (0.5.0 against 0.6.1) on 0.6.1's
expected port: the catalogue coverage stays at 1.00 - to per-app identity it is "the right
app" - but the build comes out `different`, with `ident` and the launcher exiting 1, and
the shim warning at startup yet proceeding bridged.

The case where the executable is updated **underneath** the process was tried too: the
version declared by the process wins, with the note that the file on disk is now something
else.

# Remaining limit

The executable says the version, not the content: two builds with the same version - and no
revision in the startup line - are indistinguishable. It is not an integrity check: there
is no hash of the binary.

# Coverage

The *different build* and *other app on the port* cases in the
[fault suite](../tools/craft-bridge-tests.md).

# Relations

- **mechanism in** [Identity and build](../architecture/identity.md)
- **used by** [craft-bridge-doctor](../tools/craft-bridge-doctor.md) and [craft-bridge-launch](../tools/craft-bridge-launch.md)
