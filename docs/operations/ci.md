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
(Settings → Secrets and variables → Actions → Variables) **and** by having a runner with the
labels `self-hosted`, `windows`, `craftbridge` registered and online. If either of the two is
missing the job is skipped and does not colour the badge: the next section is that switch, piece
by piece.

# The self-hosted runner, piece by piece

The `ponte-completo` job runs where the bridge really exists. What is activated and where it
lives:

| Piece | Where / value |
|---|---|
| Repository variable | `CRAFTBRIDGE_SELF_HOSTED=1` (`gh variable set CRAFTBRIDGE_SELF_HOSTED --body 1`) |
| Runner | `craftbridge-auresystem`, version 2.338.0, in `C:\Users\auresystem\actions-runner-craftbridge` |
| Labels | `self-hosted`, `windows`, `craftbridge` (they must match the job's `runs-on`) |
| Starts at logon | `%APPDATA%\...\Startup\craftbridge-actions-runner.cmd` → `start-runner.cmd` → `run.cmd` |
| Log | `C:\Users\auresystem\actions-runner-craftbridge\runner.log` |
| Online check | `gh api repos/<owner>/<repo>/actions/runners` → `"status": "online"` |

**One detail that looks like a mistake.** `gh api .../actions/runners` lists the labels as
`self-hosted, Windows, X64, craftbridge`: `Windows` is GitHub's own default label and registration
keeps it even when the `--labels` list writes `windows`. Matching is case-insensitive, so
`runs-on: [self-hosted, windows, craftbridge]` finds the runner all the same - the name that has to
match is the one the job asks for, not the one GitHub displays.

Prerequisites on the machine: `python` 3.12 in the PATH and the bridge installed
(`python tools/craft-bridge-config.py --apply`), because the diagnosis looks at what is
actually running. PowerShell 7 is **not** required: the hosted job uses `pwsh`, which GitHub
runners have and a normal PC may not, so this job's steps use `powershell`, which every Windows
has. The first real run failed exactly there (`pwsh: command not found`) - a machine teaching the
pipeline what "portable" means.

Setting it up from scratch:

```bash
# 1. tell the workflow that the machine exists
gh variable set CRAFTBRIDGE_SELF_HOSTED --body 1

# 2. official runner, latest release
VER=$(gh api repos/actions/runner/releases/latest -q .tag_name | sed 's/^v//')
curl -sSL -o runner.zip \
  "https://github.com/actions/runner/releases/download/v$VER/actions-runner-win-x64-$VER.zip"
powershell -NoProfile -Command "Expand-Archive runner.zip -DestinationPath . -Force"

# 3. register it with the labels the job asks for
TOKEN=$(gh api -X POST repos/<owner>/<repo>/actions/runners/registration-token -q .token)
bin/Runner.Listener.exe configure --url https://github.com/<owner>/<repo> \
  --token "$TOKEN" --name craftbridge-auresystem \
  --labels self-hosted,windows,craftbridge --work _work --unattended --replace

# 4. start it (and once to prove the same path works)
powershell -NoProfile -Command "Start-Process -FilePath '<dir>\start-runner.cmd' -WindowStyle Minimized"
```

**Why not a Windows service.** The suite starts the Crafting Apps and drives their windows, and a
service runs in session 0, where those windows do not exist: the runner would be online and unable
to prove anything. The Startup folder starts it inside the user's session, which is exactly where
the bridge exists. A scheduled task "at logon" would do the same but needs administrator rights.

**Why it never runs on pull requests.** This repository is public: a pull request, including one
from a fork, would run a stranger's code on the machine where the bridge is installed, and that is
not a disposable machine. The job's condition therefore accepts only `push` and
`workflow_dispatch`; the hosted job stays active on pull requests, where there is nothing to ruin.

**Removing it:**

```bash
bin/Runner.Listener.exe remove --token $(gh api -X POST \
  repos/<owner>/<repo>/actions/runners/remove-token -q .token)
gh variable delete CRAFTBRIDGE_SELF_HOSTED     # the job goes back to being skipped
```

then delete the runner folder and the Startup entry. The two together are the switch: the variable
alone, or the runner alone, changes nothing.

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
