---
type: Runbook
title: "Connect any MCP client to the bridge"
description: "One recipe for every MCP client - Freebuff, Claude Desktop, Claude Code, Cursor, Windsurf, VS Code, Cline, LM Studio, Zed, Codex (ChatGPT desktop) and DeepSeek Harness (dsh) - and the two things that make it work: the shim installed, and one entry per app pointing at it."
resource: ../../tools/craft-bridge-connect.py
tags: [runbook, installation, clients, mcp]
generated: { by: process:freebuff-buffy, at: 2026-10-14T00:00:00Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-connect.py
  title: the tool that writes the entries
- resource: ../../docs/tools/craft-bridge-mcp.md
  title: what the entry runs
- resource: ../../docs/architecture/app-locations.md
  title: why the entry names the shim, not the app
---

# The idea in one paragraph

An MCP client does not "see" the bridge: it sees **servers**. A server is one entry in
the client's own config — a `command` and its `args`. The bridge is a **stdio server**
(`craft-bridge-mcp.py`, and `craft-bridge-ui.py` for PdfCraft) that the client starts;
the entry points at the **installed copy** of that shim, not at an app, and not at the
repo. So "connecting the bridge to a client" means only one thing: writing that entry,
in that client's format, once per app.

# What has to be true first

1. The shim is installed: `python tools/craft-bridge-config.py --apply` copies
   `craft-bridge-mcp.py`, `craft-bridge-ident.py` (and `craft-bridge-ui.py`) into
   `%LOCALAPPDATA%\Programs\craft-bridge` and writes the Freebuff/`.agents` entries.
2. The client can launch a **local stdio** server (all the ones below can).
3. For the window to be driven rather than the headless CLI, the app is **open** with
   its control channel — `python tools/craft-bridge-launch.py` — but the entry works
   headless too, and always says which mode it chose.

# One command for every client

```bash
python tools/craft-bridge-connect.py --list              # who is here, and where it reads
python tools/craft-bridge-connect.py                     # dry-run: what would change
python tools/craft-bridge-connect.py --apply             # writes, with a .bak-<stamp> backup
python tools/craft-bridge-connect.py --apply --client dsh --client codex
```

`--list` answers "do I even have this client?" without writing anything. `--apply` writes
only the clients that are installed and only the entries that differ. Every file touched
gets a backup beside it.

# Client by client

| Client | Where the entry goes | How it is written |
|---|---|---|
| **Freebuff / `.agents`** | `~/.agents/mcp.json` | JSON `mcpServers` (also by `craft-bridge-config.py --apply`) |
| **Claude Desktop** | `%APPDATA%\Claude\claude_desktop_config.json` | JSON `mcpServers` |
| **Claude Code** | `~/.claude.json` (user scope) | via `claude mcp add --scope user <slug> -- <cmd> <args>` |
| **Cursor** | `~/.cursor/mcp.json` | JSON `mcpServers` |
| **Windsurf / Cascade** | `~/.codeium/windsurf/mcp_config.json` | JSON `mcpServers` |
| **VS Code / Copilot** | `~/.copilot/mcp-config.json` | JSON `mcpServers` |
| **VS Code (workspace)** | `<project>/.vscode/mcp.json` | JSON `servers` (different key) |
| **Cline** | `~/.cline/data/settings/cline_mcp_settings.json` | JSON `mcpServers` |
| **LM Studio** | `~/.lmstudio/mcp.json` | JSON `mcpServers` |
| **Zed** | `%APPDATA%\Zed\settings.json` | JSON `context_servers`, nested `command` |
| **Codex / ChatGPT desktop** | `~/.codex/config.toml` | TOML `[mcp_servers.<slug>]` |
| **DeepSeek Harness (`dsh`)** | `~/.dsh/profiles/desktop/cordis.patch.yml` | YAML patch, one `insert` per app |

The exact path is `--list`'s answer for a given machine; the table is the default. If a
client moved, or you want the project-scoped VS Code file, pass
`--client-path <id>=<file>` — the tool never guesses a path by hand.

# The two clients that are not JSON

These are the two the documentation makes least obvious, so they are spelled out.

**Codex / ChatGPT desktop** reads TOML. Each server is a table:

```toml
[mcp_servers.cadcraft]
command = "C:\\Users\\me\\AppData\\Local\\Programs\\Python\\Python312\\python.exe"
args = ["C:\\Users\\me\\AppData\\Local\\Programs\\craft-bridge\\craft-bridge-mcp.py", "--slug", "cadcraft", "--port", "7971"]
```

**DeepSeek Harness (`dsh`)** does not read a `mcpServers` JSON file: it loads the Metal
MCP client through a **Cordis YAML patch**. Each server is an item of the top-level list;
the bridge writes one per app, with a stable id:

```yaml
- insert:
    - id: craft-bridge-cadcraft
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: cadcraft
        transport: stdio
        command: 'C:\Users\me\AppData\Local\Programs\Python\Python312\python.exe'
        args: ['C:\Users\me\AppData\Local\Programs\craft-bridge\craft-bridge-mcp.py', '--slug', 'cadcraft', '--port', '7971']
```

The Desktop app uses the reserved `desktop` profile (`~/.dsh/profiles/desktop/`); the CLI
uses `web`. The two patches are separate on purpose: an entry meant for one does not leak
into the other. `--client dsh` writes the Desktop profile; for the CLI, pass
`--client-path dsh=~/.dsh/profiles/web/cordis.patch.yml`.

# What an LLM should do, in four steps

1. `python tools/craft-bridge-config.py --apply` — install the shim and the `.agents`
   entry.
2. `python tools/craft-bridge-connect.py --list` — find which clients exist here.
3. `python tools/craft-bridge-connect.py --apply --client <id>` — register them.
4. `python tools/craft-bridge-doctor.py` — one verdict; then, inside the client, ask for
   its tool list: the Crafting Apps' tools must be there, and the shim's stderr says
   `bridged` or `headless` with the reason.

# What is not automated, and why

- **The client's own confirmation step.** Some clients ask the user to approve a new
  server, or reload the config: the tool writes the file, the client decides to load it.
- **The vendor CLI path in a `--restore`.** Removing the bridge's entries is this tool
  (`--restore`); putting back the *vendor* headless entries is
  `craft-bridge-config.py --restore`, which resolves the CLI from the system registry.
- **A client that reads a shape nobody documented.** Then `--client-path` plus a hand
  edit is the honest path, and it is written down here instead of guessed in code.

# Relations

- **mechanised by** [craft-bridge-connect](../tools/craft-bridge-connect.md)
- **it points at** [craft-bridge-mcp](../tools/craft-bridge-mcp.md) and [craft-bridge-ui](../tools/craft-bridge-ui.md)
- **it installs the copies with** [craft-bridge-config](../tools/craft-bridge-config.md)
- **the paths are resolved by** [Where the app is](../architecture/app-locations.md)
- **seen whole in** [craft-bridge-report](../tools/craft-bridge-report.md)
- **verified in** [Install and repair](install-and-repair.md)
