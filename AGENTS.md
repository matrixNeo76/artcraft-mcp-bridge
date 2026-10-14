# AGENTS.md — how to work in this repo

Instructions for an agent modifying this project. The rules always hold, even when they
seem to slow the work down: they come from real defects found by measuring.

## What this project is

The bridge between the Crafting Apps and MCP clients: stdio shim, control channel,
diagnosis and proofs. Central idea: **no claim without the measurement** that supports it.
Every tool declares what it proved, and when it does not know it says so.

## Where things are

| Path | Content |
|---|---|
| `tools/` | the Python tools. They run from here, they work from any folder (`craft-bridge-ui.py` is the PdfCraft window translator; `craft-bridge-connect.py` registers the bridge in the other MCP clients, `craft-bridge-report.py` writes the status JSON and page) |
| `install/` | `install-craft-mcp.ps1`, multi-client registration of the generative MCP |
| `reports/` | generated artifacts; it is the default output of the tools, not the folder you invoke them from |
| `docs/` | documentation in **OKF v0.2** (bundle: `docs/index.md`) |
| `README.md`, `ROADMAP.md` | overview and next steps |
| `LICENSE` | the project's MIT licence: it is not modified, and a new file entering the repo inherits its terms |

## Rules that are not broken

1. **The real connector config is not a guinea pig.** Only
   `craft-bridge-config.py --apply` writes `~/.agents/mcp.json` (with a backup). The tests
   exercise it on a copy with `--config`.
2. **The installed copies are not touched by hand.**
   `%LOCALAPPDATA%\Programs\craft-bridge` is updated with `--apply`. If you change
   `craft-bridge-mcp.py`, `craft-bridge-ident.py` or `craft-bridge-ui.py` in the repo, run
   `--apply`, otherwise `doctor` reports — rightly — the drift between source and installed.
   (And the MCP entries run the **installed** file: after a change, measuring the repo is
   measuring something else.)
3. **The token value is never printed**, never entered into chat, logs, reports or the
   repo. Only the outcome of the `auth` is read.
4. **No process killed unless you started it.** If a port is occupied, skip the case (SKIP),
   do not terminate someone else's processes.
5. **Apps are started only on free ports**, inside `try/finally`, and temporaries are deleted
   at the end.

## Before saying "done"

```bash
python -m py_compile tools/*.py              # syntax of every tool
python tools/craft-bridge-doctor.py          # one verdict on the assembly (exit 0 = nothing to do)
python tools/craft-bridge-mcp.py --flags     # the attach flag every CLI declares
python tools/craft-bridge-tests.py --static  # ~34 s, the cases that start no app (20 of 24)
python tools/craft-bridge-feed.py            # installed against published (if the launcher is there)
python tools/craft-bridge-connect.py --list  # which MCP clients are here (writes nothing)
python tools/craft-bridge-report.py          # the whole state in reports/bridge-status.{json,html}
python tools/craft-bridge-tests.py           # ~72 s, including the cases with real apps
```

CI runs `python tools/craft-bridge-tests.py --static --ci`: `--ci` skips the cases that
require the bridge **explaining why**, and it must never be used to make a real machine pass
(there the skips do not happen, and a real fault stays a FAIL).

The suite also **decides**, not only reports: exit `1` is a failed case, exit `3` is a case that
got worse than the saved baseline (`reports/craft-bridge-tests.json`), and in CI both stop the
push. The comparison only applies on the same host and in the same mode, and it says so when it
does not; `--no-gate` removes the decision but not the measurement. If you change the cases or the
installed state on purpose, refresh the baseline in the same commit - and refresh it in the state
CI runs in (the apps closed), otherwise you are demanding an open window from every later push. The workflow steps can be run
locally by extracting them from `.github/workflows/checks.yml` and running them with
`powershell -NoProfile -ExecutionPolicy Bypass -File step.ps1`.

If you touched the shim, the translator, ident or doctor, the full suite is mandatory: it is
what declares whether the behaviour changed, and it compares itself with the previous run
(`reports/craft-bridge-tests.md`, section *Confronto*).

## Conventions

- **Language**: **documentation is in English** — `docs/**`, `README.md`, `AGENTS.md`,
  `ROADMAP.md` — so that it can be read by everyone. `README.md` is the main one and is
  translated into [Italiano](README.it.md), [Español](README.es.md) and
  [中文](README.zh.md); those three are translations, so when the English one changes they
  change with it. Keep the doc nodes in English too: their `title`, `description`, section
  headings and relation verbs (`**uses** [...]`, `**proved by** [...]`).
  **The prose inside the code** (comments, docstrings, CLI messages and reports) is still
  Italian: it is a separate, tracked change, not something to mix half-way while editing
  another file. Code identifiers stay in English. Use ASCII apostrophes (`l'app`), not
  typographic ones.
- **One verdict per tool**: distinct exit codes for distinct meanings (`0` ok, `1` problem,
  `2` usage error, `3` unreadable config) and each one declared in the docstring and in the
  final message.
- **A single source for shared data**: the app table lives in the shim (`--dump-apps`) and
  everyone reads it; the expected entries are produced by `craft-bridge-config.py` and also
  consumed by `doctor`. Do not duplicate tables.
  **Paths are not written by hand**: app and CLI are resolved from the system registry
  (`App Paths`), and the table stays as a confirmation — see
  [Where the app is](docs/architecture/app-locations.md). This holds for startup too.
  **And the apps served by the bridge are the shim's _plus_ the translator's**: whoever
  compares installed against published uses `CONFIG.bridge_table()`, not the shim table,
  otherwise PdfCraft stays outside a check that concerns it — see
  [craft-bridge-ui](docs/tools/craft-bridge-ui.md).
  **Inside the table, what is not ours is verified where it lives**: the attach flag is
  declared by the CLI help (`craft-bridge-mcp.py --flags`, the doctor's `flag di aggancio`
  line), the PdfCraft window methods are declared by the app (the translator's `--list`), the
  paths are declared by the registry. A declaration nobody checks is a hand-written path
  under another name.
- **When you discover a limit, write it down.** The "Limits" sections are part of the result,
  not a confession of guilt.

## Documentation

The documentation is an OKF v0.2 bundle: one concept per `.md` file under `docs/`, with YAML
frontmatter (only `type` is mandatory; here `title`, `description`, `resource`, `tags`,
`generated`, `status`, `sources` are used too) and **relations expressed as markdown links**,
with the kind of relation in the text (`**uses** [...]`, `**proved by** [...]`).

If you change the behaviour of something, update the corresponding node **and** add a line to
[docs/log.md](docs/log.md) with the date (`YYYY-MM-DD`). `index.md` and `log.md` are reserved
files: they are not concepts and their format is different.

Validating and viewing the bundle:

```bash
uvx okfgen validate docs --strict                        # OKF v0.2 conformance
uvx okfgen visualize docs -o reports/okf-graph.html      # graph of nodes and relations
```

## Traps already paid for

- The end of a message on the control channel is recognised by **parsing**, not by looking for
  a newline: the apps leave a stray `\n` after the previous answer.
- A network error must not raise: what was read is returned (a `sendall` on a connection
  closed by the app used to kill `ident` with no verdict and could have lost the MCP server).
- A peer that accepts and then stays silent **is not** a live peer: without the handshake
  bridged mode becomes headless in disguise.
- A published package is **not** an executable: the feed's `sha256` is the archive's (MSI,
  portable zip, AppImage), and the CLI is inside it. To compare it, the member is read in
  memory, and the member name depends on the system (`<slug>-cli.exe` on Windows); an MSI or a
  .dmg cannot be opened with the standard library, so for those apps the bytes stay
  uncompared — and that must be said, not worked around.
- A proof that is not there is not a passed proof: if the file to compare is missing, the
  verdict is a note with the command to fetch it, not an "ok".
- The ArtCraft launcher does **not** start or install apps from the command line (no
  `--install`/`--launch`, no registered URL scheme: issues #128 and #148 ask for exactly
  this), and it does not keep a list of what is installed — its local state is the window plus
  the release catalogue cache. Asking it where an app is therefore means asking the system:
  the source is the `App Paths` registry, filled by the app's MSI installer — in `HKLM` if for
  everyone, in `HKCU` if for the user only (`app_hive` says which), and both are read because
  the launcher itself is installed per user.
- A hand-written path ages in silence: updating a string in a table breaks no connector, and
  nobody notices until the app moves. That is why the source is the system and the table is
  only the confirmation (and the fallback where the registry has nothing).
- A table that promises an option is a declaration, not a proof: the bridge flag lives in
  another company's help (the CLI), so it must be **asked** there. If the help does not name
  it, the table is claiming something nobody confirms, and the fault would only show at the
  first connection — which is the worst place to find out.
- An app that cannot attach the window from its MCP server is not a lost app: if the CLI can
  drive it, its methods can be **translated** into MCP tools (one process per call). That is
  what the translator does for PdfCraft, and the two limits it carries — no shared state
  between calls, a different catalogue between the two modes — must be declared, not hidden.
- `reports/` is versioned on purpose: the reports are the memory of past runs.
