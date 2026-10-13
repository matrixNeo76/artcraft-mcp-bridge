---
type: Tool
title: "craft-bridge-tests - the suite that injects faults"
description: "Twenty-three cases that break something on purpose and demand the right verdict from shim, translator, doctor, ident and launcher; every run leaves a report compared with the previous one."
resource: ../../tools/craft-bridge-tests.py
tags: [tool, tests, faults, report]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-tests.py
  title: source
- resource: ../../reports/craft-bridge-tests.md
  title: the last report
- resource: ../../docs/architecture/reports.md
  title: the report format
---

# What it does

It makes repeatable what had been tried by hand: for every case it **breaks something**
(stale shim, wrong entry, non-existent path, missing executable, table against the system
path, build 0.5.0 on the port, another app on the port, refused credential, closed port,
published/installed feed and bytes, arguments and catalogue of the PdfCraft translator, a
table that declares a flag the CLI help does not confirm), asks the tools for the verdict,
demands the right outcome and puts things back.

Three cases concern the **attach flag**: the six verdicts of the comparison with the CLI
help (on fake CLIs, with no app), the `doctor` line in both directions - a table not
confirmed must be a `FIX` with the action `--flags`, one confirmed by the channel an `ok`,
and an **absent** CLI (what a runner without apps sees) a `nota` - and the measurement on
the real CLIs, where it also checks that the diagnosis says the same thing.

The cost of the `doctor` cases grew with the cost of the tool (~2.4 s per round, because
every check that talks to the CLIs or to the translator costs a process): that is why the
suite asks the doctor **only** what a single line cannot say.

Four cases concern [the window translator](craft-bridge-ui.md) and three of them **need no
app**: a fake PdfCraft answers on the channel the way the real app does (authentication
with the control file's token, `ui.state`, a fake screenshot, a real fault on a label that
does not exist), and it is **shut down mid-session** to demand the diagnosis instead of an
answer that merely looks successful; a fake MCP server plays the part of the vendor's
headless server. The fourth is the live one: if the window is not there it is **skipped
with a reason**, because that is not a fault of the bridge.

# Interface

```
python tools/craft-bridge-tests.py                 # everything (~72 s, starts real apps)
python tools/craft-bridge-tests.py --static        # only the cases without apps (~34 s, 19 of 23)
python tools/craft-bridge-tests.py --only build --json
python tools/craft-bridge-tests.py --report reports/my.json --compare old.json
python tools/craft-bridge-tests.py --static --ci   # on a runner without an installed bridge
```

# `--ci`

It is for a CI runner: if the machine has neither the connector config nor the installed
copies, the cases that talk about the bridge are **skipped with the reason** instead of
failing. A real fault stays a FAIL: the mode changes what an absent environment is, not
what a fault is. The three proofs, all run before publishing it:

1. on a machine with the bridge, `--static --ci` gives **19/19 and no skips** (and 23/23 on
   the whole suite);
2. on a machine with no bridge (this repo's checkout, empty environment), it gives
   **11 passed + 8 skipped** and exits 0;
3. with a real fault injected - one extra byte in the installed copy of the translator -
   the same command gives **FAIL** and exits 1 even with `--ci`, so the mode does not hide
   faults, it only stops calling the absence of a bridge a fault.

See [Continuous integration](../operations/ci.md).

# Report and comparison

Every run writes `reports/craft-bridge-tests.json` (machine) and
`reports/craft-bridge-tests.md` (readable), and compares itself with the previous run:
cases changed, appeared, disappeared, fingerprints of the tools. Duration is context.
`--no-report` writes nothing, `--no-compare` reads nothing.

# Safety rules

The real config is never written (the cases exercise it on a copy with `--config`); the
only real file touched is the **installed** copy of the shim, inside a `try/finally` that
puts it back; apps are started only on free ports, and if a port is occupied the case is
skipped instead of killing someone else's processes; temporaries, logs and test tokens
disappear at the end.

# Exit codes

| Exit | Meaning |
|---|---|
| 0 | every case passed (SKIP is not a fault) |
| 1 | at least one FAIL |
| 2 | usage error |

# Defects found by this suite

* [Refused credential: crash and no verdict](../findings/auth-refused-crash.md)
* [Installed files not aligned with the source](../findings/stale-installed-files.md)

# Relations

- **verifies** [craft-bridge-doctor](craft-bridge-doctor.md), [craft-bridge-ident](craft-bridge-ident.md), [craft-bridge-launch](craft-bridge-launch.md), [craft-bridge-mcp](craft-bridge-mcp.md)
- **and the translator** [craft-bridge-ui](craft-bridge-ui.md) - arguments, MCP session, fallback and live window
- **and the attach flag** [craft-bridge-mcp](craft-bridge-mcp.md) - against the help of every CLI (fake CLIs, and live)
- **and the paths** [Where the app is](../architecture/app-locations.md) - the three outcomes of the choice, without touching the registry
- **produces** [Reports and baseline](../architecture/reports.md)
- **in the runbook** [Diagnosis and verification](../operations/diagnosis.md)
- **run on every push by** [Continuous integration](../operations/ci.md) with `--static --ci`
