---
type: Runbook
title: "Continuous integration: what every push checks"
description: "The .github/workflows/checks.yml workflow: portable checks on a hosted runner, the full suite on a self-hosted runner, and what --ci means."
resource: "../../.github/workflows/checks.yml"
tags: [ci, workflow, checks, badge]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:47:19Z }
status: stable
sources:
- resource: "../../.github/workflows/checks.yml"
  title: "the workflow"
- resource: "../../tools/craft-bridge-tests.py"
  title: "the suite the workflow runs"
- resource: "../../README.md"
  title: "status badge"
---

# Why two jobs

The suite of this project **exercises a machine**, not just code: `stato pulito` demands
that `doctor` has no actions to take, `shim installato stantio` touches the installed copy,
the other cases talk to the apps. On a GitHub-hosted runner none of that exists, so the
whole suite there can only fail - and a badge that is red forever tells nobody anything.

So the workflow has two jobs:

| Job | Where | What it does |
|---|---|---|
| `controlli` | `windows-latest` (GitHub) | everything that does not depend on the machine, plus the suite with `--ci` |
| `ponte-completo` | a **self-hosted** runner with the apps | `doctor` and the whole suite, where the bridge really exists |

The second one is enabled by setting the repository variable `CRAFTBRIDGE_SELF_HOSTED=1`
(Settings → Secrets and variables → Actions → Variables) and registering a runner with the
labels `self-hosted`, `windows`, `craftbridge`. If the variable is absent, the job is
skipped and does not colour the badge.

# The steps of the hosted job

| Step | What it verifies | Why |
|---|---|---|
| Syntax | `py_compile` on every tool | a syntax error must not reach an agent that invokes them |
| Interfaces | `--help` of every tool with `argparse` | the interface exists and answers (stdio servers are skipped: a `--help` would start them waiting for stdin) |
| App table | the 11 documented apps and ports | the table is a single source: config and diagnosis read this one |
| Deterministic installer | two rounds of `--json` identical, and the entries are the shim's 11 plus the translator's one | idempotence, and the number is asked of the table instead of being written here: the fixed count went stale the first time an app changed road (expected 11, produced 12) |
| OKF bundle | `uvx --from "okfgen==0.1.3" okfgen validate docs --strict` | the documentation stays consumable by another tool; the version is pinned so it does not depend on the newest release |
| Suite | `craft-bridge-tests.py --static --ci` | the cases runnable without the bridge, with motivated skips |
| Artifact | `reports/craft-bridge-tests.*` | the run report stays downloadable, even if the run fails |

# What `--ci` means

`--ci` skips the cases that require the bridge **explaining why** (`ambiente assente su
questo runner: config assente (...)`), instead of failing. The rule is strict: it changes
what an *absent environment* is, not what a *fault* is.

The distinction is proved in three ways, all run before publishing it:

1. on a machine with the bridge, `--static --ci` gives **19/19 and no skips** (23/23 on the
   whole suite);
2. on a machine without a bridge (an empty environment: no connector config, no installed
   copies), it gives **11 passed + 8 skipped** and exits 0, with the reason on every skip;
3. with a real fault injected - one extra byte in the installed copy of the translator -
   the same command gives **FAIL** and exits 1 even with `--ci`: the mode does not hide
   faults, it only stops calling the absence of a bridge a fault.

# How the steps are proved without publishing

The steps were run locally **by extracting them from the workflow file**
(`powershell -NoProfile -ExecutionPolicy Bypass -File step.ps1`), so what runs in CI and
what was verified are the same text; then CI itself, on the first push, finished the job.
The three things this found:

* in PowerShell `"$slug: ..."` is read as a **variable with a drive**
  (`InvalidVariableReferenceWithDrive`): it must be written `"${slug}: ..."`. The step died
  with that error instead of saying what was wrong;
* counting the properties of a JSON object needs `Measure-Object`, not `.Count` (which
  printed a `1` per line);
* **`uvx` does not exist on GitHub runners**: the `astral-sh/setup-uv` step is needed, and
  the validator version must be pinned (`okfgen==0.1.3`), otherwise one of its releases can
  fail a push in which nothing changed. CI itself found this, on the first push.

# Relations

- **it runs** [craft-bridge-tests](../tools/craft-bridge-tests.md) in `--ci` mode
- **it runs** [craft-bridge-doctor](../tools/craft-bridge-doctor.md) in the self-hosted job
- **it validates** [Reports and baseline](../architecture/reports.md) as the run artifact
- **badge in** [README](../../README.md)
- **safety rules in** [Safety rules](safety-rules.md)
