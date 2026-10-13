---
type: Runbook
title: "Install and repair the bridge"
description: "From nothing to a working bridge, and how to go back: installing the copies, the connector entries, starting the apps, restoring headless."
resource: ../../tools/craft-bridge-config.py
tags: [runbook, installation, restore]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-config.py
  title: installer
- resource: ../../tools/craft-bridge-launch.py
  title: startup
- resource: ../../docs/reference/craft-bridge.md
  title: complete technical manual
---

# Install the copies and the entries

```
# 1. what would change (no writing)
python tools/craft-bridge-config.py

# 2. apply: copies the shim, ident and the window translator into
#    %LOCALAPPDATA%\Programs\craft-bridge and rewrites the entries in
#    ~/.agents/mcp.json (automatic backup)
python tools/craft-bridge-config.py --apply

# 3. In Freebuff: Connectors -> Refresh
```

Closed apps remain usable in headless; those opened with the control channel become
driveable.

# Start the apps with the channel active

```
python tools/craft-bridge-launch.py                        # every app in the config
python tools/craft-bridge-launch.py --apps gridcraft --verify
python tools/craft-bridge-launch.py --apps pdfcraft --verify # the one served by the translator
```

PhotoCraft needs the token file written by the app (`~/.craft-bridge/photocraft.token`):
for the other apps the first command is enough.

# Going back

```
python tools/craft-bridge-config.py --restore    # headless entries, as before the bridge
```

# Checking that everything is in place

```
python tools/craft-bridge-doctor.py        # one verdict on the assembly
python tools/craft-bridge-verify.py        # every entry with its real command
python tools/craft-bridge-mcp.py --flags   # every CLI confirms the attach flag we declare
```

# Relations

- **installs** [craft-bridge-config](../tools/craft-bridge-config.md)
- **starts** [craft-bridge-launch](../tools/craft-bridge-launch.md)
- **explains the two places** [Installed, source and global MCP](../architecture/installation-layout.md)
- **if something does not add up** [Diagnosis and verification](diagnosis.md)
