---
type: Runbook
title: "Continuous integration: what every push checks"
description: "The .github/workflows/checks.yml workflow: portable checks on a hosted runner, the full suite on a self-hosted runner, and what --ci means."
resource: "../../.github/workflows/checks.yml"
tags: [ci, workflow, checks, badge]
generated: { by: process:freebuff-buffy, at: 2026-10-14T08:15:00Z }
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
| Runner log | `C:\Users\auresystem\actions-runner-craftbridge\runner.log` (the runner's own: while it runs it holds the file open) |
| Launcher log | `C:\Users\auresystem\actions-runner-craftbridge\start-runner.log` (so the launcher's lines do not compete for a locked file) |
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

From Git Bash, call the script as `MSYS_NO_PATHCONV=1 ./start-runner.cmd`: without it `cmd /c
script.cmd` becomes a path (`/c` turns into `C:\`), cmd opens an interactive shell that reads stdin
and the command hangs with no output. Wasted two minutes on it.

**Why not a Windows service.** The suite starts the Crafting Apps and drives their windows, and a
service runs in session 0, where those windows do not exist: the runner would be online and unable
to prove anything. The Startup folder starts it inside the user's session, which is exactly where
the bridge exists. A scheduled task "at logon" would do the same but needs administrator rights.

**It starts once.** The launcher is **idempotent**: if a listener of this folder is already alive
(exit and log back in inside the same session, double click on the entry) it writes a line to
`start-runner.log` and stops, instead of registering a second listener on the same runner. Which
check it uses, and how it was proved:

| Attempt | Outcome |
|---|---|
| `Get-CimInstance -Filter "Name='Runner.Listener.exe'"` inside a `for /f` | **wrong**: cmd eats the escaped quotes, PowerShell receives `Name 'Runner.Listener.exe'`, the query is invalid and the count comes out `0` — a check that checks nothing |
| `Get-Process Runner.Listener \| Where-Object { $_.Path -like '<dir>bin*' }` | right: `1` with the listener alive, `0` without |
| the launcher with a listener alive | exit 0, one line in `start-runner.log`, **still one** listener process |
| the listener stopped, then the launcher | new listener in the user's session, online, and a dispatched run was taken (`Running job` in `runner.log`) |

Two more traps, both inside the script: no parentheses inside an `if (...)` block (they close the
block early and the batch file dies with `: non atteso`), and the log must not be `runner.log` while
the runner holds it open (`the file is being used by another process` — the line one needs is exactly
the one that cannot be written).

**After a forced stop.** Killing the listener does not kill the registration, but GitHub keeps the
old session for about two minutes: the new listener gets `A session for this runner already exists`
and `Conflict. Retrying until reconnected.`, then creates the session and prints `Listening for
Jobs`. A run dispatched **inside that window** can stay queued forever even after the reconnection -
dispatch it again and it starts immediately. Measured: killed at 21:25 local, conflict until
19:27:40Z, `Listening for Jobs`; the job dispatched at 19:26:51Z stayed `queued`, the one dispatched
at 19:33 took the runner at 19:33:48Z and succeeded. So: after a restart, dispatch again instead of
staring at the queue.

**The two files on the machine** (they live outside the repo because they name this machine):
`start-runner.cmd` next to the runner, and one line of Startup in
`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\craftbridge-actions-runner.cmd`:

```bat
start "craftbridge-actions-runner" /min "C:\Users\auresystem\actions-runner-craftbridge\start-runner.cmd"
```

The operative part of `start-runner.cmd` (the file on the machine carries the comments, in Italian
like the rest of the code):

```bat
set RUNNER_DIR=%~dp0
cd /d "%RUNNER_DIR%"

set ALIVE=?
for /f "usebackq delims=" %%N in (`powershell -NoProfile -Command "(Get-Process Runner.Listener -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '%RUNNER_DIR%bin*' }).Count"`) do set ALIVE=%%N
if not "%ALIVE%"=="0" (
  echo ==== %DATE% %TIME% un listener e' gia' attivo, conteggio %ALIVE%, nessuna seconda partenza ==== >> "%RUNNER_DIR%start-runner.log"
  exit /b 0
)

echo ==== avvio %DATE% %TIME% (cartella %RUNNER_DIR: =%) ==== >> "%RUNNER_DIR%start-runner.log"
call "%RUNNER_DIR%run.cmd" >> "%RUNNER_DIR%runner.log" 2>&1
echo ==== uscita %DATE% %TIME% (codice %ERRORLEVEL%) ==== >> "%RUNNER_DIR%start-runner.log"
```

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

# The steps of the self-hosted job

| Step | What it does |
|---|---|
| Diagnosis | `craft-bridge-doctor.py`; a non-zero exit fails the job with the actions it listed |
| Full suite | `craft-bridge-tests.py` **without** `--ci`: here the absent-environment skips are not forgiven, and the gate on regressions applies - a case that gets worse than the committed baseline exits 3 and the job fails |
| Artifact | `craft-bridge-tests-selfhosted` (the hosted job's is `craft-bridge-tests`: two different names, so the two runs do not overwrite each other) |
| Status page | `craft-bridge-report.py` (live diagnosis) | the page of the machine where the bridge exists: verdict, entries, clients, baselines |
| Status artifact | `bridge-status-selfhosted` (the hosted job's is `bridge-status`) | same rule as the report: two names, so the two runs do not overwrite each other |

The steps use `powershell`, not `pwsh` - see above.

Measured on the machine that has the apps: **24 cases, 23 PASS, 1 SKIP, 0 FAIL, ~76 s**. The skip is
the declared one: *live PdfCraft window* - the window was closed, so the entry would go headless,
which is not a fault. Among the 23 that ran there are the ones that start a real app (*app on the
port*, *different build*, *another app on the port*, *refused credential*, *attach flag, live*):
those are the cases this job exists for.

# The baseline this job measures against

The comparison reads `reports/craft-bridge-tests.json` **from the checkout** (the complete run's
baseline; the `--static` one has its own file, `.static.json`), so every push is compared with the
state someone last committed, not with the run before: a regression cannot age away by itself. When it fires, two honest answers exist - fix the cause, or refresh the baseline
in the same commit, which is a decision and not an accident. Refresh it in the state CI runs in
(the apps closed): a baseline taken with the PdfCraft window open would make every later push
red for a closed window. The gate itself is in
[craft-bridge-tests](../tools/craft-bridge-tests.md).

Proved, not assumed: on a throwaway branch whose baseline declared a proof the machine did not
have (PdfCraft `PASS` with the window closed) this job failed with `regressione rispetto alla
baseline` and the offending case named in the log, while the hosted job stayed green - its
`--static --ci` run has its own baseline and does not accuse another mode's file.

# The steps of the hosted job

| Step | What it verifies | Why |
|---|---|---|
| Syntax | `py_compile` on every tool | a syntax error must not reach an agent that invokes them |
| Interfaces | `--help` of every tool with `argparse` | the interface exists and answers (stdio servers are skipped: a `--help` would start them waiting for stdin) |
| App table | the 12 documented apps and ports | the table is a single source: config and diagnosis read this one |
| Deterministic installer | two rounds of `--json` identical, and the entries are the shim's 12 plus the translator's one | idempotence, and the number is asked of the table instead of being written here: the fixed count went stale the first time an app changed road (expected 11, produced 12) |
| OKF bundle | `uvx --from "okfgen==0.1.3" okfgen validate docs --strict` | the documentation stays consumable by another tool; the version is pinned so it does not depend on the newest release |
| Suite | `craft-bridge-tests.py --static --ci` | the cases runnable without the bridge, with motivated skips. The gate on regressions does **not** apply here: a `--static --ci` run has its own baseline name (`craft-bridge-tests.static.ci.json`), which inside a fresh checkout does not exist yet |
| Artifact | `reports/craft-bridge-tests.*` | the run report stays downloadable, even if the run fails |
| Status page | `craft-bridge-report.py --no-live` | refreshes `reports/bridge-status.*` even with no apps, and even if the suite died before its own refresh |
| Status artifact | `bridge-status` | the page stays downloadable on every push |

# The status page travels with the run

Both jobs end with the same pair of steps: one **regenerates** `reports/bridge-status.json` and
`reports/bridge-status.html` - the same page `craft-bridge-report.py --serve` shows locally - and
one **publishes** them as artifacts (`bridge-status` from the hosted job,
`bridge-status-selfhosted` from the other). Every push therefore leaves a downloadable view of the
state, with nobody having to regenerate it by hand.

Three deliberate choices:

* the hosted step runs with `--no-live`: on a runner without the apps there is no port to ask, and
a probe would only add waiting to a page that is already honest about what it cannot see;
* the step is `continue-on-error: true` and runs `if: always()`. A page that cannot be written is
not a fault of the bridge - the verdict already says what is wrong - so the artifact is a
commodity here, not a gate;
* the suite refreshes the page itself at the end of a run (`--no-status` turns that off), so this
step looks redundant - it is there for the run where the suite dies before reaching its own
refresh, which is exactly the run whose page one would want to read.

Downloading it:

```bash
gh run download --name bridge-status && start bridge-status/bridge-status.html
gh run download --name bridge-status-selfhosted   # the run that used the self-hosted job
```

The file to open is `bridge-status.html`, with `bridge-status.json` beside it: opened straight from
the downloaded folder it still renders, because the page carries a copy of the data inside for the
`file://` case.

# What `--ci` means

`--ci` skips the cases that require the bridge **explaining why** (`ambiente assente su
questo runner: config assente (...)`), instead of failing. The rule is strict: it changes
what an *absent environment* is, not what a *fault* is.

The distinction is proved in three ways, all run before publishing it:

1. on a machine with the bridge, `--static --ci` gives **20/20 and no skips** (24/24 on the
   whole suite); with the PdfCraft window closed, the one live case of that mode skips and
   says why - it is the case that needs the window, not a fault;
2. on a machine without a bridge (an empty environment: no connector config, no installed
   copies), it gives **12 passed + 8 skipped** and exits 0, with the reason on every skip;
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
- **it publishes** [craft-bridge-report](../tools/craft-bridge-report.md) as the run's status artifact
- **it validates** [Reports and baseline](../architecture/reports.md) as the run artifact
- **badge in** [README](../../README.md)
- **safety rules in** [Safety rules](safety-rules.md)
