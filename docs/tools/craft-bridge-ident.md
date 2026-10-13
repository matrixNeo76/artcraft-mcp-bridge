---
type: Tool
title: "craft-bridge-ident - who answers and which build"
description: "Answers two questions: who is listening on a port (an app recognised by its command catalogue) and which version is running there (PID, executable, command line)."
resource: ../../tools/craft-bridge-ident.py
tags: [tool, identity, build]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-ident.py
  title: source
- resource: ../../docs/architecture/identity.md
  title: the mechanism
- resource: ../../docs/reference/craft-bridge.md
  title: complete technical manual
---

# What it does

It opens the channel, performs the handshake, asks for the command catalogue and compares
it; then it reads the listening process for the build. It is the expert that `doctor`,
`launch` and the shim question when there is a doubt about who is talking.

# Interface

```
python tools/craft-bridge-ident.py --slug gridcraft        # one app (port inferred)
python tools/craft-bridge-ident.py --all                   # every port of every app
python tools/craft-bridge-ident.py --all --json
python tools/craft-bridge-ident.py --slug gridcraft --expect-version 0.6.1   # exit 1 if different
python tools/craft-bridge-ident.py --slug gridcraft --record                  # records the fingerprint
```

| Option | Meaning |
|---|---|
| `--slug` / `--port` | a single target |
| `--all` | every app in the config |
| `--config` | config to use (default `~/.agents/mcp.json`) |
| `--token-file`, `--token-field` | PhotoCraft credential (`token` or `key`) |
| `--timeout`, `--wait` | wait for the answer / for the channel to appear |
| `--no-identity`, `--no-build`, `--build-only` | they select the question |
| `--expect-version` | demands an exact version |
| `--record` | writes the fingerprint to `~/.craft-bridge/builds.json` |
| `--json` | JSON only |

# Exit codes

| Exit | Meaning |
|---|---|
| 0 | peer recognised, build consistent |
| 1 | port closed / foreign peer / wrong app / different build |
| 2 | usage error |
| 3 | unreadable config or table |

# Relations

- **the mechanism in** [Identity and build](../architecture/identity.md)
- **used by** [craft-bridge-doctor](craft-bridge-doctor.md), [craft-bridge-launch](craft-bridge-launch.md)
- **proved by** [craft-bridge-tests](craft-bridge-tests.md)
