---
type: Mechanism
title: "Generated reports and comparison between runs"
description: "Every generated artefact lives in reports/ and that is the tools' default; the suite compares the current run with the saved baseline of the same mode, and a worsening stops the run."
resource: ../../reports/craft-bridge-tests.json
tags: [report, baseline, comparison]
generated: { by: process:freebuff-buffy, at: 2026-10-13T19:55:00Z }
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
| `reports/craft-bridge-tests.json` | fault suite, complete run | cases, outcomes, duration, tool fingerprints, comparison, regressions |
| `reports/craft-bridge-tests.md` | fault suite, complete run | the same data in readable form, with the comparison and regression sections |
| `reports/craft-bridge-tests.static.json` (`.md`) | fault suite, `--static` | the same, for the cases that start no app |
| `reports/craft-bridge-tests.ci.json` (`.md`) | fault suite, `--ci` | the same, for a run where the absent environment is skipped with a reason |
| `reports/craft-bridge-tests.only-<filter>.json` (`.md`) | fault suite, `--only` | the same, for one filter (with `--static` and `--ci` the parts add up: `.static.only-x.ci.json`) |
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

# One baseline per mode

A single name for every mode does not hold: `--static` or `--only` would overwrite the
complete baseline with a partial run, and from then on the comparison (and the CI job that
reads the committed file) would look at something that no longer describes the whole. So the
name carries the mode, and each mode compares with its own - which is what makes the gate on
regressions apply to a `--static` run too, instead of refusing every list as "different modes".
An explicit `--report` writes exactly where it is told, with no suffix: it is a decision, not a
default, and it is how a one-off comparison gets its own file.

Two of those files are kept in the repo on purpose, because they are the baselines CI and the
pre-push check measure against: the complete one and the static one. The `.ci` and
`.only-*` files are transient (in CI they are written inside the checkout and disappear with
it), and it is not a fault if they are not there: a run without a baseline says so and does
not decide.

# Relations

- **produced by** [craft-bridge-tests](../tools/craft-bridge-tests.md)
- **produced by** [craft-bridge-sweep](../tools/craft-bridge-sweep.md)
- **produced by** [report-mcp-tools](../tools/report-mcp-tools.md)
