---
type: Tool
title: "craft-bridge-sweep - headless against bridged"
description: "Starts one app at a time and measures the same tools in both modes, to prove that the bridge adds capability on the window instead of replacing the CLI."
resource: ../../tools/craft-bridge-sweep.py
tags: [tool, measurement, comparison]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-sweep.py
  title: source
- resource: ../../reports/craft-bridge-sweep.json
  title: the report it produces
- resource: ../../docs/reference/craft-bridge.md
  title: complete technical manual
---

# What it does

For every app: it runs the headless entry and collects the tools; it starts the app with
the control channel, repeats the same collection in bridged mode, and compares the two
lists - including the **app-only names**, that is the tools that exist only by driving
the live window. Then it closes the app.

# Interface

```
python tools/craft-bridge-sweep.py                     # every app in the config
python tools/craft-bridge-sweep.py --apps gridcraft,photocraft --wait 60
python tools/craft-bridge-sweep.py --skip-tool         # lists only, no call
python tools/craft-bridge-sweep.py --out reports/sweep.json
```

# Outcome

Report in `reports/craft-bridge-sweep.json` (default): for every app the two tool lists,
the app-only names, the startup command used and the outcome of the call.

# Relations

- **it measures the effect of** [Shim modes](../architecture/shim-modes.md)
- **complementary to** [craft-bridge-verify](craft-bridge-verify.md) (which looks at the entries, not the apps)
- **the measurements are told in** [Technical manual](../reference/craft-bridge.md)
