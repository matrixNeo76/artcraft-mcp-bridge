---
type: Tool
title: "craft-bridge-config - idempotent installer"
description: "Installs the copies of the shim, of ident and of the window translator, rewrites the bridged entries in the connector config with a backup, and realigns the files when the source changes."
resource: ../../tools/craft-bridge-config.py
tags: [tool, installation, config]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-config.py
  title: source
- resource: ../../docs/reference/craft-bridge.md
  title: complete technical manual
- resource: ../../docs/architecture/installation-layout.md
  title: installed against source
---

# What it does

* it installs `craft-bridge-mcp.py`, `craft-bridge-ident.py` and `craft-bridge-ui.py` in
  `%LOCALAPPDATA%\Programs\craft-bridge` (default, overridable with `--install-dir`);
* it rewrites the connector entries in `~/.agents/mcp.json` (default, `--config`), each
  with the right command and the control channel on the expected port - for PdfCraft the
  entry names [the translator](craft-bridge-ui.md), because that app has no fixed port
  and no bridge flag;
* it is idempotent: on the second run it rewrites nothing, and it always says what it
  would change.

# Interface

```
python tools/craft-bridge-config.py                        # shows what would change
python tools/craft-bridge-config.py --apply                # writes (with a backup)
python tools/craft-bridge-config.py --apply --port photocraft=7981
python tools/craft-bridge-config.py --restore              # goes back to the headless entries
python tools/craft-bridge-config.py --json
```

# File alignment

The defect fixed on 13 October: it used to copy the two files **only** if an entry
changed, so with the config already in place the installed copy fell behind. Now it
compares the bytes and realigns - see
[Installed files not aligned](../findings/stale-installed-files.md).

The entries it writes contain no app paths: they name the shim and the port, so an app
that moves does not require rewriting the config. The only exception is `--restore`, which
puts back the vendor's headless entries: there the CLI path is the one resolved by the
system, not a string written by hand - see
[Where the app is](../architecture/app-locations.md).

# Relations

- **it installs** [craft-bridge-mcp](craft-bridge-mcp.md), [craft-bridge-ident](craft-bridge-ident.md) and [craft-bridge-ui](craft-bridge-ui.md)
- **the paths are resolved by** [Where the app is](../architecture/app-locations.md)
- **the full scenario in** [Installed, source and global MCP](../architecture/installation-layout.md)
- **used by the actions of** [craft-bridge-doctor](craft-bridge-doctor.md)
- **proved by** [craft-bridge-tests](craft-bridge-tests.md) on a copy of the config, never on the real one
