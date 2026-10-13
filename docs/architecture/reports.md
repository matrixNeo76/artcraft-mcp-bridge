---
type: Mechanism
title: "Generated reports and comparison between runs"
description: "Every generated artefact lives in reports/ and that is the tools' default; the suite compares the current run with the previous one by itself."
resource: ../../reports/craft-bridge-tests.json
tags: [report, baseline, comparison]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-tests.py
  title: what produces the report with the comparison
- resource: ../../reports/craft-bridge-sweep.json
  title: the sweep report
---

# Where they go

| File | Produced by | Content |
|---|---|---|
| `reports/craft-bridge-tests.json` | fault suite | cases, outcomes, duration, tool fingerprints, comparison |
| `reports/craft-bridge-tests.md` | fault suite | the same data in readable form, with the comparison section |
| `reports/craft-bridge-sweep.json` | sweep | per app: headless tools, bridged tools, app-only names |
| `reports/mcp-tools-report.md` | report-mcp-tools | inventory of the servers and their tools |
| `reports/photocraft-pilot-report.json` | pilot | the steps of the app session and the image artefacts |
| `reports/photocraft-live-*.png` | pilot | the images captured from the live window |
| `reports/okf-graph.html` | `uvx okfgen visualize docs` | the bundle as an interactive graph: nodes, relations, types |

The tools write there by **default**, not into the folder you invoke them from: that way
two runs made from different places stay comparable.

# The comparison

The suite report is also its own baseline: the current run reads the json it is about to
overwrite and derives the differences - cases whose outcome changed, appeared or
disappeared, tool fingerprints - which end up in the markdown and in the `changes` field of
the json. Duration is context, not a difference. To compare any two reports:
`--compare old.json`.

# Relations

- **produced by** [craft-bridge-tests](../tools/craft-bridge-tests.md)
- **produced by** [craft-bridge-sweep](../tools/craft-bridge-sweep.md)
- **produced by** [report-mcp-tools](../tools/report-mcp-tools.md)
