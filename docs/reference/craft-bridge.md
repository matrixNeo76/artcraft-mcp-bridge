---
type: Reference
title: "Craft Bridge - technical manual"
description: "The control channel of the Crafting Apps: protocol, bridged/headless shim, identity and build, commands and proofs."
resource: ../../docs/reference/craft-bridge.md
tags: [bridge, protocol, manual]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:23:21Z }
status: stable
---

# Crafting Apps — bridged mode of their MCP servers (experimentation)

**Date:** 13 October 2026 · **Machine:** Windows x64, user `auresystem`
**State:** all 13 apps tried live (the 12 shim apps - FigCraft, the newest, in §6.2 - and PdfCraft by translation); protocol and credentials derived from the installed binaries.

References: [analysis.md](./analysis.md) · [spec.md](./spec.md) · [plan.md](./plan.md)

---

## 1. What bridged mode is

Every Crafting App has two executables in the same folder (`C:\Program Files\<App>\`):

- `<app>.exe` — the desktop application;
- `<app>-cli.exe` — the headless CLI, which can also act as an **MCP server on stdio**.

That folder is written by hand nowhere: it is resolved by the `App Paths` registry (the
entry each app's MSI installer writes, and which Windows uses to open it by name), and the
bridge's table stays as a confirmation — see
[Where the app is](../architecture/app-locations.md). An app that moves is followed with no
configuration change.

The 12 entries of `~\.agents\mcp.json` currently use `*-cli.exe mcp`, that is a **headless
session**: in-process engine, no window, no visibility of what the user has opened.

All the apps (except PdfCraft) can do better: started with `--control PORT` they expose a
**JSON-lines control channel on 127.0.0.1** that drives the real window, and the CLI
connects to that channel with `mcp --connect` / `mcp --bridge`. That is **bridged** mode:
the agent sees and moves the open app — UI state, `ui_*` tools, screenshots of the window,
open documents.

PdfCraft cannot attach the window from its MCP server (`mcp --connect` → `unknown option`),
but it **can** drive it from the CLI through a control file: the window is therefore
**translated** into MCP tools, one method per invocation (§5, *The window translator*).

```
<app>.exe --control PORT            # the app opens the control channel
<app>-cli.exe mcp --connect PORT    # the MCP server drives that window
```

---

## 2. Matrix per app

All of it derived from the installed binaries (`craft-bridge-recon.py`) and confirmed by the
CLI help.

| App | App startup | CLI bridge flag | Shim port | Credential | Tried |
|---|---|---|---|---|---|
| `cadcraft` | `--control` (env `CADCRAFT_CONTROL_PORT`) | `mcp --connect HOST:PORT` | 7971 | — | ✅ bridged, 11→14 tools |
| `deckcraft` | `--control PORT` | `mcp --connect PORT` | 7972 | — | ✅ bridged, live screenshot |
| `designcraft` | `--control` (env `DESIGNCRAFT_CONTROL_PORT`) | `mcp --connect PORT` | 7973 | — | ✅ bridged, live screenshot |
| `effectcraft` | `--control <port>` | `mcp --bridge PORT` | 9877 | — | ✅ bridged, 27→36 tools |
| `figcraft` | `--control PORT` | `mcp --attach PORT` | 7981 | — | ✅ bridged, 18 tools, `inspect_document` live (the same 18 as headless: this CLI adds no `ui_*`) |
| `filmcraft` | `--control <port>` (env `FILMCRAFT_CONTROL_PORT`) | `mcp --bridge 127.0.0.1:PORT` | 7974 | — | ✅ bridged, `render_preview` live |
| `gridcraft` | `--control 7979` | `mcp --connect PORT` | 7975 | — | ✅ bridged, `inspect_workbook` + screenshot |
| `lightcraft` | `--control PORT` (env `LIGHTCRAFT_CONTROL_PORT`) | `mcp --connect [ADDR]` | 7980 | — | ✅ bridged, 326→**502** tools |
| `pdfcraft` | `--control FILE` (**file**, not a port) | **absent**: `mcp [--root DIR]` | dynamic port in the file | **token in the file** | ✅ window driven over MCP by **translation** (15 methods; its server has no bridge flag) |
| `photocraft` | `--control <port>` (env `PHOTOCRAFT_CONTROL_PORT`) | `mcp --bridge 127.0.0.1:PORT` | 7976 | **control-token 64-hex** | ✅ bridged, `ui_inspect` live |
| `soundcraft` | `--control` (env `SOUNDCRAFT_CONTROL_PORT`) | `mcp --connect PORT` | 7977 | — | ✅ bridged, live screenshot |
| `vectorcraft` | `--control 7979` | `mcp --connect ADDR` | 7979 | — | ✅ bridged, `inspect_ui` live |
| `wordcraft` | `--control 7981` | `mcp --connect HOST:PORT` | 7978 | **control key 64-hex** | ✅ bridged, `ui_inspect` live |

Notes from the matrix:

- The **bridge flag** column is no longer something we remember: `craft-bridge-mcp.py --flags` asks every CLI for its own help and compares (details and measurements in §5, *The attach flag*).
- **Every shim app (12 of 13) exposes `--control` as a port**; PdfCraft is the one exception — it uses a *control file* and its MCP server **has no** bridge flag. Two different roads remain: for 12 apps the bridge is the shim attaching to the channel, for PdfCraft it is a translator invoking the CLI (§5).
- The **bridge flag** is not the same name everywhere: FigCraft's CLI takes `--attach PORT` (a bare port; the others want an address), while the shim passes `--attach` exactly as it passes `--connect`/`--bridge`. The help check covers all three.
- VectorCraft is the only one declaring an **automatic fallback** to headless when the app is not there; the others, if the app is missing, **fail** (verified: GridCraft, PhotoCraft).
- `--automation-read-root` / `--automation-write-root` confine the files read/written by the agent, but **only in headless**: with `--connect` the app applies its own roots (WordCraft says so explicitly, VectorCraft too). It is a security difference to keep in mind.

---

## 3. The control protocol

The channel is JSON-lines over TCP loopback. Two apps verify a credential.

### 3.1 PhotoCraft — `control-token` (verified)

Token of **64 hexadecimal characters**. Sources, in the app's order of precedence:

```
--control-token <64-hex>
--control-token-file <path>          # PHOTOCRAFT_CONTROL_TOKEN_FILE
PHOTOCRAFT_CONTROL_TOKEN             # or the variable holding the file
```

Verified behaviour of the token lifecycle:

| App startup | Outcome |
|---|---|
| `--control 7982` (no token) | it generates a random token and **prints it**: `photocraft: control token: 71ae898c…77e3` |
| `--control-token-file` on a **non-existent** file | it generates the token and **writes the file** (65 bytes: 64 hex + newline) |
| `--control-token-file` on an existing file | it uses that one |

The **client** (`photocraft-cli`) demands a credential: without one it exits at once with

```
error: bridge mode needs --control-token, --control-token-file,
PHOTOCRAFT_CONTROL_TOKEN, or PHOTOCRAFT_CONTROL_TOKEN_FILE
```

Handshake, measured on a raw socket:

```json
→ {"id":1,"method":"auth","params":{"token":"<64-hex>"}}
← {"id":1,"ok":true,"result":{"authenticated":true}}
```

Without `auth` (or with a wrong token) every method is refused:

```json
← {"error":"authentication required","id":null,"ok":false}
```

So the gate is **in the app process**, not in the CLI: a wrong token of valid format does not
get through.

### 3.2 WordCraft — `control key` (verified)

Same idea, different name. Started with `--control 7981` the app writes the key by itself:

```
wordcraft::control_server: control server listening on 127.0.0.1:7981,
  key in C:\Users\auresystem\AppData\Roaming\WordCraft\control-key.local-7981
```

The file `control-key.local-<port>` contains 64 hexadecimal characters. The CLI finds it on
its own; alternatively the key is passed with `WORDCRAFT_CONTROL_KEY`. Handshake:

```json
→ {"id":1,"method":"auth","params":{"key":"<64-hex>"}}     ← field `key`, not `token`
← {"id":1,"ok":true,"result":{}}
```

Without authentication: `{"error":"unauthorized","id":1,"ok":false}`. Careful: if the app has
no writable settings folder, the key is **not written** and the requests are refused
(`control key file not written`).

### 3.3 PdfCraft — control file (verified)

PdfCraft does not use a port on the command line: `pdfcraft --control FILE` opens the channel
on a **random port** and writes its details into a JSON file. Measured:

```json
{ "pid": 6228, "port": 37902, "token": "<32 characters>" }
```

The CLI reads it with `ui --control FILE <method>`: `state` returns the UI state of the
window, `screenshot --out x.png` produced a `1440x920` PNG (197 KB). Here too the token is
verified by the app:

```json
→ without token    ← {"error":{"code":-32001,"message":"authenticate first: auth {token}"}}
→ {"method":"auth","params":{"token":"…"}}   ← {"result":{"ok":true}}
```

**PdfCraft's MCP server cannot be attached**: `pdfcraft-cli mcp --connect 127.0.0.1:37902`
answers `mcp: unknown option --connect`. The app can be driven, the MCP entry cannot: that
entry stays headless by construction.

Hence the second road, which is not an attach but a **translation**: if the channel cannot be
opened, one can at least ask the CLI, one method at a time, for what the MCP server cannot
expose. That is what [craft-bridge-ui.py](../../tools/craft-bridge-ui.py) does — 15 tools for
the 15 methods the app declares, with the CLI invoked once per call (§5).

Summary: **three apps out of thirteen** verify a credential on the channel (PhotoCraft `token`,
WordCraft `key`, PdfCraft `token`).

### 3.4 The handshake: who is behind the port (verified)

A successful `connect()` does not say that the peer speaks the channel. Measured: with a
socket that **accepts and then stays silent** in place of the app, the shim declared
`bridged` and the DeckCraft CLI answered `25 tool, nessun errore` — a headless session
indistinguishable from the real one by tool list. Now the choice of mode is made with a real
request:

```json
→ {"id":1,"method":"__craft_bridge_ident__","params":{}}
← {"error":"unknown method `__craft_bridge_ident__`","id":1,"ok":false}
```

The method is **deliberately non-existent**: the expected answer is the error, and that proves
the protocol without depending on a method every app should have. Signature = a JSON object
with the `id` repeated and one of `ok`/`error`/`result`.

| Handshake outcome | Meaning | Outcome of a `connect()` |
|---|---|---|
| `craft` | the peer speaks the control channel | — |
| `silent` | the port is listening but does not answer | **indistinguishable** (the case that used to deceive) |
| `foreign` | it answered, but not with the channel's signature (e.g. HTTP) | indistinguishable |
| `unreachable` | connection refused / host unreachable | distinguishable |

Where there is a credential the handshake takes a second step: `auth` with the token from the
config. `authenticated` means the peer is not just "a Craft channel", it is **ours**. No
per-app knowledge is needed: the apps of the family all answer the same request, and the
unauthenticated error only changes text (`authentication required` for PhotoCraft,
`unauthorized` for WordCraft).

**One mistake of mine, found by measuring.** On the first round the *right* token came out as
refused: I was sending the `auth` as a second request, on the connection already refused for
lack of a credential. On that socket the app no longer listens. Now the `auth` goes **first,
on a connection of its own**, and the correct token is recognised. The negative case stays
covered: wrong token → `auth rifiutata`.

The same check lives in two places, with the same outcome:
[craft-bridge-ident.py](../../tools/craft-bridge-ident.py) as a diagnosis tool, and inside
[craft-bridge-mcp.py](../../tools/craft-bridge-mcp.py) as the criterion for choosing
bridged/headless (no dependency: the shim installs as a single file).

### 3.5 Who it is, and which build: the catalogue and the listening executable (verified)

The handshake says the peer speaks the protocol, not **which** app it is. The channel does not
declare it: out of 40 candidate names (`app.version`, `version`, `about`, `app.info`, `hello`,
`identify`, `whoami`, …) none exists. The only thing that tells about itself is its own
**command catalogue**:

```json
→ {"id":2,"method":"engine.commands","params":{}}
← {"id":2,"ok":true,"result":[{"id":"file.new","label":"New Workbook",…}, …]}
```

The catalogue is app-specific, and the installed CLI knows its own (`<cli> commands`). The
comparison is therefore two-sided and with no tables to maintain:

| Peer on the port | Coverage of the local catalogue |
|---|---|
| the right app | **1.00**: every id the CLI declares also exists in the channel (0 local ids missing, except one in `vectorcraft`); the channel has more — 33–273 more |
| any other app | **≤ 0.15** (measured max 0.15, typically 0.01–0.09) |

Measured on all 11: `app` identified with coverage 1.00 and its version
(`cadcraft-cli 0.6.2`, `gridcraft-cli 0.6.1`, `lightcraft-cli 0.7.1`, `vectorcraft-cli 0.10.0`,
`SoundCraft CLI 0.6.1`, …). Two apps do not print JSON in their own catalogue (`soundcraft`
prints a table, `photocraft`/`wordcraft` ask for the credential on the channel): the table is
read separately and the `auth` has to be done first.

**The catalogue identifies the APP, not the build.** Two builds of the same app cover the same
catalogue (measured: coverage 1.00 even with a different build on the port), so the app comes
out as right while the listening executable is not the configured one: the bridge would drive
a window that is not the one you think. The build is read elsewhere, and the channel declares
none of it:

| Source | What it says |
|---|---|
| listening PID → process executable | the version of the **file** the process started from (PE version resource, via `Get-Process`/`Get-Item`) |
| app log, startup line | what the **process** claims to be: `gridcraft: GridCraft 0.6.1…`, and where present also the revision — `cadcraft 0.6.2 (00c7613f…)` |
| executable next to the configured CLI | the build the entry **would start** |
| `~/.craft-bridge/builds.json` | the build **verified** last time (`--record`) |
| `<cli> version` | the version of the **CLI**, which is not the one of the app on the port |

The startup line counts for a port only because it is followed, in the same log, by the
`control … listening on …:<port>` line: that is what ties the declaration to *that* process.
The log rotates (`gridcraft.1.log`), so all rotations are searched. When the file on disk and
the declaration diverge — an update **under** an already started process — the declaration
wins, and it is noted.

The comparison is between the build **running** and the **reference** one (in this order:
`--expect-version`, the recorded fingerprint, the configured executable):

| Outcome | Meaning | Exit |
|---|---|---|
| `same` | same version (if both known, same revision too) | 0 |
| `same` + `da <other file>` | same build, run from another path: not a fault, but it is said | 0 |
| `different` | same app, **another build**: the entry would start a different executable | 1 |
| `unknown` | no proof (PID gone, unreadable version, no reference) | 0 |

```
[craft] gridcraft    porta=7990  senza credenziale | app=gridcraft (copertura 1.0)
  | cli gridcraft-cli 0.6.1 | build 0.5.0 != config 0.6.1 (NON e' la build configurata)
  | da C:\…\craft-bridge-test\gridcraft-old.exe
```

**Tried on a second real build**, not simulated: the executable was copied and its version
resource rewritten to 0.5.0 (at unchanged length), leaving the installation untouched. On port
7990 that executable answers with GridCraft's catalogue (coverage **1.00** — for the per-app
identity it is correctly "gridcraft") and its startup line says `GridCraft 0.5.0`. With build
0.6.1 as the reference: `build=different` and exit 1; with the update under the running process
(I rename the running executable and put a new one at the same path) the running version stays
0.5.0 — the one the process declares — with the note
`l'eseguibile su disco ora dichiara 0.6.1: aggiornato sotto il processo`.

Where the verdict ends up: `craft-bridge-ident.py` (diagnosis, with `--build-only` for the
build alone without the handshake and `--record` to record the verified one),
`craft-bridge-launch.py` (which exits 1 and says *who* it found), and the shim, which warns at
startup but **proceeds bridged**: a different build speaks the same protocol, whereas silence
would hide exactly the case of driving the wrong window.

**Limit that remains:** the executable says the version, not the content: two builds with the
same version and no revision in the log are indistinguishable.

**Why it is needed.** Given another app's port, a CLI falls back to headless **without saying
so**: measured, `deckcraft-cli mcp --connect 7975` (GridCraft's port) answers `25 tool` and no
error. With identity, the case is visible at startup:

```
craft-bridge-mcp: gridcraft: sulla porta 7975 risponde un'altra app
  (copre 29/339 comandi di gridcraft): la CLI ripiegherebbe in headless senza dirlo.
  Vado headless
craft-bridge-mcp: gridcraft: modalita' headless (porta 7975, peer=craft, app estranea)
```

**Two mistakes of mine, found by measuring.** The first: reading the responses stopped at the
first `\n`, and the apps leave a stray newline after the previous answer — the second request
read an empty byte instead of a 47 KB catalogue, and the identity came out "unknown"
**intermittently** (it depended on how the bytes arrived). Now the end of the message is
recognised by parsing the JSON. The second: `soundcraft-cli commands --json` prints **nothing**
and the catalogue exists only in the textual table; without reading it, its identity stayed
unknown although it was verifiable.

---

## 4. Experimental proofs

Method: actually start the desktop app with the control channel, connect the MCP server, and
**call a tool that touches the window**. `tools/list` alone proves nothing: PhotoCraft lists
the same 25 tools even when pointed at a dead port.

| # | Proof | Measured outcome |
|---|---|---|
| 1 | PhotoCraft `--control 7981 --control-token-file` | `control server listening on 127.0.0.1:7981`, PID distinct from the app |
| 2 | bridge **without** a token | immediate refusal: `bridge mode needs --control-token …` |
| 3 | bridge with the right token | 25 tools, `serverInfo` = `photocraft 0.8.2` |
| 4 | `ui_inspect` on the live app | real UI state: `brush.size 20.0`, dock, `frame: 7` |
| 5 | `ui_set {brushSize: 33}` then `ui_inspect` | **20.0 → 33.0**: the window state changed |
| 6 | `doc_new 640x480 #204060` | `{"document":0}` — a document created in the open app |
| 7 | `ui_screenshot` | real PNGs `512x320` (21 485 B) and `640x400` (28 735 B), magic `89504e470d0a1a0a` |
| 8 | bridge with a **wrong** token | `app: authentication required` |
| 9 | bridge towards a **dead** port | `bridge: 'ui.inspect' failed: cannot connect to 127.0.0.1:7999 …; the request was not sent` |
| 10 | GridCraft `--control 7979` + `mcp --connect 7979` | `control channel listening on 127.0.0.1:7979`; 21 tools; stderr `(connected to the GridCraft app at 127.0.0.1:7979)` |
| 11 | GridCraft `screenshot` | `1440x900` PNG, 152 171 B — the real window |
| 12 | GridCraft towards a dead port | exit **1**, `cannot connect to the GridCraft app at 127.0.0.1:7999: connection timed out` — **no silent fallback** |
| 13 | WordCraft `--control 7981` + `mcp --connect` | 16 tools; `ui_inspect` → `canvasRect [22,184,1418,710]`, caret, pages |
| 14 | WordCraft raw socket without the key | `{"error":"unauthorized"}` |
| 15 | App killed **during** the session | per-call error `… is not reachable: connection timed out`, the MCP server **stays alive** |
| 16 | Wrapper with the app closed / open | it chooses `headless` / `bridged`; identical screenshot (`sha256 c41932c8db312ce7`) between direct bridge and wrapper |

Artifacts left in the repo as proof: `photocraft-live-1.png`, `photocraft-live-doc.png`,
`photocraft-pilot-report.json`, `craft-photocraft-tools.json`.

### Note on method

While writing the wrapper I introduced and then fixed a real bug: `source.read(65536)` on a
pipe **blocks** until it has 64 KB (or EOF), so the MCP messages — short ones — were never
forwarded and the client timed out. The copy now uses `os.read`/`os.write` on the descriptors,
with no buffering.

---

## 5. What I built

| File | Role |
|---|---|
| [craft-bridge-recon.py](../../tools/craft-bridge-recon.py) | extracts from the binaries the flags/credentials of the control channel (read-only, no app started) |
| [craft-bridge-probe.py](../../tools/craft-bridge-probe.py) | generic MCP probe: `initialize`, `tools/list`, one call, outcome as JSON |
| [craft-bridge-pilot.py](../../tools/craft-bridge-pilot.py) | runs a sequence of calls on the open app, saves the image artifacts |
| [craft-bridge-mcp.py](../../tools/craft-bridge-mcp.py) | **stdio shim**: it chooses bridged or headless and launches the right CLI |
| [craft-bridge-ui.py](../../tools/craft-bridge-ui.py) | **window translator**: for the app that cannot be attached, one MCP method = one CLI invocation |
| [craft-bridge-config.py](../../tools/craft-bridge-config.py) | installs shim and identity tool and rewrites the MCP entries (idempotent, with backup; it realigns the files even when the entries do not change) |
| [craft-bridge-verify.py](../../tools/craft-bridge-verify.py) | reads the written config and queries **every entry with its real command** |
| [craft-bridge-sweep.py](../../tools/craft-bridge-sweep.py) | starts one app at a time and measures the same entry headless **and** bridged |
| [craft-bridge-launch.py](../../tools/craft-bridge-launch.py) | **starts one or more apps** with the channel already active on the ports the config expects |
| [craft-bridge-ident.py](../../tools/craft-bridge-ident.py) | **who answers on the port and which build runs there**: handshake on the protocol, app recognised from the command catalogue, listening executable and version declared by the app |
| [craft-bridge-doctor.py](../../tools/craft-bridge-doctor.py) | **a single verdict on the whole assembly**: repo, installed shim, config entries, executables, attach flag, PdfCraft window, credentials and the build running on the ports; at the end the actions to take |
| [craft-bridge-tests.py](../../tools/craft-bridge-tests.py) | **the injected faults, runnable**: it breaks something on purpose (26 cases today), demands the right verdict from shim/translator/doctor/ident/launcher/connect/report, puts things back and leaves the [report](../../reports/craft-bridge-tests.md) compared with the previous run |
| [craft-bridge-connect.py](../../tools/craft-bridge-connect.py) | **the bridge in every MCP client**: it writes the same entries (one source: `craft-bridge-config.py`'s `planned_entries()`) into the JSON, TOML or YAML file each client reads, with a dry-run by default |
| [craft-bridge-report.py](../../tools/craft-bridge-report.py) | **the whole state in one place**: it gathers the doctor verdict, the entries, the clients, the baselines, the feed and the launch logs into `reports/bridge-status.json` and the page `reports/bridge-status.html` that reads it |

### Other clients and the status page

`craft-bridge-config.py` writes **one** config, the one the `.agents` clients read; the
same shim, though, can be seen by every other MCP client installed on the machine, each
with its own file and format. `craft-bridge-connect.py` closes that gap without a second
source of truth, and `craft-bridge-report.py` shows the result: one JSON and one page with
the verdict, the clients (and what each one is missing), the baselines and the logs. The
recipe, client by client — including Codex's TOML and `dsh`'s Cordis YAML patch — is the
runbook [Connect a client](../operations/connect-a-client.md).

### The shim

`craft-bridge-mcp.py` asks who is on the control port at startup and chooses the mode: if the
app's channel answers it drives the window, otherwise it uses the headless session. The same
MCP entry works in both cases — which the CLIs alone do not do. The question is not a
`connect()`: it is a handshake on the protocol (§3.4), because a listening port does not say
who is behind it.

The mode is chosen **once**, deliberately: bridged and headless expose different tool lists
(bridged adds `ui_*`), so switching mode mid-session would leave the client with a stale
`tools/list`. If the app is closed during the session, the calls give an explicit error
without killing the server.

```powershell
# entry of ~\.agents\mcp.json
{ "type": "stdio",
  "command": "C:\\Users\\auresystem\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
  "args": ["C:\\Users\\auresystem\\AppData\\Local\\Programs\\craft-bridge\\craft-bridge-mcp.py",
           "--slug", "lightcraft", "--port", "7980"] }
```

### The attach flag, verified

The table says which option is needed to drive the window (`--connect` for eight apps,
`--bridge` for three, `--attach` for one — FigCraft) and for PdfCraft it says there is no flag. It is a declaration about an
interface that is **not ours**: the CLI belongs to another piece of software and can change
without asking. The bridge runs that flag at every start, so getting it wrong would only show
up at the first connection.

That is why the flag is asked of the party concerned: `craft-bridge-mcp.py --flags` launches
every CLI's `--help` (in parallel, ~0.4 s for thirteen) and compares. Three outcomes: `ok` (the
help names the declared flag; or, for the app with no attach, names none and documents
`--control`), `diverge` (the table claims an option the help does not name — or the help names
one the table does not use), `non leggibile` (the CLI prints no help: it stays a declaration,
and it is written down as one).

Measured on 13 October 2026: **12/12** CLIs document the declared flag, and `pdfcraft-cli
--help` names neither `--connect` nor `--bridge` but shows `ui --control FILE [method]` — the
same thing the table claims, verified instead of remembered. The verdict sits in the diagnosis
as the `flag di aggancio` line: **13/13** confirmed, and a table not confirmed is a `FIX` with
the action to take (demonstrated by injecting a test table with `doctor --apps-file`, which is
also how the suite proves it).

### The window translator (PdfCraft)

`craft-bridge-ui.py` is the answer to the question the channel did not allow to be asked: if
PdfCraft's MCP server has no bridge flag, the way to bring the window to an MCP client is to
**translate its calls into CLI invocations** — one process per method. The client sees a normal
MCP server (`serverInfo: pdfcraft-ui`) with the 15 tools the app declares it can do; every
`tools/call` becomes `pdfcraft-cli ui --control FILE <method> [key=value ...]`, with the values
serialised as JSON so the CLI re-reads them with the right type (a `true` string stays a
string).

For the rest, the choices are those of the bridge:

* **two modes, declared**: a window that answers → the 15 methods of the window; window closed
  → delegation to the vendor's headless server, byte for byte. `--require-bridge` exits 3
  instead of falling back;
* **the catalogue is not taken at its word**: the app lists its own methods when it receives an
  unknown one, and `--list` compares — measured `15 metodi nostri, 15 dall'app: coincide`;
* **a fault of the app is not a fault of the bridge**: it arrives as `isError`, with the CLI
  message (`no enabled clickable widget labelled …`) and below it the diagnosis only the bridge
  can produce;
* **the CLI is resolved from the system** (`App Paths`), as for the shim: no path written by
  hand.

Measured live (13 October 2026, `1440x920` window on port 48129, CLI `pdfcraft-cli 0.7.1`):
`initialize` 0.23 s and `tools/list` 15 tools; `ui_state` 0.05 s; `ui_commands` **192
commands**; `ui_inspect` **107 widgets**; `ui_screenshot` 0.20 s → 197 KB PNG returned as image
content ([reports/pdfcraft-finestra.png](../../reports/pdfcraft-finestra.png)); `ui_click` on a
non-existent label → `isError` with the app's message.

The price, declared: **one process per call** (no shared state) and the change of catalogue.
With the window open the entry exposes the 15 window methods; with the window closed the 161
tools of the vendor's headless server. It is the same rule as the shim — one mode or the other
— but here the switch is visible in the number of tools, because the two catalogues really are
different.

### The installer

```powershell
python craft-bridge-config.py            # dry-run: says what would change
python craft-bridge-config.py --apply    # installs shim, ident and translator; backup; rewrites the 12 entries
python craft-bridge-config.py --restore  # brings the entries back to headless `mcp`
```

It protects what does not belong to it (`artcraft`, the protocol proxy, is **not touched**), and
before writing it creates `mcp.json.bak-<timestamp>`. PdfCraft is no longer the exception: its
entry is written by the installer, like the others, but it **names the translator** instead of
the shim and carries no port — the app picks that and writes it into the control file.

### Applied on 13 October 2026

```
da aggiornare (11): cadcraft, deckcraft, designcraft, effectcraft, filmcraft, gridcraft,
                    lightcraft, photocraft, soundcraft, vectorcraft, wordcraft
non toccate  : pdfcraft, artcraft
installato   : %LOCALAPPDATA%\Programs\craft-bridge\craft-bridge-mcp.py
backup       : ~\.agents\mcp.json.bak-20261013-135250
```

Re-run of the installer: `da aggiornare (0), invariate (11)` — no writing, no new backup. The
installed shim is **identical** to the copy in the repo (`md5
8c4250537950d10d457a2edacf9bcdfe`).

> On 13 Oct the installed copy was realigned by hand several times (after the docstring, after
> the identity handshake, after the identity from the command catalogue). The 11 config entries
> never changed, so for the installer they stay unchanged.
>
> Practical note: the MCP entries run the **installed** file, not the one in the repo. After
> every change to the shim: `cp craft-bridge-mcp.py "%LOCALAPPDATA%\Programs\craft-bridge\"` —
> otherwise you measure the old version (it happened during this proof).

---

## 6. Verification of the applied entries

Every entry was exercised **with the command exactly as written in `~\.agents\mcp.json`**, not
with a convenient variant ([craft-bridge-verify.py](../../tools/craft-bridge-verify.py)).

**All apps closed** — `--expect headless`: 13/13 OK, the 11 shim entries go headless,
`artcraft` (61 tools) and `pdfcraft` (161 tools) keep answering after the rewrite.

**Updated on 13 October 2026, after the translator**: the mode is read for the PdfCraft entry
too, which does not go through the shim. Measured with the window open:
`pdfcraft modo=bridged tool=15` and the same line becomes a KO with `--expect headless` — that
is, the mode is verifiable there too. The summary is now **13/13 entries OK, 12 with a bridge**
(11 from the shim, `pdfcraft` from the translator).

> **Update, same day**: with **FigCraft** added the numbers move by one — **14/14 entries OK,
> 13 with a bridge** (12 from the shim, `pdfcraft` from the translator). The measurements below
> were taken before it and are left as they were; the app is measured in §6.2.

**Three apps open** on the ports the config expects (GridCraft 7975, PhotoCraft 7976 with the
config's token, WordCraft 7978):

| Entry | Chosen mode | Tools | Call on the open app |
|---|---|---|---|
| `gridcraft` | **bridged** | 21 | `inspect_workbook` → `activeCell A1`, `mode Ready`; `screenshot` → 1440x900 PNG |
| `photocraft` | **bridged** | 25 | `ui_inspect` → UI state of the window |
| `wordcraft` | **bridged** | 16 | `ui_inspect` → `canvasRect [22,184,1418,710]`, caret |
| other 8 | headless | 11–326 | — |

Combined run: **13/13 entries OK**, 3 bridged and 8 headless in the same pass. In that proof
only those three apps were open: the other eight were headless *because* they were closed, not
because they were unable to bridge — the full proof is in §6.1.

### Two traps, both fixed

The first `screenshot` on GridCraft failed with `GridCraft app at 127.0.0.1:7975 is not
reachable: … mancata risposta dall'host connesso`, **while on the same bridge
`inspect_workbook` worked**. Isolating the variable brought out two distinct causes, and I
fixed both in the harness:

1. **Window occlusion.** The capture tools photograph the live window: if it stays behind the
   others it does not redraw and the call times out. Brought to the foreground, the `1440x900`
   PNG arrived at once. The sweep now brings the window forward before calling.
2. **Missing required argument.** The sweep called `screenshot` with `{}`. That is not enough:
   `GridCraft` wants `path`, and with an empty argument the tool answers without capturing
   anything. The signal that revealed it was case 2 of the sequence — failed **even** with the
   window in the foreground. Now the sweep reads the schema and fills `path`/`out` when they
   exist.

**Practical consequence for an agent:** before declaring "the bridge does not work", check (a)
that the window is visible and (b) that you passed the arguments the tool schema requires. A
timeout on `screenshot` does not mean the channel is dead — `inspect_workbook` was answering.

Note: the apps do not all behave the same. `cadcraft` and `deckcraft` accept `screenshot`
without `path` (they write to a path of their own); `gridcraft`, `designcraft`, `effectcraft`
and `soundcraft` want the path.

### 6.1 Sweep over all the apps

[craft-bridge-sweep.py](../../tools/craft-bridge-sweep.py) starts one app at a time on the
expected port, measures the entry **before** (app closed) and **after** (app open), discovers
the tools that appear only in bridged and really calls one of them. **11/11 shim apps went
bridged**, each with a successful call on the live window. PdfCraft has no port to probe, so it
is not part of this sweep: it is verified by `craft-bridge-ui.py --list`, the `doctor` (line
`finestra pdfcraft`) and `craft-bridge-launch.py --apps pdfcraft --verify`.

| App | Headless tools | Bridged tools | App-only tools | Successful call |
|---|---|---|---|---|
| `cadcraft` | 11 | 14 | 3 | `screenshot` → 1600x1000 PNG |
| `deckcraft` | 25 | 25 | 0 | `screenshot` → 1440x900 |
| `designcraft` | 25 | 25 | 0 | `screenshot` → 1440x900 |
| `effectcraft` | 27 | **36** | 9 | `screenshot` → 1600x956 |
| `filmcraft` | 17 | 17 | 0 | `render_preview` → live window |
| `gridcraft` | 21 | 21 | 0 | `screenshot` → 1440x900 (with `path`) |
| `lightcraft` | 326 | **502** | **176** | `ui_inspect` → UI state |
| `photocraft` | 25 | 25 | 0 | `ui_inspect` → UI state |
| `soundcraft` | 17 | 17 | 0 | `screenshot` |
| `vectorcraft` | 32 | 32 | 0 | `inspect_ui` → documents/canvas |
| `wordcraft` | 16 | 16 | 0 | `ui_inspect` → `canvasRect`, caret |
| `pdfcraft` | 161 | **15** (translator) | 15 window methods | `ui_state`, `ui_screenshot` → 1440x920 PNG (port 48129, pid 42336) |

**Lesson: the number of tools is not an indicator.** Seven of eleven apps expose the **same**
list of names in headless and in bridged: what changes is *where they act* — in headless
`screenshot` renders the document, in bridged it photographs the window. An agent comparing
counts concludes "nothing changed" and is wrong: the difference is only visible by calling.
PdfCraft is the opposite extreme, and there the number *does* say something: 161 tools of the
vendor's headless server against the **15 window methods** of the translator — two really
different catalogues, served by two different things. In both cases the reliable signal remains
stderr, which declares `modalita' bridged` or `modalita' headless`.

The raw sweep report is in [craft-bridge-sweep.json](../../reports/craft-bridge-sweep.json):
for every app it contains the two tool lists, the app-only names, the startup command used and
the outcome of the call. The sweep table predates FigCraft; the app was measured separately
(§6.2).

### 6.2 FigCraft, the newest app — and PdfCraft checked again (verified)

**FigCraft** (installed 12 Oct, registered in `App Paths` as `C:\Program Files\FigCraft\figcraft.exe`)
is not in the launcher's feed yet, so the feed lists 13 apps and does not name it: the
comparison with the published release reports it as *absent* rather than counting it among the
aligned ones. The bridge serves it like the others, and its channel answers the shim's own
handshake.

| Step | Measured |
|---|---|
| App opens the channel | `figcraft --control 7981` → log line `FigCraft control server listening on 127.0.0.1:7981` |
| Handshake | `__craft_bridge_ident__` → `{"error":"unknown method …","id":1,"ok":false}`: same JSON-lines protocol, `peer=craft` |
| Catalogue | `engine.commands` → **536** ids; `figcraft-cli commands --json` → the same **536**, coverage **1.00** (the identity check that spots the wrong app works unchanged) |
| Bridge flag | `figcraft-cli mcp --attach 7981` → `attached to the FigCraft app at 127.0.0.1:7981`; the CLI help documents `--attach` |
| Tools | **18** — `list_commands run_command batch create_node set_properties inspect_document get_node select export screenshot open_file save_file undo redo pointer key type_text inspect_ui`; **the same 18 in headless**, unlike the apps whose bridged mode adds `ui_*` |
| Call on the window | `inspect_document` → the open document (`Untitled`, page 1, layers) |
| Through the config | the entry written by the installer runs the shim, which declares `modalita' bridged (porta 7981, peer=craft)`; `doctor` confirms `figcraft 0.5.1 = config (stessa build)` |

The CLI (0.5.1, like the app) takes a **bare port** for `--attach` ("--attach needs a port
number"); the shim passes it exactly as it passes `--connect`/`--bridge`, so nothing in its mode
decision changed.

**PdfCraft checked again** (the bridge that had been “no response”): with a window open,
`craft-bridge-ui.py --list` reports `bridged (la finestra risponde e autentica)`, port 61864,
pid 38136, `pdfcraft-cli 0.7.1`, `catalogo: 15 metodi nostri, 15 dall'app: coincide`; the
configured entry serves the 15 `ui_*` tools and `ui_commands` returns the window's own commands.
`craft-bridge-launch.py --apps pdfcraft` starts it and confirms the channel. It is the same
result as the first measurement, reproduced: the translation doesn't depend on the window having
been started by the bridge.

---

## 7. How it is used in practice

1. **A single command** starts the apps with the channel already active on the port the shim
   expects ([craft-bridge-launch.py](../../tools/craft-bridge-launch.py)):

   ```bash
   python craft-bridge-launch.py                          # every app in the config
   python craft-bridge-launch.py --apps gridcraft,wordcraft
   python craft-bridge-launch.py --verify                 # + end-to-end proof of the shim
   python craft-bridge-launch.py --list                  # table and state, starts nothing
   python craft-bridge-launch.py --apps gridcraft --dry-run
   ```

   The ports are **not** written in the script: it reads them from the shim config
   (`~\.agents\mcp.json`), that is from the `--port` that `craft-bridge-mcp.py --slug <app>
   --port <port>` will probe. If a port is changed in the config one day, the command follows
   on its own. The executables and the token flag come from the wrapper's table
   (`--dump-apps`), so there is a single source there too.

   What it does, in order: it skips the apps whose channel is already up; it starts the others
   **detached from the shell** (`DETACHED_PROCESS`, so the windows stay open after the command
   returns) with `--control <port>` and, for PhotoCraft, `--control-token-file` on the **same**
   file as the config; it waits for all the channels in parallel; it reads in each app's log the
   line announcing the listen and asks the peer who it is (handshake, §3.4).

   The output, for every app: the log line with which the app announces the channel, the
   identity of the peer (`peer=craft`, `app=<slug>` with the catalogue coverage, the version of
   the binary, `autenticato` where there is a credential) and, with `--verify`, the shim's mode.

   | Exit | Meaning |
   |---|---|
   | 0 | every requested app has the channel active (and in bridged, with `--verify`) **and the configured build** |
   | 1 | at least one does not: the `diagnosi` line says why, with the tail of the log (or because another build runs on the port) |
   | 2 | usage error (unknown slug, duplicate port) |
   | 3 | unreadable config or app table |

   The command is **honest about what it proved**: "attivo" means either that the app itself
   wrote that it is listening, or that the peer answered the handshake; a port occupied by
   something else is called "occupata da altro (handshake: silent)" and exits 1 — see §8. The
   `build` line says which version really runs on that port, and a build different from the
   configured one exits 1 even with the channel active (§3.5). To know who is listening without
   starting anything: `python craft-bridge-ident.py --all`.

   If instead the question is "is everything in order?", the answer is in a single command:
   `python craft-bridge-doctor.py` — see below.

   ```bash
   python craft-bridge-ident.py --all                    # who is on every port
   python craft-bridge-ident.py --slug photocraft --token-file ~/.craft-bridge/photocraft.token
   python craft-bridge-ident.py --all --wait 30          # waits for the app to answer
   python craft-bridge-ident.py --all --record           # records the verified builds
   python craft-bridge-ident.py --port 7975 --build-only # the build only (PID + file, ~1 s)
   python craft-bridge-launch.py --apps gridcraft --record-builds   # records while starting
   ```

   **One command for the assembly.** The checks that hold the bridge up were scattered over
   several tools; [craft-bridge-doctor.py](../../tools/craft-bridge-doctor.py) asks them all and
   closes with a single line:

   ```
   craft-bridge doctor
     ok   repo            4 strumenti presenti (mcp 3bed1c535edb, ident 8df181789548, config 7776f22be252, feed 8f0bf116b72d)
     ok   shim installato 2 file identici al repo (…)
     ok   config          11 entry come le scriverebbe l'installer
     ok   percorsi        tutti i file citati dalle entry esistono
     ok   eseguibili      11 CLI e 11 app presenti (versioni: 0.10.0, 0.6.1, …)
     ok   posizione app   11 percorsi su 11 dal registro App Paths: la tabella conferma, non decide
     ok   pubblicato      11 app allineate alla release pubblicata (feed del …)
     ok   app aperte      0 su 11 porte in ascolto: tutte headless, nessuna app aperta
     nota impronte        build non registrate: cadcraft, deckcraft, …

   VERDETTO: tutto in ordine (nessuna azione)
   ```

   The ninth check, `posizione app`, is the new one: the path of app and CLI is dictated not by
   the hand-written table but by the `App Paths` registry (`cli_source`), and when the two
   diverge the line shows it — see [Where the app is](../architecture/app-locations.md).

   It duplicates nothing: it asks the expected entries to `craft-bridge-config.py` (the same
   function that writes them) and the builds to `craft-bridge-ident.py` (the same functions as
   the diagnosis), so the three cannot diverge. The proofs, all run: installed shim altered by
   one byte → `FIX shim installato` with the different hash and the action that repairs it (and
   `--apply` really repairs it: the doctor then confirms `ok`); changed entry and non-existent
   `command` → `FIX config` + `FIX percorsi`; missing executable → `FIX eseguibili`; **build
   0.5.0** on gridcraft's port → `FIX porta 7975 … gira 0.5.0 invece di 0.6.1`; GridCraft on
   deckcraft's port → `FIX porta 7972 … risponde un'altra app (copre 0.11 dei suoi comandi)`;
   PhotoCraft started with a token **different** from the config's → `FIX porta 7976 … l'app ha
   rifiutato la credenziale` (the value is never printed, only the outcome is visible).

   | Exit | Meaning |
   |---|---|
   | 0 | nothing to fix (the `nota` lines do not count: they are facts, not faults) |
   | 1 | at least one thing to fix, listed at the end with the action |
   | 2 | usage error |
   | 3 | unreadable config or app table |

   `--no-live` skips the ports (repo, shim, config, executables only), `--json` gives
   `checks`/`problems`/`actions` for another program. Full cost: ~2.4 s with the apps closed,
   a few seconds more with them open (one catalogue read per occupied port).

   ### The suite: the same faults, runnable

   The proofs told here used to be manual, one by one. Now they live in
   [craft-bridge-tests.py](../../tools/craft-bridge-tests.py), which **breaks something on
   purpose** and demands the right verdict from shim, doctor, ident and launcher:

   ```
   craft-bridge tests
     ok   stato pulito               doctor: nessuna azione
     ok   shim installato stantio    accusato e riparato dall'azione indicata
     ok   entry di config sbagliata  doctor e installer concordano: 1 entry da aggiornare
     ok   percorso inesistente       FIX percorsi: cadcraft.command
     ok   eseguibile mancante        lightcraft app, lightcraft cli
     ok   posizione dell'app dal sistema registro prima, tabella poi, e l'assenza si dichiara
     ok   app registrate dal sistema 11/11 percorsi dal registro App Paths, tabella confermata
     ok   confronto col feed del launcher 9 righe: dietro, pari, assente, estraneo e i tre casi di byte
     ok   byte pubblicati contro installati uguali ok, diversi FIX, archivio manomesso FIX
     ok   feed assente non e' un guasto doctor: nota con la ragione, non un FIX
     ok   feed illeggibile o estraneo assente 3, illeggibile 3, estraneo 0
     ok   porta chiusa               ident unreachable, shim headless (porta 7979)
     ok   app giusta sulla porta     gridcraft 7975: ident/doctor/launcher tutti d'accordo
     ok   build diversa              doctor, ident e launcher: tutti e tre exit 1 con 0.5.0 != 0.6.1
     ok   altra app sulla porta      GridCraft su 7972: doctor e ident lo riconoscono
     ok   credenziale rifiutata      token diverso: accusato da doctor e ident (valore mai stampato)
     ok   argomenti della chiamata   numeri, stringhe (virgolette), liste, null e booleani come li vuole la CLI
     ok   sessione del traduttore    15 tool, parametri tipizzati, immagine, isError su guasto, -32602 sull'ignoto, modo bridged dichiarato, finestra sparita a meta' sessione diagnosticata
     ok   senza finestra il traduttore ripiega nessuna finestra: il server headless del fornitore passa attraverso, dichiarato
     ok   finestra PdfCraft dal vivo porta 48129 (pid 42336), 15 metodi come li dichiara l'app
     ok   flag di aggancio, verificato confermato, non confermato, flag diverso, assenza confermata e help illeggibile
     ok   doctor: flag non confermato tabella non confermata -> FIX con l'azione; confermata dal canale -> ok
     ok   flag di aggancio dal vivo  11/11 CLI documentano il flag della tabella, e la diagnosi lo ripete

   23 passati, 0 falliti, 0 saltati
   ```

   `--static` runs only the cases that start no app (20 of 24, ~34 s); the full suite **starts
   real apps on free ports** and takes ~72 s. The cost grew with that of the tools that talk to
   the CLIs (every `doctor` asks the help of thirteen CLIs and queries the translator): that is
   why the suite asks the doctor only what a single line cannot say. The safety rules are in the
   docstring and always hold: the real config is never written (the cases exercise it on a copy
   with `--config`), the only real file touched is the installed shim — one byte more, inside a
   `try/finally` that puts it back, with the `--apply` the suite itself runs; if a port is
   occupied the case is **skipped** instead of killing something it did not start; temporary
   files, logs and test tokens are removed (verified: a second run in a row, 16/16).

   Every run leaves **two reports** beside it —
   [craft-bridge-tests.json](../../reports/craft-bridge-tests.json) for the machine (outcome,
   duration, fingerprints of the tools, cases) and
   [craft-bridge-tests.md](../../reports/craft-bridge-tests.md) for the reader — and the
   comparison with the previous run is **automatic**: the baseline is the json that is about to
   be overwritten, and the differences (cases changed, appeared or disappeared, fingerprints of
   the tools) end up both on screen and in the markdown, with the duration set aside as context,
   so two runs days apart can be read without reconstructing them from memory. To compare any
   two reports: `--compare old.json`; `--no-report` writes nothing, `--no-compare` reads nothing.
   The destination is given with `--report`, or with `--out` as in the other tools of the
   project.

   **Two defects found precisely by automating.** The first, in the binaries: with a refused
   credential the app **closes the connection**, and the next `sendall` raised
   `ConnectionAbortedError` — `ident` died with a traceback and **no verdict** (exit 1, empty
   stdout); the installed shim could have done the same at startup, that is, lose the MCP
   server. Now a network error does not raise: what was read is returned, and the verdict is
   given all the same. The second, about process: after changing the shim or a tool, the
   **installed** files stay behind until `--apply` is run — the suite flags it at once as
   `FAIL stato pulito` with the doctor line that explains it.

2. In Freebuff: **Connectors → Refresh**. The open apps become driveable; the closed ones stay
   headless.

For the apps without a credential, the first command is enough without
`--control-token-file`. The expected ports are the shim's ladder: `cadcraft 7971`, `deckcraft
7972`, `designcraft 7973`, `filmcraft 7974`, `gridcraft 7975`, `photocraft 7976`, `soundcraft
7977`, `wordcraft 7978`, `vectorcraft 7979`, `lightcraft 7980`, `figcraft 7981`, `effectcraft 9877` (the last
three are the defaults documented by the respective CLIs).

The same step by hand, if you need one app and an explicit command:

```powershell
& "C:\Program Files\PhotoCraft\photocraft.exe" --control 7976 `
    --control-token-file "$HOME\.craft-bridge\photocraft.token"
```

The token file is written by the app: it need not be invented nor put into chat.

---

## 8. Limits and what is not verified

- **13 of 13 apps driven and verified live**, each with a successful call on the window (§6.1).
  For 12 the road is the shim attached to the channel; for PdfCraft it is the **translator**
  invoking the CLI: neither is an attach to the vendor's MCP server, which for PdfCraft does not
  exist.
- **Startup**: [craft-bridge-launch.py](../../tools/craft-bridge-launch.py) was tried **on all
  11 apps in a single call** (`--verify`: channel up, log line, **app identified with coverage
  1.00**, shim in bridged, 11/11, exit 0; the bridged tools match the ones measured in §6.1 —
  `lightcraft 502`, `effectcraft 36`, `cadcraft 14`), on the relaunch with the channel already
  active (it does not restart, does not duplicate) and on the hard cases: mute peer, a peer
  speaking another protocol, **wrong app on the port**, a token in the config different from the
  app's, `--dry-run`, `--json`, duplicate ports, unknown slug. The same proofs talk to the
  binaries over the protocol, not to the Freebuff chat: the agent that uses those servers
  through the interface remains unobserved.
- **Window capture**: it requires the window to be visible (see §6). An agent calling
  `screenshot` on an app in the background may receive a timeout error that looks like a bridge
  fault and is not.
- **Bridged mode used to fall back silently on a mute peer — now it does not** (measured and
  fixed on 13 Oct). With a socket that **accepts the connection and then stays silent** in place
  of the app, the shim declared `modalita' bridged` and the DeckCraft CLI answered `25 tool,
  nessun errore`: headless in disguise, indistinguishable by tool list. The choice of mode is now
  made with the handshake (§3.4): `peer=silent`/`foreign` → the shim goes **headless** and writes
  it to stderr; the launcher exits 1; `craft-bridge-ident.py` gives the verdict. Tried in the
  three cases: mute → headless, foreign HTTP → headless, real app → bridged.
  - The **wrong app** on the port is recognised too (§3.5): the handshake says the peer speaks
    the protocol, the command catalogue says *which* app it is. Measured: 1.00 coverage for the
    right app, ≤ 0.15 for any other; with the wrong app the shim goes headless and the launcher
    exits 1.
  - The **build** on the port is recognised (§3.5): the app identifies itself with the catalogue,
    the version with the PID of the port, the executable of that process and the startup line the
    app writes by itself. Measured on a second real build of the same app (0.5.0 against 0.6.1):
    catalogue coverage **1.00** — for the per-app identity it is "the right app" — and
    `build=different`, with `ident`/launcher exiting 1 and the shim warning at startup but
    proceeding bridged. Also tried: the case where the executable is updated **under** the
    process (rename + new file at the same path): the running version stays the one declared by
    the process, with the note that the file on disk is now something else.
  - Limit that remains: the executable says the version, not the content. Two builds with the
    same version — and no revision in the startup line — are indistinguishable; the comparison is
    not an integrity check (no hash of the binary).
  - **The installed shim did not follow the repo — now it does** (found by putting the build check
    to work). `craft-bridge-config.py` copied the shim **only** if a config entry changed: with 11
    entries already in place the command said "da aggiornare (0)" and the installed shim stayed
    the old one (different hashes, measured). Now it compares the files and realigns them when
    needed, and it installs [craft-bridge-ident.py](../../tools/craft-bridge-ident.py) next to the
    shim too — it is what answers the question about the build, so without that file the installed
    shim could not ask it. Idempotent: on the second run it rewrites nothing.
  - Cost: when an MCP server starts, the handshake adds one request (milliseconds with the app
    alive; up to ~4.5 s with a mute peer, before declaring headless). With `--require-bridge` an
    unidentified peer exits 3 instead of falling back.
- **No proof of persistence**: every measurement is on a freshly started app, one at a time. The
  behaviour with several apps open at once and with the user working inside has not been
  measured.
- **PdfCraft**: it uses a control file with port+token and its MCP has no `--connect`/`--bridge`,
  so there is no way to attach the window from the vendor's server. The window is driven by
  translation (§5), with two declared limits: **one CLI process per call** (no shared state
  between calls, ~0.05–0.25 s per call) and the **catalogue switch** between the two modes (15
  window methods against 161 headless tools). That the window is closed *during* a session is
  handled and proved: the suite case shuts down the fake PdfCraft mid-session and demands an
  `isError` with the diagnosis (`la finestra non risponde piu'…`) instead of an answer that looks
  successful — with the fake peer, not by closing the real app mid-session.
- **`--automation-read-root`/`--automation-write-root` are not effective in bridged** (the app
  applies its own roots): the shim configuration does not pass them, so in bridged the boundaries
  are decided by the app. To be assessed before giving an agent access to files on a shared
  machine.
- **Other clients not updated**: the rewrite concerns only `~\.agents\mcp.json` (Freebuff). Claude
  Code, Claude Desktop and Antigravity stay on the headless entries: there, bridged is added with
  an equivalent change to their files.
- **The Freebuff chat/UI was not observed**: the experiments use the binaries and the protocol,
  not the app's interface.
- The test tokens live in `~\.craft-bridge\` (created during the experiments) and the WordCraft
  key in `%APPDATA%\WordCraft\control-key.local-7981`: they are local files of the user, outside
  the repo.
