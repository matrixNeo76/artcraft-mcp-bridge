---
type: Tool
title: "craft-bridge-doctor - one verdict on the assembly"
description: "Checks repo, installed copies, config entries, executables, PdfCraft window, credentials and listening builds; at the end it lists the actions that fix the problems found."
resource: ../../tools/craft-bridge-doctor.py
tags: [tool, diagnosis, verdict]
generated: { by: process:freebuff-buffy, at: 2026-10-14T10:40:00Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-doctor.py
  title: source
- resource: ../../docs/reference/craft-bridge.md
  title: complete technical manual
- resource: ../../tools/craft-bridge-tests.py
  title: the suite that exercises the tools
---

# What it does

Eleven checks in one command, each `ok` / `FIX` / `nota`: repo, installed copies, config
entries, the paths they mention, the app executables, **where the app is** (the
`App Paths` registry against the table), **the attach flag** (does the CLI help name what
the table uses?), **the PdfCraft window** (does the
[translator](../tools/craft-bridge-ui.md) answer? and are its methods the ones the app
declares?), **what the vendor publishes** against what is installed, the **other MCP
clients**, and - on the listening ports - who answers and which build runs there.

The comparison with the published release looks at the apps the bridge **serves**, not
only the ones of the shim: the translator's ones are there too (`pdfcraft`).

The installed copies it watches are **three**, not two: `craft-bridge-mcp.py`,
`craft-bridge-ident.py` and `craft-bridge-ui.py` (the PdfCraft translator). The
`shim installato` check accuses a repo file newer than the installed one for the third as
well, and the action is always `--apply`.

Two of these are not possible faults. The `pubblicato` line: an app behind the launcher's
release stays a `nota` with the action "update from the launcher", because the bridge
works with the previous version too, and a missing launcher does not change the verdict
because without a feed there is no term of comparison (details in
[craft-bridge-feed](craft-bridge-feed.md)). And the `posizione app` line: when the
registry and the hand-written table point at different folders the line says which ones,
and the action is **align the table** - the path actually used stays the system's - see
[Where the app is](../architecture/app-locations.md).

The `flag di aggancio` line is the most direct of the three: the bridge runs
`<cli> mcp --connect PORT` at every start, so the flag the table declares **must** be the
one the CLI accepts. Here the question is put to the CLI help (one per app, ~0.7 s in
total): if the table claims an option the help does not name, or if the help names one the
table does not use, it is a `FIX` with the action `--flags`; a CLI that prints no help is
not an `ok`, it is a `nota` that says so. Measured: **13/13** confirmed - 12 attaches and
1 for translation. Details in [craft-bridge-mcp](craft-bridge-mcp.md).

The `finestra pdfcraft` line has three outcomes too, and the reason is the same: that the
window is not there is **not** a fault (the entry falls back to the vendor's headless
server), so there the verdict is a `nota` with the action to open it; it is a `FIX`
instead if the translator does not answer at all, because then the entry does not start.
When the window is there, the line compares the **15 methods** of the table with the ones
the app declares: it is the only thing no one else can do, because the table is a copy of
what the app says it can do.

The `client MCP` line answers the question the user actually asks - "does my Claude / Cursor
/ `dsh` see the bridge?": for every client present on the machine it counts how many of the
entries the [connector](craft-bridge-connect.md) would write are **there as bridge entries**
(naming the shim or the translator). An entry left **headless** by the vendor's installer
does **not** count - and that is exactly the fault found on this machine, twice: Claude
Desktop and Antigravity sat at 12/13 with the vendor CLI, and Claude Code was at 12/13 too
while `figcraft` was missing altogether. The counting is `craft-bridge-connect.py`'s own (one
definition, so the diagnosis and the connector cannot diverge); `agents` stays out, because
its config is checked exactly by `config`. The action is
`python craft-bridge-connect.py --apply`; a client that is not installed is not a fault, and
with no client besides `.agents` the line is a `nota`.

For Claude Code and every file-based client the check **reads the file**; the one that used to
be unreadable was Claude Code, whose entries live in `~/.claude.json` under the user scope:
without that reading its row was invisible (not even counted as present) and a leftover
headless entry could stay there forever. Present means "the client is here": the **folder**
for a file-based client, the **executable** for Claude Code, which has no folder of its own.
Measured after `--apply` on this machine: `6 client presenti, tutti con le 13 entry del ponte
(claude-desktop, claude-code, cursor, windsurf, antigravity, vscode-editor)`. A file that is
not there gives **no set** (nothing to accuse); a config that cannot be read is a `nota` that
says so.

Then at the end it puts **only the problems, numbered, with the action that fixes each**.
The doctor changes nothing by itself: it advises, and you run the action (or the suite
does).

# Interface

```
python tools/craft-bridge-doctor.py                # everything, open apps included
python tools/craft-bridge-doctor.py --no-live      # skips the ports (~1 s)
python tools/craft-bridge-doctor.py --json         # checks / problems / actions
python tools/craft-bridge-doctor.py --install-dir <dir> --config <file>
python tools/craft-bridge-doctor.py --feed-dir <folder>   # test launcher feed
python tools/craft-bridge-doctor.py --apps-file table.json  # test table (diagnosis)
python tools/craft-bridge-doctor.py --client-path cursor=f.json  # a client's file (tests)
```

# Test tables are the whole world

With `--apps-file` the injected table **is everything that run sees**: the checks that read
the table (flags, published release, paths) look only at it, and the translator's apps are not
added on top. Mixing them would make the same case give one verdict here and another on a
machine without apps - and it happened: the `flag di aggancio` line also read the machine's
`pdfcraft`, so on a bare CI runner it came out as `nota` where the injected table had every
right to be `ok`.

# Exit codes

| Exit | Meaning |
|---|---|
| 0 | nothing to fix |
| 1 | at least one problem (the actions say which) |
| 2 | usage error |
| 3 | unreadable config or app table |

# Cost

~2.7 s with the apps closed: ~0.8 s for the thirteen CLI helps (one per app served by the
bridge, the most expensive part), and the rest for the comparison with the feed and the
executable versions, which are read once and used by two checks. A few seconds more with
apps open (one catalogue read per occupied port).

# Relations

- **uses** [craft-bridge-ident](craft-bridge-ident.md) for the question about the build
- **uses** [craft-bridge-config](craft-bridge-config.md) for the expected entries (a single source)
- **uses** [craft-bridge-feed](craft-bridge-feed.md) for the published release, against the installed build
- **asks the shim** [craft-bridge-mcp](craft-bridge-mcp.md) for the declared attach flag, and the CLI whether it is true
- **watches** [craft-bridge-ui](craft-bridge-ui.md) - installed copy and catalogue of the PdfCraft window
- **counts the entries of the other clients with** [craft-bridge-connect](craft-bridge-connect.md) - one definition for both
- **it takes the paths from** [Where the app is](../architecture/app-locations.md) - the system registry, with the table as confirmation
- **verified by** [craft-bridge-tests](craft-bridge-tests.md) - every `FIX` proved by injecting the fault
- **in the runbook** [Diagnosis and verification](../operations/diagnosis.md)
