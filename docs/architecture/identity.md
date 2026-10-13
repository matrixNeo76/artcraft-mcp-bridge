---
type: Mechanism
title: "App identity and the build that is running"
description: "Two distinct questions: who answers on the port (command catalogue, 0.9 threshold) and which version is really running (PID, executable, startup line, builds.json)."
resource: ../../tools/craft-bridge-ident.py
tags: [identity, build, measurement]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-ident.py
  title: implementation
- resource: ../../tools/craft-bridge-doctor.md
  title: who uses it for the verdict
- resource: ../../tools/craft-bridge-tests.py
  title: the suite that exercises the tools
---

# Who answers

Opening a channel is not enough: the right port may be occupied by another app. Identity
is established by comparing the **command catalogue** declared by the peer with that of
the expected app:

| Coverage | Meaning |
|---|---|
| 1.00 | it is the right app |
| <= 0.15 | it is another app |

Below the 0.9 threshold the peer is not considered to be this app: the shim goes headless
and the launcher exits 1.

# Which build

The version is not asked to the catalogue: it is read from the **process that is
listening** (the port's PID), from that process's executable and from the startup line the
app writes by itself into its log. `--record` stores the digest in
`~/.craft-bridge/builds.json`, so the next comparison is against a known value rather than
against itself.

Measured on two real builds of the same app (0.5.0 against 0.6.1): the catalogue coverage
stays at **1.00** — to per-app identity it is "the right app" — and the build comes out
`different`, with `ident` and the launcher exiting 1.

# Declared limit

The executable says the **version**, not the content: two builds with the same version and
no revision in the startup line are indistinguishable. The comparison is not an integrity
check (there is no hash of the binary).

# Relations

- **used by** [Shim modes](shim-modes.md) - so as not to drive the wrong app
- **used by** [craft-bridge-doctor](../tools/craft-bridge-doctor.md) - for the verdict on the ports
- **proved by** [craft-bridge-tests](../tools/craft-bridge-tests.md) - injected build 0.5.0 and wrong app
- **used by** [craft-bridge-launch](../tools/craft-bridge-launch.md) - `--verify`, `--record-builds`
