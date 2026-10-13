---
type: Reference
title: "Execution plan"
description: "Phases, milestones and verifications foreseen for the bridge."
resource: ../../docs/reference/plan.md
tags: [plan, milestones]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:23:21Z }
status: stable
---

# ArtCraft MCP — execution plan

**References:** [analysis.md](./analysis.md) · [spec.md](./spec.md)
**Date:** 13 October 2026 · **State:** ✅ **PHASES 1-5 EXECUTED** (confirmation received; Crafting Apps suite included)

> Phases 1-5 have been executed. The commands remain as a reference for re-running or rollback.

---

## Phase 0 — Prerequisites and decisions (blocking)

| # | Activity | Expected outcome |
|---|---|---|
| 0.1 | Obtain the **ArtCraft credentials** (login on artcraft.ai → `session` and `visitor` cookies) **or** an `ARTCRAFT_API_KEY` | credential source available |
| 0.2 | Confirm the **scope** (global-user vs Freebuff only) | decision |
| 0.3 | Decide whether to install the **Crafting Apps suite** too (scope B) | decision |
| 0.4 | Decide where to write the skill, given that `~\.agents\skills` is a symlink | decision |

**Gate:** without 0.1 the MCP server answers but every tool fails in auth.

---

## Phase 1 — Stabilise the binary

| # | Step |
|---|---|
| 1.1 | Create `%LOCALAPPDATA%\Programs\artcraft-mcp\` |
| 1.2 | Copy `bin\artcraft-mcp.exe` from the package into that path |
| 1.3 | (Optional) keep `SKILL.md` + `references\` in the same folder as the skill source |

Proposed command:

```powershell
$src = "C:\Users\auresystem\Downloads\artcraft-mcp-v1.1.0"
$dst = "$env:LOCALAPPDATA\Programs\artcraft-mcp"
New-Item -ItemType Directory -Force -Path $dst | Out-Null
Copy-Item "$src\bin\artcraft-mcp.exe" $dst -Force
Get-FileHash "$dst\artcraft-mcp.exe" -Algorithm SHA256   # hash to be recorded
```

**Verification (V1):** the file exists and the hash is noted.
**Rollback:** remove the folder created.

---

## Phase 2 — Register credentials (outside the package)

| # | Step |
|---|---|
| 2.1 | Create `~\Artcraft\credentials\` |
| 2.2 | Write `artcraft_session.txt` and `artcraft_avt.txt` with the cookie values **only** |
| 2.3 | Exclude the folder from git/unencrypted backups |

```powershell
$cred = "$env:USERPROFILE\Artcraft\credentials"
New-Item -ItemType Directory -Force -Path $cred | Out-Null
# the values must be entered manually by the user, NOT printed on screen
```

**Verification (V2):** `artcraft_get_credits` returns a real balance.
**Security note:** cookies are credentials → never in logs, never in `SKILL.md` files.

---

## Phase 3 — Register the MCP server in the clients

### 3.1 Freebuff (global)

Create `~\.agents\mcp.json`:

```json
{
  "mcpServers": {
    "artcraft": {
      "type": "stdio",
      "command": "C:\\Users\\auresystem\\AppData\\Local\\Programs\\artcraft-mcp\\artcraft-mcp.exe",
      "args": [],
      "env": {}
    }
  }
}
```

### 3.2 Claude Code (user scope)

```powershell
claude mcp add --scope user artcraft -- "C:\Users\auresystem\AppData\Local\Programs\artcraft-mcp\artcraft-mcp.exe"
# manual equivalent: merge into ~\.claude.json -> mcpServers
```

> Preserve the existing entries: `blender`, `drawio`, `railway`.

### 3.3 Claude Desktop

Merge `artcraft` into `%APPDATA%\Claude\claude_desktop_config.json` → `mcpServers` (empty today).

### 3.4 Antigravity (optional)

Merge `artcraft` into `~\.gemini\config\mcp_config.json`, preserving `notebooklm`.

### 3.5 dsh (DeepSeek Harness)

Add the server **from the dsh UI** (it writes `cordis.patch.yml`). Do not edit by hand.

### 3.6 Codex — documentation only

Not installed. Note the target config (`~\.codex\config.toml`, `[mcp_servers.artcraft]`) for when it
is installed.

**Verification (V3-V4):** every client lists `artcraft`; the pre-existing servers are still there;
for every modified file a `.bak.<timestamp>` exists.
**Rollback:** restore from the `.bak` files generated.

---

## Phase 4 — Install the global skill

| # | Step |
|---|---|
| 4.1 | Copy `skills\artcraft-mcp\` into `~\.agents\skills\artcraft-mcp\` (Freebuff) |
| 4.2 | Copy into `~\.claude\skills\artcraft-mcp\` (Claude Code) |
| 4.3 | Update the references if the binary is not in the skill folder |

**Verification (V5):** the clients list the `artcraft-mcp` skill.
**Careful:** `~\.agents\skills` is a **symlink** → check where you are writing before copying.

---

## Phase 5 — End-to-end verification and hardening

| # | Verification |
|---|---|
| E2E-1 | Direct handshake: `initialize` → `protocol_version: 2025-03-26` |
| E2E-2 | `tools/list` → **61** tools |
| E2E-3 | Authentication: `artcraft_get_credits` and `artcraft_get_session_info` |
| E2E-4 | Cost estimate: `artcraft_estimate_cost` answers |
| E2E-5 | Through each client: "check my ArtCraft credits" |
| E2E-6 | Idempotence: re-run of the installer → no difference in the files |
| E2E-7 | `git status`: no secrets, no unwanted files |
| E2E-8 | Policy: a note in `AGENTS.md`/the skill forbidding billing tools without explicit consent |

---

## Deliverables

| # | Deliverable | Phase |
|---|---|---|
| D1 | Binary in a stable path + SHA256 hash | 1 |
| D2 | Credentials configured (outside the repo) | 2 |
| D3 | `artcraft` registered in the clients (Freebuff, Claude Code, Claude Desktop, dsh) | 3 |
| D4 | Codex config documentation | 3.6 |
| D5 | Global `artcraft-mcp` skill | 4 |
| D6 | **Idempotent multi-client** installer script — ✅ delivered and executed | 3 |
| D7 | E2E verification report | 5 |
| D8 | [artcraft-mcp-proxy.py](../../tools/artcraft-mcp-proxy.py) — MCP conformance shim for the generative MCP | 5 |

---

## Estimate

| Phase | Effort | Notes |
|---|---|---|
| 0 | user decisions | blocking |
| 1–2 | 10 min | the binary is ready, self-contained |
| 3 | 20–30 min | + time if multi-client adapters are generated |
| 4 | 10 min | mind the symlink |
| 5 | 15 min | requires real credentials for E2E-3 |

---

## Residual risks and mitigations

| Risk | Mitigation |
|---|---|
| Credentials unavailable → blocked | explicit Phase 2; guided tests only afterwards |
| `setup_mcp.py` insufficient (3 clients) | dedicated script (D6), idempotent and with backups |
| dsh edited by hand → corrupted config | UI / import only |
| Skill symlink → writing into the wrong repo | preliminary check of the real target |
| Supply chain (third-party repo) | version pin + hash + per-user execution |
| Billing tools used by an agent | policy in the skill/`AGENTS.md` |

---

## Confirmed decisions (13 October 2026)

| # | Decision | State |
|---|---|---|
| C1 | **Scope:** global-user on every detected client | ✅ confirmed |
| C2 | **Clients:** Freebuff + Claude Code + Claude Desktop + Antigravity; dsh via UI; Codex docs only | ✅ confirmed |
| C3 | **Skill:** a single `artcraft-mcp`, global | ✅ confirmed |
| C4 | **Credentials:** the user does NOT have them yet | ⛔ blocks only the authentication E2E, not the configuration |
| C5 | **Multi-client installer:** to be generated | ✅ delivered: [install-craft-mcp.ps1](../../install/install-craft-mcp.ps1) |
| C6 | **Scope B (Crafting Apps suite):** all 12, already installed by the user in `C:\Program Files\` | ✅ implemented and verified |

### State of the installer script — [install-craft-mcp.ps1](../../install/install-craft-mcp.ps1)

| Verification | Outcome |
|---|---|
| PowerShell parsing (`Parser::ParseFile`) | ✅ SYNTAX OK |
| ASCII characters only (Windows PowerShell 5.1 compatible) | ✅ no non-ASCII byte |
| `-DryRun` end-to-end | ✅ 13 servers planned on every client |
| Automatic app discovery | ✅ 12/12 CLIs detected in `C:\Program Files` |
| Real execution | ✅ 13 servers x 4 clients = 52 registrations |
| Idempotence (re-run) | ✅ `added=0, unchanged=13` on every client |
| Backup | ✅ `.bak.20261013-130016` for the 2 pre-existing configs |
| Pre-existing servers preserved | ✅ `blender`, `drawio`, `notebooklm`, `preferences` intact |
| MCP of the 12 apps via `claude mcp list` | ✅ all `Connected` |
| ArtCraft generative MCP | ✅ `Connected` through the conformance proxy (see [analysis.md](./analysis.md) §3.5) |
| Proxy `artcraft-mcp-proxy.py` | ✅ tested: camelCase fields, 61 tools, exit 0 |

### Execution

```powershell
# dry-run (preview)
powershell -ExecutionPolicy Bypass -File .\artcraft-integration\install-craft-mcp.ps1 -DryRun

# real execution
powershell -ExecutionPolicy Bypass -File .\artcraft-integration\install-craft-mcp.ps1

# Crafting Apps only, without the generative one
powershell -ExecutionPolicy Bypass -File .\artcraft-integration\install-craft-mcp.ps1 -SkipGenerative

# with the conformance shim for the generative MCP (recommended)
powershell -ExecutionPolicy Bypass -File .\artcraft-integration\install-craft-mcp.ps1 -ProxyScript .\artcraft-integration\artcraft-mcp-proxy.py
```

The shim is copied into `%LOCALAPPDATA%\Programs\artcraft-mcp\` and the `artcraft` entry becomes
`python <proxy>`; the installer can recognise the difference in the command and re-registers the
entry (in Claude Code it runs `mcp remove` + `mcp add`).

### Remaining manual steps

1. **dsh**: add the 12 servers (+ the eventual `artcraft`) from the dsh UI, which writes
   `cordis.patch.yml`.
2. **Generative ArtCraft credentials**: `%USERPROFILE%\Artcraft\credentials\artcraft_session.txt` +
   `artcraft_avt.txt` (the protocol defect is already fixed by the proxy; they remain necessary for
   real generation).
3. **Codex** (not installed): `%USERPROFILE%\.codex\config.toml` → `[mcp_servers.<name>]`.
