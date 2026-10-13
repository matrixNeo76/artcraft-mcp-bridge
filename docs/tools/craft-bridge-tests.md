---
type: Tool
title: "craft-bridge-tests - the suite that injects faults"
description: "Twenty-four cases that break something on purpose and demand the right verdict from shim, translator, doctor, ident and launcher; every run leaves a report compared with the saved baseline, and a case that gets worse stops the run with its own exit code."
resource: ../../tools/craft-bridge-tests.py
tags: [tool, tests, faults, report]
generated: { by: process:freebuff-buffy, at: 2026-10-13T19:55:00Z }
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

One case concerns **the gate itself**, on fake reports and with no machine: which worsenings stop
the run (PASS → FAIL, PASS → SKIP, SKIP → FAIL, a case that is no longer run), which do not (a
case that appears, FAIL → PASS), and the two comparisons that must be **refused** because they
would accuse the environment instead of the code (another host, another mode). It also asks the
exit-code function, so the mapping `0/1/3` is proved where it is written.

Three cases concern the **attach flag**: the six verdicts of the comparison with the CLI
help (on fake CLIs, with no app), the `doctor` line in both directions - a table not
confirmed must be a `FIX` with the action `--flags`, one confirmed by the channel an `ok`,
and an **absent** CLI (what a runner without apps sees) a `nota` - and the measurement on
the real CLIs, where it also checks that the diagnosis says the same thing.

The cost of the `doctor` cases grew with the cost of the tool (~2.4 s per round, because
every check that talks to the CLIs or to the translator costs a process): that is why the
suite asks the doctor **only** what a single line cannot say.

Four cases concern [the window translator](craft-bridge-ui.md) and three of them **need no
window**: a fake PdfCraft answers on the channel the way the real app does (authentication
with the control file's token, `ui.state`, a fake screenshot, a real fault on a label that
does not exist), and it is **shut down mid-session** to demand the diagnosis instead of an
answer that merely looks successful; a fake MCP server plays the part of the vendor's
headless server. The fourth is the live one: if the window is not there it is **skipped
with a reason**, because that is not a fault of the bridge.

No window does not mean no CLI: in the session case the chain under test is the translator →
`pdfcraft-cli ui --control FILE` → channel, so **the vendor's CLI is what must speak to the
channel** and the case needs it installed. Where it is missing (a CI runner with no apps) the
case is **skipped with the reason** (`la CLI del fornitore non e' installata (...)`), which is
what the first real CI run of the translator found: it used to die with `server MCP chiuso in
anticipo`, an error that says nothing about what was missing. The fallback case is the one that
really needs nothing, because there the fake CLI **is** the headless server.

# Interface

```
python tools/craft-bridge-tests.py                 # everything (~76 s, starts real apps)
python tools/craft-bridge-tests.py --static        # only the cases without apps (~36 s, 20 of 24)
python tools/craft-bridge-tests.py --only build --json
python tools/craft-bridge-tests.py --report reports/my.json --compare old.json
python tools/craft-bridge-tests.py --static --ci   # on a runner without an installed bridge
python tools/craft-bridge-tests.py --no-gate       # compare, but do not decide the exit code
```

# `--ci`

It is for a CI runner: if the machine has neither the connector config nor the installed
copies, the cases that talk about the bridge are **skipped with the reason** instead of
failing. A real fault stays a FAIL: the mode changes what an absent environment is, not
what a fault is. The three proofs, all run before publishing it:

1. on a machine with the bridge, `--static --ci` gives **20/20 and no skips** (and 24/24 on
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

# The gate on regressions

A comparison nobody acts on is a report nobody reads, so the comparison **decides**: when a case
gets worse than the baseline the suite exits **3**, and in CI that is a red push instead of a
paragraph in an artifact. Which worsenings count:

| Baseline | Now | Verdict |
|---|---|---|
| PASS | FAIL | worse: the proof is contradicted |
| PASS | SKIP | worse: a proof that is not there is not a passed proof |
| SKIP | FAIL | worse |
| PASS | not run any more | worse: same loss, seen from the other side |
| FAIL | PASS, SKIP | PASS | better (or still unproven): it does not stop anything |
| - | new case | a new case is not a regression |

It applies **only where the comparison means something**: same host and same modes
(`static`, `only`, `ci`). On another machine, or against a `--ci` baseline, the run says so and
does not decide - two different environments must not accuse each other, and the hosted job
(`--static --ci`) therefore never gates. `--no-gate` removes the decision but not the
measurement: what got worse is still listed and still written in the report. `--no-report`
removes both, because with no file written there is nothing saved to compare against.

Which baseline? The saved one: in CI it is the committed
[report and baseline](../architecture/reports.md), so every push is measured against a
**decision**; locally it is the run before, so accepting a regression and running again is a
deliberate act, which is exactly what "saving a baseline" means. Refresh it in the state you
expect CI to be in (the apps closed): a baseline taken with the PdfCraft window open is a
baseline that demands the window open.

# Safety rules

The real config is never written (the cases exercise it on a copy with `--config`); the
only real file touched is the **installed** copy of the shim, inside a `try/finally` that
puts it back; apps are started only on free ports, and if a port is occupied the case is
skipped instead of killing someone else's processes; temporaries, logs and test tokens
disappear at the end.

# Exit codes

| Exit | Meaning |
|---|---|
| 0 | every case passed and nothing got worse (SKIP is not a fault) |
| 1 | at least one FAIL |
| 2 | usage error |
| 3 | no FAIL, but at least one case got worse than the saved baseline |

# Defects found by this suite

* [Refused credential: crash and no verdict](../findings/auth-refused-crash.md)
* [Installed files not aligned with the source](../findings/stale-installed-files.md)

# Relations

- **verifies** [craft-bridge-doctor](craft-bridge-doctor.md), [craft-bridge-ident](craft-bridge-ident.md), [craft-bridge-launch](craft-bridge-launch.md), [craft-bridge-mcp](craft-bridge-mcp.md)
- **and the translator** [craft-bridge-ui](craft-bridge-ui.md) - arguments, MCP session, fallback and live window
- **and the attach flag** [craft-bridge-mcp](craft-bridge-mcp.md) - against the help of every CLI (fake CLIs, and live)
- **and the paths** [Where the app is](../architecture/app-locations.md) - the three outcomes of the choice, without touching the registry
- **decides against the saved baseline** [Reports and baseline](../architecture/reports.md)
- **in the runbook** [Diagnosis and verification](../operations/diagnosis.md)
- **run on every push by** [Continuous integration](../operations/ci.md) with `--static --ci`
