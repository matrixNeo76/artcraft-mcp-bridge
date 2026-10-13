---
type: Tool
title: "Exploratory tools: recon, probe, pilot"
description: "The three tools with which the bridge was discovered and then demonstrated: recon reads the binaries, probe queries any MCP server, pilot drives the app and saves the artifacts."
resource: ../../tools/craft-bridge-recon.py
tags: [tool, exploration, recon, probe, pilot]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-recon.py
  title: recon
- resource: ../../tools/craft-bridge-probe.py
  title: probe
- resource: ../../tools/craft-bridge-pilot.py
  title: pilot
- resource: ../../docs/reference/craft-bridge.md
  title: complete technical manual
---

# craft-bridge-recon

It reads the app binaries (read-only, no app started) and looks for flags and hints of the
control channel: this is how `--control`, the variable names and the ports came out.
`--matrix` shows presence only, `--all-context` more context.

Where the app is, the **system** says: recon asks the shim for the folder registered in
`App Paths` (the same function the bridge uses to find CLI and executable), so an app
that moves is followed without touching anything; `--root` remains the fallback for apps
the system does not register - see [Where the app is](../architecture/app-locations.md).

```
python tools/craft-bridge-recon.py --app gridcraft --json
python tools/craft-bridge-recon.py --matrix --needle control
```

# craft-bridge-probe

A generic MCP probe: it launches any server, performs `initialize`, `tools/list` and
optionally one call, and reports the outcome as JSON. It is used to tell "the server does
not answer" from "the server answers but the tool does not exist".

```
python tools/craft-bridge-probe.py --cmd "<app>-cli.exe" --args mcp --tool ui_screenshot --tool-args '{"max_side":512}'
```

# craft-bridge-pilot

It runs a sequence of calls on the open app and **saves the image artifacts**: it is the
proof that an agent can drive the window, not just list its tools.

```
python tools/craft-bridge-pilot.py --cmd "<app-cli>" --args mcp \
    --step '{"tool":"ui_screenshot","args":{"max_side":512},"artifact":"shot.png"}' \
    --out reports/pilot.json
```

# Relations

- **recon produced** [Control channel](../architecture/control-channel.md)
- **pilot demonstrates** [Shim modes](../architecture/shim-modes.md) on the live window
- **artifacts in** [Reports and baseline](../architecture/reports.md)
- **the full account in** [Technical manual](../reference/craft-bridge.md)
