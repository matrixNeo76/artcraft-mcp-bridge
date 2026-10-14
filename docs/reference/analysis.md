---
type: Reference
title: "ArtCraft MCP ecosystem analysis"
description: "Inventory of the 13 configured MCP servers, the working environment, the decisions taken and the state of the bridge."
resource: ../../docs/reference/analysis.md
tags: [analysis, mcp, inventory]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:23:21Z }
status: stable
---

# ArtCraft — analysis for the global MCP integration

**Analysis date:** 13 October 2026 — updated on 13 October 2026 with the bridged-mode experimentation (§10)
**Machine:** Windows x64, user `auresystem`
**State:** analysis document — **no change applied**, pending confirmation

---

## 1. Context and goal

The user has:

1. installed the **ArtCraft launcher** (`artcraft-launcher-0.3.2-windows-x64.msi`);
2. unpacked **ArtCraft MCP v1.1.0** into `C:\Users\auresystem\Downloads\artcraft-mcp-v1.1.0`.

Stated goal: to understand **how to make it available globally to Freebuff and the other
frameworks** (Claude, Codex, dsh harness), whether it takes **one skill per application of the
suite** or whether MCP v1.1.0 is enough, and what is **really installed** on the machine.

References provided: <https://github.com/storytold/artcraft> · <https://github.com/theCosmicCrafter/artcraft-mcp>

---

## 2. Method

Everything that follows was **verified directly on the machine** (Windows registry, MSI tables,
launcher feed, client configs, running the binary) and integrated with the official
documentation of the repositories. Claims that cannot be verified are marked explicitly.

Test run on the binary (real MCP handshake):

```
echo '{"jsonrpc":"2.0","id":1,"method":"initialize",...}' | bin\artcraft-mcp.exe
→ {"result":{"protocol_version":"2025-03-26","server_info":{"name":"artcraft-mcp","version":"0.1.0"}}}
tools/list → 61 tool
```

---

## 3. Inventory of what is really installed

### 3.1 Launcher — INSTALLED (via MSI)

| Item | Verified value |
|---|---|
| ProductName | `ArtCraft Launcher` |
| Version | `0.3.2` |
| Publisher | `Learning Machines LLC` |
| ProductCode | `{252C0C55-6539-443D-A917-D873F8E3A822}` |
| Installation | `%LOCALAPPDATA%\Programs\ArtCraft Launcher\artcraft-launcher.exe` |
| Data/state | `%LOCALAPPDATA%\ArtCraft Launcher\` (`feed.json`, `releases.json`, `downloads\`) |
| MSI content | **a single file**: `artcraft-launcher.exe` |

### 3.2 What the launcher installs (official feed)

`feed.json` lists **13 apps** — the launcher plus **12 Crafting Apps**:

| App | Repo | Tag |
|---|---|---|
| ArtCraft Launcher | storytold/craft-launcher | v0.3.2 |
| CADCraft | storytold/cadcraft | v0.6.2 |
| DeckCraft | storytold/deckcraft | v0.6.1 |
| DesignCraft | storytold/designcraft | v0.7.1 |
| EffectCraft | storytold/effectcraft | v0.9.2 |
| FilmCraft | storytold/filmcraft | v0.7.2 |
| GridCraft | storytold/gridcraft | v0.6.1 |
| LightCraft | storytold/lightcraft | v0.7.1 |
| PdfCraft | storytold/pdfcraft | v0.7.1 |
| PhotoCraft | storytold/photocraft | v0.8.2 |
| SoundCraft | storytold/soundcraft | v0.6.1 |
| VectorCraft | storytold/vectorcraft | v0.10.0 |
| WordCraft | storytold/wordcraft | v0.6.1 |

> Note: the website also lists **FigCraft**, and it **is** installed here, but it does not
> appear in the local launcher feed (verified: exactly 13 entries, and `figcraft` is not one
> of them). The launcher's `releases.json` names its repository (`storytold/figcraft`); the
> feed that lists what to install does not include it yet, so the bridge's comparison with
> the published release reports it as *absent* instead of aligned. The bridge serves it all
> the same — see [the manual](craft-bridge.md) §6.2.

### 3.3 Actual state of the suite — ALL 13 APPS INSTALLED

> **⚠️ Correction (13 Oct 2026, after verification).** A first reconnaissance concluded "no app
> installed": that was **wrong**. I was only looking in `%LOCALAPPDATA%\Programs`, whereas the
> Crafting Apps are installed **machine-wide in `C:\Program Files\<App>\`**. Correct check:

Windows registry (`Uninstall`): `CADCraft 0.6.2`, `DeckCraft 0.6.1`, `DesignCraft 0.7.1`,
`EffectCraft 0.9.2`, `FigCraft 0.5.1`, `FilmCraft 0.7.2`, `GridCraft 0.6.1`, `LightCraft 0.7.1`,
`PdfCraft 0.7.1`, `PhotoCraft 0.8.2`, `SoundCraft 0.6.1`, `VectorCraft 0.10.0`, `WordCraft 0.6.1`
(13 apps; `FigCraft` was installed later than the first reconnaissance and is the newest of
the suite).

Every app installs **two executables** in `C:\Program Files\<App>\`:

| File | Role |
|---|---|
| `<app>.exe` | desktop application (GUI) |
| `<app>-cli.exe` | headless CLI, exposing the **`mcp`** subcommand |

| App | CLI | Version | MCP |
|---|---|---|---|
| CADCraft | `cadcraft-cli.exe` | 0.6.2 | ✅ Connected |
| DeckCraft | `deckcraft-cli.exe` | 0.6.1 | ✅ Connected |
| DesignCraft | `designcraft-cli.exe` | 0.7.1 | ✅ Connected |
| EffectCraft | `effectcraft-cli.exe` | 0.9.2 | ✅ Connected |
| FilmCraft | `filmcraft-cli.exe` | 0.7.2 | ✅ Connected |
| GridCraft | `gridcraft-cli.exe` | 0.6.1 | ✅ Connected |
| LightCraft | `lightcraft-cli.exe` | 0.7.1 | ✅ Connected |
| PdfCraft | `pdfcraft-cli.exe` | 0.7.1 | ✅ Connected |
| PhotoCraft | `photocraft-cli.exe` | 0.8.2 | ✅ 25 tool |
| SoundCraft | `soundcraft-cli.exe` | 0.6.1 | ✅ Connected |
| VectorCraft | `vectorcraft-cli.exe` | 0.10.0 | ✅ Connected |
| WordCraft | `wordcraft-cli.exe` | 0.6.1 | ✅ 16 tool |

- The CLIs are **not on the PATH**: the MCP config must use the **absolute path**.
- The **generative** ArtCraft desktop app (`storytold/artcraft`) is **not** installed:
  `%LOCALAPPDATA%\ai.artcraft.app\` and the credentials in `~\Artcraft\credentials\` are absent.

**Correct conclusion:** the Crafting Apps suite is **fully installed and working**.

### 3.4 MCP v1.1.0 package — extracted, not registered

| Item | Value |
|---|---|
| Path | `C:\Users\auresystem\Downloads\artcraft-mcp-v1.1.0` |
| Binary | `bin\artcraft-mcp.exe` (10.26 MB, Rust, self-contained, zero dependencies) |
| Tools exposed | **61** (verified with `tools/list`) |
| Protocol | `2025-03-26` |
| Authentication | ArtCraft cookie/session (NOT present → the server starts but the calls will fail) |
| Skills included | `skills/artcraft-mcp/SKILL.md` + 6 references; `skills/open-source-contributor/` |

Discrepancies inside the package worth knowing (not blocking):

- `AGENTS.md` also mentions `artcraft-mcp-server.exe`: **it does not exist**, only
  `artcraft-mcp.exe` is there. Follow the binary that is present.
- `ArtCraft-MCP-Setup-Guide.md` says "40+ tools / protocol 2025-03-26": the real package exposes 61.
- `setup_mcp.py` covers **Windsurf, Claude Desktop, Cursor only**.

### 3.5 Conformance defect of the generative MCP (blocking, verified)

`artcraft-mcp.exe` answers `initialize` with **snake_case** keys instead of camelCase:

```json
{"result":{"protocol_version":"2025-03-26","server_info":{"name":"artcraft-mcp",...}}}
```

The MCP specification requires `protocolVersion` and `serverInfo`. **Strict** clients therefore
refuse the server. Verified on Claude Code:

```
artcraft: ...\artcraft-mcp.exe - ✘ Failed to connect — INVALID_RESULT:
  Invalid result for initialize: expected string at path ["protocolVersion"],
                                 expected object at path ["serverInfo"]
```

Complete map of the non-conformant fields (verified by querying the server):

| Method | Field sent by the server | Field required by the MCP standard |
|---|---|---|
| `initialize` | `protocol_version` | `protocolVersion` |
| `initialize` | `server_info` | `serverInfo` |
| `initialize` | `capabilities.tools.list_changed` | `listChanged` |
| `tools/list` | `tools[].input_schema` | `inputSchema` |
| `tools/call` | `result.is_error` | `isError` |

**State: SOLVED** with [artcraft-mcp-proxy.py](../../tools/artcraft-mcp-proxy.py) — a stdio shim
that rewrites **only** these protocol fields (without touching the tool schemas, which correctly
use the JSON Schema keywords) and forwards everything to the real binary in binary UTF-8, with no
newline translation.

Verification: `artcraft -> ✔ Connected`, `initialize` with correct `protocolVersion`/`serverInfo`,
`tools/list` = 61 tools.

---

## 4. CRITICAL distinction: two different ecosystems

This is the point that clarifies the question "skill per app, or is MCP v1.1.0 enough".

```
┌──────────────────────────────────────────────────────────────────┐
│ A) ArtCraft GENERATIVE PLATFORM  (api.storyteller.ai)            │
│    • desktop app "ArtCraft" (storytold/artcraft)                 │
│    • ONE MCP:  artcraft-mcp v1.1.0  → 61 tools                    │
│      (THIRD-PARTY repo: theCosmicCrafter/artcraft-mcp)           │
│    • generates images/video/3D/audio via credit-based cloud      │
└──────────────────────────────────────────────────────────────────┘
                              ⚡ NOT the same product ⚡
┌──────────────────────────────────────────────────────────────────┐
│ B) CRAFTING APPS SUITE  (storytold/*, installed by the launcher) │
│    • 12 native desktop apps (PhotoCraft, FilmCraft, CADCraft…)   │
│    • EACH app has its OWN CLI and its OWN MCP:                   │
│        photocraft-cli mcp / filmcraft-cli mcp / cadcraft-cli mcp │
│    • it works locally; no ArtCraft cloud credits                 │
└──────────────────────────────────────────────────────────────────┘
```

**Practical consequences**

1. **`artcraft-mcp` v1.1.0 does NOT cover the Crafting Apps suite.** They are separate worlds:
   different GitHub owner, different backend (credit-based cloud vs local apps).
2. The `theCosmicCrafter/artcraft-mcp` package is, as far as is publicly documented, **a
   third-party/community project** for the generative platform: it is not a component of the
   suite nor of the `storytold/*` repos. It should be treated as a third-party dependency
   (supply chain).
3. If you install the Crafting Apps in the future, each one requires its **own** MCP registration.

---

## 5. Where each client reads MCP servers from (verified on the machine)

| Client | State | MCP config file | Skills |
|---|---|---|---|
| **Freebuff** | installed (`@codebufffreebuff-desktop`) | **`~\.agents\mcp.json`** (via the orchestrator's `McpConfigStore`); UI panel **Connectors** + **Refresh** button | `~\.agents\skills\<name>\SKILL.md`; cloud account skills in `%USERPROFILE%\.config\freebuff-desktop\account-skills\...` |
| **Claude Code** | v2.1.296 | `~\.claude.json` → `mcpServers` key (user scope); per project: `.mcp.json`; CLI: `claude mcp add -s user` | `~\.claude\skills\<name>\SKILL.md` |
| **Claude Desktop** | installed | `%APPDATA%\Claude\claude_desktop_config.json` → `mcpServers` (currently **empty**) | — |
| **dsh (DeepSeek Harness)** | v0.11.1 | `%APPDATA%\dsh-desktop\harness` — MCP servers in the `cordis.patch.yml` patches (home level + profile level, plugin id `dsh-mcp-client`) | `$DSH_HOME\skills` / skills managed by the profile |
| **Codex** | **NOT installed** | `~\.codex\config.toml` → `[mcp_servers.<name>]` (to be documented, not runnable now) | AGENTS.md |
| **Antigravity** | installed | `~\.gemini\config\mcp_config.json` → `mcpServers` (already contains `notebooklm`) | — |
| Other present | Trae, OpenCode, OpenClaw, OpenFang, Rowboat, Continue, Qoder, Vibe, `.codeium` | own files | — |

### 5.1 How Freebuff really loads MCP servers (verified in the app bundle)

Analysing `resources\orchestrator\orchestrator.js`, the process that really does the work:

```js
var agentsConfigPath = (home = homedir()) => join(home, ".agents", "mcp.json");
var CONFIG_DISPLAY_PATH = "~/.agents/mcp.json";
var stdioEntry = z.object({ type: z.literal("stdio").optional(), command, args, env, cwd })
```

- The **`McpConfigStore`** class reads **`~\.agents\mcp.json`** and validates every entry with
  `stdioEntry` / `remoteEntry`.
- The UI is called **Connectors** and has a **Refresh** button that reloads the configuration (the
  bundle's error message says: *"...then press Refresh in Connectors"*).
- There is a **sidecar** `~\.freebuff\mcp.json`, but it is **internal state** (`serverId`,
  `launchHash`, `manifestHash`), **not** user configuration: nothing should be duplicated there.
- Accepted transports: `stdio` and `http`. The `sse` type is refused; remote URLs must be `https`.
- **Environment variables**: Freebuff resolves only `HOME`, `PATH`, `SHELL`, `USER`, `LANG`,
  `TMPDIR`. For all the others it **does not read secrets from the shell**: the values must be
  written **literally** inside `env`.

**Practical consequence (verified field by field):** the 13 entries written are valid for this
schema — `type: "stdio"`, `command`, `args` (array of strings), `env` (string→string map).

> Note: the SDK bundle (`app.asar`) also contains a multi-directory loader (`<cwd>\.agents`,
> `<parent>\.agents`, `~\.agents`) used **only by its tests**, not by the desktop app: at runtime
> the `McpConfigStore` is what counts.

The orchestrator API answers on `http://127.0.0.1:57631` but `/api/mcp` and `/api/connectors`
return **401** without the app's token, so the programmatic check has to be done from the
Connectors panel.

Current state of the global MCP servers:
- Claude Code: `blender`, `drawio`, `railway`
- Antigravity: `notebooklm`
- Freebuff: no `~\.agents\mcp.json`
- dsh: no server configured

**Conclusion on "global":** there is no single MCP registration point shared by all the clients.
"Global" = **same binary + same entry replicated in the config files of each client**, so a
multi-client installation script is needed (the `setup_mcp.py` provided is not enough).

---

## 6. Short answers to the questions

**Q1 — How to implement it globally (Freebuff + Claude + Codex + dsh)?**
There is no single MCP registry. What is needed: (a) the binary in a **stable path** (not
`Downloads`), (b) credentials outside the package, (c) the **same `artcraft` entry** written into
every client's config file. dsh has a `dsh-config-manager` that manages/backs up MCP servers and
skills, but in the direction **other agents → DSH** (import/backup), so it is **not** a hub that
writes towards the other clients.

**Q2 — A skill per app of the suite, or is MCP v1.1.0 enough?**
They are two different things:
- the **generative** platform = **ONE** MCP (v1.1.0) → **ONE** `artcraft-mcp` skill is enough
  (already provided in the package);
- the **Crafting Apps** = 12 MCP servers (one per app) → a skill **per app** makes sense, but it is
  best to create them as you go, only for the apps you really use.

Recommendation: **one global skill** for the generative MCP now; per-app skills later, on demand.
MCP servers are self-describing (a schema per tool), so a skill is an optimisation, not a
requirement.

**Q3 — Is the suite installed with MSI + software/CLI? Or is the CLI that installs MCP 1.1.0 needed?**
- **Yes, the suite is installed**: launcher + **all 12** Crafting Apps, each with its own CLI in
  `C:\Program Files\<App>\<app>-cli.exe` exposing the `mcp` subcommand. Machine-wide installation
  (it requires elevated privileges; the user has installed them).
- **There is no** "CLI that installs MCP 1.1.0". `setup_mcp.py` **installs nothing**: it locates an
  already present binary and edits the config JSONs, and only for 3 clients. For
  Freebuff/Claude Code/dsh/Codex the dedicated script
  [install-craft-mcp.ps1](../../install/install-craft-mcp.ps1) was needed.

---

## 7. Gaps and blockers to solve before use

| # | Gap | Impact | Mitigation |
|---|---|---|---|
| G1 | **ArtCraft credentials missing** | The server starts but every tool fails in auth | Create `~\Artcraft\credentials\artcraft_session.txt` + `artcraft_avt.txt` (cookies from artcraft.ai) **or** use `ARTCRAFT_API_KEY` / `ARTCRAFT_MCP_PRIVATE_SESSION_TOKEN` |
| G2 | Binary inside **`Downloads`** | Volatile path, risk of cleanup | Copy to a stable per-user path |
| G3 | `setup_mcp.py` covers only 3 clients | Freebuff/Codex/dsh not configured | Dedicated multi-client installation script |
| G4 | **Codex not installed** | Not configurable now | Document the target config; apply it when installed |
| G5 | **Third-party** dependency (community repo) | Supply chain / trust | Version pin, hashing, per-user execution |
| G6 | `~\.agents\skills` is a **symlink** to `~\repos\craft-skills-flow\skills` | Writing there = writing into that repo | Decide: write in the repo or replace it with a real folder |
| G7 | **Billing** tools exposed (checkout/subscription) | An agent could start purchases | Restrict the tools / policy in `AGENTS.md` / skill |
| G8 | dsh exposes MCP servers via `cordis.patch.yml` | Manual editing is risky | Use the dsh UI/import |

---

## 8. Risks

1. **Confusion between the two ecosystems** → one might generate skills/MCP servers for the
   Crafting Apps believing that MCP v1.1.0 covers them.
2. **Secrets in config files** → session cookies are credentials: they must not end up in git nor
   in `SKILL.md` files.
3. **Cost** → credit-based generation: `artcraft_estimate_cost` must be imposed as a mandatory step
   before every generation (the skill provides for it).
4. **Skill duplication** → many near-identical skills increase the noise in the model's context.

---

## 9. Outcome of the installation (13 Oct 2026)

[install-craft-mcp.ps1](../../install/install-craft-mcp.ps1) was run — **13 MCP servers** registered
in **4 clients** (52 registrations).

| Client | File | Outcome |
|---|---|---|
| Freebuff | `~\.agents\mcp.json` | ✅ 13 servers (file created) |
| Claude Desktop | `%APPDATA%\Claude\claude_desktop_config.json` | ✅ 13 servers, `preferences`/`coworkUserFilesPath` preserved |
| Antigravity | `~\.gemini\config\mcp_config.json` | ✅ 13 servers, `notebooklm` preserved |
| Claude Code | `~\.claude.json` (via CLI) | ✅ 13 servers; `blender`/`drawio` preserved |

Real check with `claude mcp list`:

```
cadcraft, deckcraft, designcraft, effectcraft, filmcraft, gridcraft,
lightcraft, pdfcraft, photocraft, soundcraft, vectorcraft, wordcraft  ->  ✔ Connected
artcraft (via proxy)  ->  ✔ Connected
```

| Axis | Outcome |
|---|---|
| Idempotence (re-run) | ✅ `added=0, unchanged=13` on every client, no new backup |
| Up-front backups | ✅ `.bak.20261013-130016` for the 2 pre-existing configs |
| Stable binary | ✅ `%LOCALAPPDATA%\Programs\artcraft-mcp\artcraft-mcp.exe` |
| MCP of the 12 apps | ✅ working and verified |
| Generative MCP | ✅ conformant and connected through the proxy (§3.5) |
| dsh / Codex | ⚠️ manual (not automated) |

---

## 10. Bridged mode: driving the open apps instead of headless sessions

The 12 MCP entries use `*-cli.exe mcp`, that is a **headless** session: in-process engine, no
window. But every app can expose a **control channel** onto the real window, and the CLI can
connect to that channel:

```
<app>.exe --control PORT            # the app opens the control channel
<app>-cli.exe mcp --connect PORT    # the MCP server drives that window
```

Tried live on **all 12 apps**: the 11 with a port channel switch to bridged, each with a
successful call on the real window — LightCraft goes from 326 to **502** tools (176 bridged-only),
EffectCraft from 27 to 36, CADCraft from 11 to 14. Bridged mode returns the UI state
(`ui_inspect`), accepts state changes (in PhotoCraft `brushSize` 20 → 33, re-readable), creates
documents in the open app and captures real screenshots of the window. PdfCraft is the exception:
its app is driven through a control file, but its MCP server has no bridge flag (verified:
`unknown option --connect`).

Three apps verify a credential on the control channel:

| App | Credential | Handshake | Refusal without a credential |
|---|---|---|---|
| PhotoCraft | `control-token` 64-hex (`--control-token`, `--control-token-file`, env `PHOTOCRAFT_CONTROL_TOKEN`/`_FILE`) | `{"method":"auth","params":{"token":"…"}}` | `{"error":"authentication required"}` |
| WordCraft | `control key` 64-hex, file `control-key.local-<port>` written by the app (env `WORDCRAFT_CONTROL_KEY`) | `{"method":"auth","params":{"key":"…"}}` | `{"error":"unauthorized"}` |
| PdfCraft | `token` (32 chars) in the **dynamic port** + control file with `pid`/`port`/`token` | `{"method":"auth","params":{"token":"…"}}` | `{"error":{"code":-32001,"message":"authenticate first: auth {token}"}}` |

Details that matter: the gate is **in the app process**, not in the CLI (a wrong token does not get
through); PhotoCraft **generates and writes the token itself** if the file does not exist, so the
secret need not travel through chat or configuration.

For the other apps the channel is a loopback port with no credential (PdfCraft is the exception: it
uses a *file* with port+token and its MCP has no bridge flag). With the app closed and no one
listening, bridged **does not fall back**: GridCraft exits 1 with `cannot connect to the GridCraft
app at …`, PhotoCraft answers per call `… the request was not sent`. With a port occupied by
someone else that accepts the connection and then stays silent, however, the silent fallback did
exist (measured on DeckCraft: 25 headless tools and no error). Hence the **handshake** with which
the shim decides the mode: it asks the peer to speak the protocol (a non-existent method, whose
error is expected) and goes headless if it gets silence or foreign bytes, instead of declaring
bridged and falling back at the first tool. And since the channel can be asked **which** app it is
— it declares its own command catalogue, which the installed CLI knows: coverage 1.00 for the right
app, ≤ 0.15 for any other — the shim also recognises the wrong app on the port, which a CLI alone
does not challenge (`deckcraft-cli mcp --connect 7975` on GridCraft's port answers 25 tools and no
error). The proof that the app is behind the port is therefore the log line the app writes **plus**
the handshake answer — not the outcome of the connection. Hence the shim
[craft-bridge-mcp.py](../../tools/craft-bridge-mcp.py), which probes the port at startup and
chooses bridged or headless, making the same MCP entry valid in both cases.

**Applied on 13 Oct 2026** to `~\.agents\mcp.json`: 11 entries now go through the shim
([craft-bridge-config.py](../../tools/craft-bridge-config.py)), with the backup
`mcp.json.bak-20261013-135250`; `pdfcraft` and `artcraft` untouched. Verification with the command
exactly as configured ([craft-bridge-verify.py](../../tools/craft-bridge-verify.py)): **13/13
entries OK** — with the apps closed the 11 shim entries go headless, with GridCraft/PhotoCraft/
WordCraft open on the expected ports the same entries go **bridged**. Re-run of the installer: 0
changes.

**Update, same day — PdfCraft is no longer the exception.** The analysis above stays true in the
point that matters (`pdfcraft-cli mcp --connect` → `unknown option`: the vendor's MCP server has no
bridge flag), but "not bridgeable" does not mean "window out of reach": the CLI drives it well, so
its methods can be **translated** into MCP tools, one invocation per call
([craft-bridge-ui.py](../../tools/craft-bridge-ui.py), §5 of [craft-bridge.md](./craft-bridge.md)).
Effect on the configuration: the `pdfcraft` entry moved from the vendor's headless server to the
translator, so the entries rewritten by the installer are **12**, not 11, and `artcraft` remains the
only one untouched. Measured: `1440x920` window, 15 methods matching the ones the app declares, 192
commands, 107 widgets, screenshot of the window.

**Complete account, per-app matrix and measured proofs: [craft-bridge.md](./craft-bridge.md).**

---

## 11. Related documents

- [spec.md](./spec.md) — requirements and target architecture
- [plan.md](./plan.md) — execution phases, verifications, rollback
- [install-craft-mcp.ps1](../../install/install-craft-mcp.ps1) — idempotent multi-client installer
- [artcraft-mcp-proxy.py](../../tools/artcraft-mcp-proxy.py) — MCP conformance shim for the generative MCP
- [report-mcp-tools.py](../../tools/report-mcp-tools.py) — generates the real tool inventory of every server
- [mcp-tools-report.md](../../reports/mcp-tools-report.md) — **report of the available tools** (13/13 servers, 618 tools)
- [craft-bridge.md](./craft-bridge.md) — **bridged mode of the Crafting Apps** (matrix, control-token, proofs)
- [craft-bridge-mcp.py](../../tools/craft-bridge-mcp.py) — bridged/headless stdio shim
- [craft-bridge-config.py](../../tools/craft-bridge-config.py) — idempotent installer of the bridged entries (it installs the shim **and** the identity tool next to it, and realigns the files when the repo changes)
- [craft-bridge-recon.py](../../tools/craft-bridge-recon.py) · [craft-bridge-probe.py](../../tools/craft-bridge-probe.py) · [craft-bridge-pilot.py](../../tools/craft-bridge-pilot.py) — recon, MCP probe, app pilot
- [craft-bridge-sweep.py](../../tools/craft-bridge-sweep.py) — goes through the apps and measures every entry headless **and** bridged ([report](../../reports/craft-bridge-sweep.json))
- [craft-bridge-verify.py](../../tools/craft-bridge-verify.py) — verifies the MCP entries with the real command written in the config
- [craft-bridge-tests.py](../../tools/craft-bridge-tests.py) — **the injected faults, runnable**: it breaks something on purpose and demands the right verdict from doctor, ident and launcher ([report](../../reports/craft-bridge-tests.md) compared with the previous run)
- [craft-bridge-doctor.py](../../tools/craft-bridge-doctor.py) — **a single verdict on the whole assembly** (repo, installed shim, config entries, executables, credentials, build running on the ports), with the actions to take
- [craft-bridge-launch.py](../../tools/craft-bridge-launch.py) — starts one or more apps with the control channel already active on the expected ports
- [craft-bridge-ident.py](../../tools/craft-bridge-ident.py) — handshake and identity: who answers behind the control port (the app, from the command catalogue) **and which build** runs there (PID of the port, executable, version declared by the app; fingerprint in `~/.craft-bridge/builds.json` with `--record`)
