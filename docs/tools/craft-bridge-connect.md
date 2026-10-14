---
type: Tool
title: "craft-bridge-connect - the bridge in every MCP client, not only one"
description: "Registers the same bridge entries into every MCP client found on the machine (Freebuff, Claude Desktop, Claude Code, Cursor, Windsurf, VS Code, Cline, LM Studio, Zed, Codex, dsh), each in its own format, from a single source and with a dry-run by default."
resource: ../../tools/craft-bridge-connect.py
tags: [tool, installation, clients]
generated: { by: process:freebuff-buffy, at: 2026-10-14T00:00:00Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-connect.py
  title: source
- resource: ../../docs/operations/connect-a-client.md
  title: how to connect any MCP client
- resource: ../../tools/craft-bridge-config.py
  title: the single source of the entries
---

# What it does

`craft-bridge-config.py` writes **one** config (`~/.agents/mcp.json`), the one Freebuff
and the `.agents` clients read. The same shim, though, can be seen by every other MCP
client the user has: each with its **own** file and its **own** format. Rewriting them
by hand is where one gets it wrong — and does not know, because the client simply does
not show the server.

This tool takes the entries from a **single source** — `craft-bridge-config.py`'s
`planned_entries()`, the same function that writes the agents config, so the two cannot
diverge — and deposits them, client by client. It never duplicates the app table.

# Clients and formats

| Client | File (Windows, per user) | Shape |
|---|---|---|
| `agents` | `~/.agents/mcp.json` | JSON `mcpServers` |
| `claude-desktop` | `%APPDATA%\Claude\claude_desktop_config.json` | JSON `mcpServers` |
| `claude-code` | via `claude mcp add --scope user` | CLI, not a file |
| `cursor` | `~/.cursor/mcp.json` | JSON `mcpServers` |
| `windsurf` | `~/.codeium/windsurf/mcp_config.json` | JSON `mcpServers` |
| `antigravity` | `~/.gemini/config/mcp_config.json` | JSON `mcpServers` |
| `vscode` | `~/.copilot/mcp-config.json` | JSON `mcpServers` |
| `vscode-workspace` | `<project>/.vscode/mcp.json` | JSON `servers` |
| `cline` | `~/.cline/data/settings/cline_mcp_settings.json` | JSON `mcpServers` |
| `lmstudio` | `~/.lmstudio/mcp.json` | JSON `mcpServers` |
| `zed` | `%APPDATA%\Zed\settings.json` | JSON `context_servers`, nested `command` |
| `codex` | `~/.codex/config.toml` | TOML `[mcp_servers.<slug>]` |
| `dsh` | `~/.dsh/profiles/desktop/cordis.patch.yml` | YAML patch, one `insert` per app |

The paths are **declared by each client's documentation**, not invented; a client that
moves is corrected with `--client-path <id>=<file>` without touching the code. The
`.vscode/mcp.json` file is per project, so it has no default path: you pass it.

# Interface

```
python tools/craft-bridge-connect.py --list                 # who is here, and where it reads
python tools/craft-bridge-connect.py                        # dry-run: what would change
python tools/craft-bridge-connect.py --apply                # writes (with a .bak-<stamp> backup)
python tools/craft-bridge-connect.py --apply --client cursor --client zed
python tools/craft-bridge-connect.py --apply --client codex --client dsh
python tools/craft-bridge-connect.py --restore --client cursor
python tools/craft-bridge-connect.py --json
```

| Option | Meaning |
|---|---|
| `--client ID` | limit to one client (repeatable; default: all) |
| `--client-path ID=FILE` | a different file for a client (repeatable; what the tests use) |
| `--apps` | comma-separated slugs (default: every app the bridge serves) |
| `--restore` | removes the bridge's entries instead of writing them |
| `--apply` | writes; without it, dry-run only |
| `--list` / `--json` | show the clients / machine-readable output |

# Safety

- **It does not write by default**: only `--apply` writes, and it always makes a
  `.bak-<timestamp>` copy first. A client that is not installed is skipped, not created.
- **The real config of a client is not a guinea pig**: the tests exercise the tool on
  temporary files with `--client-path`, exactly as the suite does with `--config`.
- Non-JSON formats are handled with the minimum of care that stays idempotent: a TOML
  table (`[mcp_servers.<slug>]`) is replaced block by block; a `dsh` row is one
  `- insert:` item with the id `craft-bridge-<slug>`; what is not ours is never touched.

# Measured

On this machine (14 October): 13 clients known, **4 present** (`agents`,
`claude-desktop`, `windsurf`, `antigravity`). In dry-run `agents` was already
consistent (13 entries, the config `--apply` had written), while `claude-desktop` and
`antigravity` had **12 of 13** — written by the PowerShell installer as **headless**
entries — and `windsurf` had **0**. That is the point: three clients were reading the
vendor CLI, the bridge was in one. **Applied** (`--apply` on the three): all four are
now at **13/13**, with the foreign servers intact (`artcraft` in Claude Desktop and
Antigravity, `notebooklm` in Antigravity), a `.bak-<stamp>` beside each file that
existed, and the entries proven startable: `--config <client file>` run through
[craft-bridge-verify](craft-bridge-verify.md) answers for `cadcraft`, `figcraft` and
`pdfcraft` with the shim's own mode line. The suite proves the four shapes end to end
(`client MCP multipli`): written, idempotent on a second run, and `--restore` leaves
only the foreign server behind.

# Exit codes

| Exit | Meaning |
|---|---|
| 0 | nothing to do, or the write succeeded |
| 1 | a client refused a write (the detail says which) |
| 2 | usage error (unknown client or slug) |
| 3 | a client's file is unreadable: no change was made for that client |

# Relations

- **it takes the entries from** [craft-bridge-config](craft-bridge-config.md) - one source, not two
- **it registers** [craft-bridge-mcp](craft-bridge-mcp.md) and [craft-bridge-ui](craft-bridge-ui.md)
- **it is the machinery of** [Connect a client](../operations/connect-a-client.md) - the runbook for any client
- **proved by** [craft-bridge-tests](craft-bridge-tests.md) on temporary files
