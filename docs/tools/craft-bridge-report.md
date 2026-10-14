---
type: Tool
title: "craft-bridge-report - the whole state in one JSON and one HTML page"
description: "Collects the doctor verdict, the config entries, the MCP clients found, the last suite baseline, the feed comparison and the tail of the launch logs into reports/bridge-status.json and the page reports/bridge-status.html that reads it."
resource: ../../tools/craft-bridge-report.py
tags: [tool, report, visualization]
generated: { by: process:freebuff-buffy, at: 2026-10-14T08:15:00Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-report.py
  title: source
- resource: ../../docs/architecture/reports.md
  title: where the generated artefacts go
- resource: ../../docs/operations/diagnosis.md
  title: the commands it collects
---

# What it does

The reports of the project are many and each has its own shape: right, because each
answers a different question. To *look* at the bridge today, though, you want one place.
This tool gathers the sources **without duplicating them** and writes two files:

| File | Content |
|---|---|
| `reports/bridge-status.json` | the data (`schema`: `craft-bridge-status/1`): verdict, config, clients, baselines, feed, logs |
| `reports/bridge-status.html` | one self-contained page that **reads** the JSON beside it and shows it |

Nothing here is a second measurement: the verdict is `craft-bridge-doctor.py`'s own
`--json`, the clients come from [craft-bridge-connect](craft-bridge-connect.md), the
baselines are the files the suite writes, and the feed is `craft-bridge-feed.py --json`.
If a source cannot be read it is a missing section, not a fatal error.

# The page reads the JSON

`bridge-status.html` does `fetch('bridge-status.json')` and, when the browser does not
allow it (opened as a `file://`), falls back to the copy it carries inside: so it always
shows something, and served from an origin the page stays aligned with the file. The
fallback is a convenience, not a second source — the JSON is the data.

The page has a verdict banner (green/amber/red), the KPI row, the full doctor table with
the actions, the config entries, the **MCP clients** table (how many bridge entries each
one sees and how many it is missing), the suite baselines with the gate, the feed and the
tail of the launch logs (`~/.craft-bridge/launch-logs/*.log`).

# Interface

```
python tools/craft-bridge-report.py                 # writes both files in reports/
python tools/craft-bridge-report.py --json          # only the JSON to stdout, writes nothing
python tools/craft-bridge-report.py --no-doctor     # skips the diagnosis (~2.4 s), the rest stays
python tools/craft-bridge-report.py --no-live       # diagnosis without the open apps' ports
python tools/craft-bridge-report.py --no-clients --no-feed
python tools/craft-bridge-report.py --out-json X.json --out-html X.html
python tools/craft-bridge-report.py --serve          # writes, then serves and opens the page
python tools/craft-bridge-report.py --serve --port 1418 --no-open
```

# One command for the view

`--serve` writes the two files and then starts a **local server** on the folder of the page,
opens it in the browser and stays listening until Ctrl+C. The reason is the one the panel
teaches: a page served by an origin lets `fetch('bridge-status.json')` work, so the view
shows the JSON beside it and is never stale; opened as a `file://` it falls back to the copy
inside. `--bind` (default `127.0.0.1`), `--port` (default `0`, a free port chosen by the
system) and `--no-open` (print the URL only) adjust it. It is the only mode that keeps
running, and it refuses `--json`: that mode writes nothing, so there would be no page to
serve.

# Measured

On this machine (14 October) the generated JSON carried 14 config entries, 13 known
clients of which **4 present**, both suite baselines and 13 launch logs; the page was
opened served by a local server, verdict `tutto in ordine`. Before the clients were
registered the table showed `claude-desktop` and `antigravity` at **12 of 13** and
`windsurf` at **0** — the gap `craft-bridge-connect` closes; after `--apply` all four
read **13/13, 0 missing**. The suite case `report di stato` reads the JSON (schema and
entries) and checks the page fills its data placeholder. `--serve` is proven for real by the
case `report --serve`: on temporary files, it starts the server, waits for the port, GETs the
page (200, and `Craft Bridge` in it) and the JSON (the expected schema), then stops it.

# The page CI hands you

Every run of [checks.yml](../operations/ci.md) regenerates the two files and publishes them as an
artifact - `bridge-status` from the hosted job, `bridge-status-selfhosted` from the machine that has
the bridge - so a push leaves a view to download (`gh run download --name bridge-status`) instead of
a state to reconstruct. The hosted one runs with `--no-live`, because there is no app port to ask
there; the step is `if: always()` and never fails the job, since a page that cannot be written is not
a fault of the bridge.

# Exit codes

| Exit | Meaning |
|---|---|
| 0 | report written (even if the bridge has something to fix: the verdict says so) |
| 2 | usage error (e.g. `--serve` together with `--json`) |
| 3 | the files could not be written, or the server did not start (address in use) |

# Relations

- **it collects the verdict of** [craft-bridge-doctor](craft-bridge-doctor.md)
- **the clients of** [craft-bridge-connect](craft-bridge-connect.md)
- **the baselines of** [craft-bridge-tests](craft-bridge-tests.md)
- **the comparison of** [craft-bridge-feed](craft-bridge-feed.md)
- **it lives with** [Reports and baseline](../architecture/reports.md)
- **published as an artifact by** [Continuous integration](../operations/ci.md)
- **read in** [Diagnosis and verification](../operations/diagnosis.md)
