# ArtCraft MCP Bridge

[![checks](https://github.com/matrixNeo76/artcraft-mcp-bridge/actions/workflows/checks.yml/badge.svg)](https://github.com/matrixNeo76/artcraft-mcp-bridge/actions/workflows/checks.yml)

**English** · [Italiano](README.it.md) · [Español](README.es.md) · [中文](README.zh.md)

A bridge between the **Crafting Apps** (CADCraft, DeckCraft, DesignCraft, EffectCraft, FigCraft,
FilmCraft, GridCraft, LightCraft, PdfCraft, PhotoCraft, SoundCraft, VectorCraft, WordCraft) and MCP
clients: instead of falling back to the interface-less CLI, the running app is driven through its
**control channel**, so the tools act on the open window.

## The problem

Every Crafting App exposes a headless MCP server (`<app>-cli.exe mcp`). Many tools, though, only
make sense on the live app: drawing, capturing the canvas, moving a cursor. In headless those
tools disappear or fail, and the client cannot know why.

## How it works

1. the app is started with `--control <port>` (and, for PhotoCraft, `--control-token-file`);
2. the **shim** registered in the connectors performs a **handshake** on that port;
3. if the peer speaks the protocol **and is the right app** (command catalogue, threshold 0.9) it
   goes **bridged** and forwards the requests to the app; otherwise it goes **headless** and says
   so on stderr. With `--require-bridge` it exits 3 instead of falling back.

PdfCraft is the exception to point 3: it uses a *control file* and its MCP server has no bridge
flag (`mcp --connect` → `unknown option`). Its window is driven all the same, by
**translation**: [craft-bridge-ui.py](tools/craft-bridge-ui.py) exposes the 15 methods the app
declares as as many MCP tools, invoking `pdfcraft-cli ui --control FILE <method>` once per call.

No silent fallback: the mode chosen is always declared, and whoever answers on the port is
identified (the app **and** the running build). The same holds for the table: the attach flag each
app requires is not something we remember — we ask the CLI help, and when it does not confirm it
the diagnosis says so.

## Layout

```
tools/     the tools (Python): shim, window translator, ident, doctor, config, launch, verify, sweep, tests, exploratory
install/   install-craft-mcp.ps1 (multi-client registration of the generative MCP)
reports/   generated artifacts: suite and sweep reports, tool inventory, images
docs/      documentation in OKF v0.2 format (nodes and relations) - see docs/index.md
```

## Quick start

```bash
# 1. installs the copies of the shim and rewrites the connector entries (with a backup)
python tools/craft-bridge-config.py --apply
# 2. in Freebuff: Connectors -> Refresh

# 3. start the apps with the control channel (the windows stay open)
python tools/craft-bridge-launch.py

# 4. verify: one verdict on the assembly, then every entry with its real command
python tools/craft-bridge-doctor.py
python tools/craft-bridge-verify.py
```

Back to headless: `python tools/craft-bridge-config.py --restore`.

## Other MCP clients

Freebuff is not the only client. One command puts the same bridge into the others you
have — Claude Desktop, Claude Code, Cursor, Windsurf, VS Code, Cline, LM Studio, Zed,
Codex (ChatGPT desktop) and DeepSeek Harness (`dsh`) — each in its own file and format,
from a single source and without touching what is not ours:

```bash
python tools/craft-bridge-connect.py --list     # who is here, and where it reads
python tools/craft-bridge-connect.py            # dry-run: what would change
python tools/craft-bridge-connect.py --apply    # writes, with a backup
```

The recipe, client by client (including the two that are not JSON), is in
[docs/operations/connect-a-client.md](docs/operations/connect-a-client.md).

To see the whole state at a glance — verdict, entries, clients, baselines, feed, logs —
in one JSON and one page that reads it:

```bash
python tools/craft-bridge-report.py             # reports/bridge-status.json + .html
python tools/craft-bridge-report.py --serve     # + local server, opens the page (Ctrl+C to stop)
```

## Verified state (13 October 2026)

| Proof | Outcome |
|---|---|
| Apps driveable with a successful call on the window | 13 of 13 (12 bridged through the shim — `figcraft` included — PdfCraft by translation) |
| Config entries run with the real command | 14/14 |
| Fault suite (28 cases, injected faults) | 27 run + 1 skipped with the PdfCraft window closed (the one live case says why), 23+1 in `--static`, two runs in a row identical |
| Clients the bridge is registered in | 13 known, 4 present on this machine; after `--apply` all at **13/13** (before: `agents` 13, `claude-desktop` and `antigravity` **12** as headless entries, `windsurf` **0**) |
| Installed against the release published by the launcher | 12 of 13 compared (feed of 13 October): the feed does not name `figcraft` yet, so for it there is no term of comparison and the diagnosis says so |
| Bytes of the installed CLI against the published ones | 1 of 12 tried: SoundCraft identical (`sha256 915ee3abb121…`); for the others the archive is not on disk |
| App and CLI paths | 12 of 12 from the `App Paths` registry (the table confirms, it does not decide) |
| PdfCraft window methods | 15 of 15 as the app declares them; 192 commands, 107 widgets, screenshot of the window |
| Attach flags declared by the table | 13 of 13 confirmed by the CLI help (11 `--connect`/`--bridge` and 1 `--attach` attaches, PdfCraft with no flag and with `--control`) |
| Tool inventory of the servers | 14/14 servers, 636 tools (`pdfcraft`: the 15 window methods; `figcraft`: 18) |
| Overall diagnosis | `tutto in ordine` |

## Documentation

The documentation lives in [docs/index.md](docs/index.md): it is an **OKF v0.2** bundle, one node
per concept with explicit relations between the nodes (architecture, tools, operations, defects
found). The long, complete text, with every measurement, is
[docs/reference/craft-bridge.md](docs/reference/craft-bridge.md).

```bash
uvx okfgen validate docs --strict                      # conformant: 35 concepts, 0 errors
uvx okfgen visualize docs -o reports/okf-graph.html    # interactive graph of the bundle
```

The generated graph is in [reports/okf-graph.html](reports/okf-graph.html): 35 nodes, 182 relations.

## What is installed, against what is published

The version of an executable says what it claims to be, not whether it is the release the vendor
distributes. The ArtCraft launcher keeps on disk the list it uses to update the apps (repository,
latest release, packages with their `sha256`):
[craft-bridge-feed.py](tools/craft-bridge-feed.py) puts that list beside the installed build and
says where the two do not match. And with `--bytes` it asks the one question the version cannot
answer: it compares the installed executable with the one **inside** the published package, read
in memory without extracting anything — `--download <slug>` fetches the package (feed digest
verified before use, one app at a time, only from the feed hosts). Inside `doctor` a version
behind is a `nota`, not a `FIX`: the bridge works with the previous release too. Details in
[docs/tools/craft-bridge-feed.md](docs/tools/craft-bridge-feed.md).

## Automated checks

On every push to `main` (and on every pull request) [checks.yml](.github/workflows/checks.yml)
runs: syntax of the tools, interfaces, consistency of the app table with the documented ports,
determinism of the installer, conformance of the OKF bundle and the suite with `--ci` — which on a
runner without apps skips the environment cases **with the reason**, while a real fault stays a
FAIL. The whole suite runs on a self-hosted runner where the bridge is installed (repository variable
`CRAFTBRIDGE_SELF_HOSTED=1`): it is active on pushes to `main` and on manual runs, never on pull
requests — the repository is public, and a stranger's code does not run on the machine that hasthe apps. A case that gets worse than the saved baseline exits 3, so a regression stops the push
instead of waiting in a report. Details in [docs/operations/ci.md](docs/operations/ci.md).

## Declared limits

- **Windows only**: the suite and the launcher use `taskkill` and `DETACHED_PROCESS`.
- Window capture requires the window to be visible; an app in the background may return a timeout
  that looks like a bridge fault and is not.
- The version of the executable is not its content: two builds with the same version and no
  revision in the startup line are indistinguishable (no hash of the binary).
- The real use by an agent inside Freebuff, through the interface, has not been observed: the
  proofs talk to the binaries over the protocol.

## Licence

**MIT** — the full text is in [LICENSE](LICENSE): free use, modification and redistribution, even
inside closed products, as long as the copyright notice and the licence stay with the software.
The software is provided as is, without warranty.
