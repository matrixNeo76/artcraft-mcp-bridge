---
type: Tool
title: "craft-bridge-ui - the PdfCraft window as an MCP server"
description: "The translator that exposes the 15 methods of the PdfCraft window as MCP tools, invoking `pdfcraft-cli ui --control FILE <method>` once per call: the vendor's MCP has no bridge flag, its CLI does."
resource: ../../tools/craft-bridge-ui.py
tags: [tool, translator, pdfcraft, window, stdio]
generated: { by: process:freebuff-buffy, at: 2026-10-13T19:20:00Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-ui.py
  title: source
- resource: ../../docs/reference/craft-bridge.md
  title: complete technical manual (the control file, §3.3)
- resource: ../../tools/craft-bridge-tests.py
  title: the suite that exercises the translator without apps and live
---

# The problem it solves

PdfCraft is the only app with a channel different from the others: not `--control PORT`,
but `--control FILE` — the app opens the channel on a **random port** and writes its
details (`pid`, `port`, `token`) into a JSON file. Its CLI drives it perfectly
(`pdfcraft-cli ui --control FILE <method>`), but **its MCP server has no way to attach to
the window**: `pdfcraft-cli mcp --connect 127.0.0.1:PORT` answers
`mcp: unknown option --connect`. Driving the app is possible, serving its methods to an MCP
client is not: the entry stayed headless by construction — and the tools that act on the
window disappeared, exactly the problem the bridge exists to solve.

The control channel cannot be "attached" from outside, but it can be **translated**: one
MCP method = one CLI invocation. This tool is that translator.

# What it does

It speaks MCP on stdio towards the client and, for every `tools/call`, runs **one
process**:

```
client MCP  --stdio-->  craft-bridge-ui.py  --process-->  pdfcraft-cli ui --control FILE <method>
```

The 15 tools are the methods **the app itself declares** (`state`, `inspect`, `commands`,
`screenshot`, `click`, `focus`, `resize`, `move`, `drag`, `type`, `key`, `command`, `set`,
`open`, `quit`), one per method, with none invented:

| Tool | What it does | Read-only |
|---|---|---|
| `ui_state` | window state: theme, panels, documents, dialogs | yes |
| `ui_inspect` | widget tree (id, role, label, clickable); `query` filters by label | yes |
| `ui_commands` | catalogue of the window's commands: these are the ids `ui_command` accepts | yes |
| `ui_screenshot` | picture of the window, as PNG **image** content | yes |
| `ui_click` | click on a widget (by id or label) or on a point | no |
| `ui_focus`, `ui_resize`, `ui_move`, `ui_drag` | focus, size, position, drag | no |
| `ui_type`, `ui_key`, `ui_command`, `ui_set`, `ui_open` | text, key, command, setting, document open | no |
| `ui_quit` | closes the window and the app (`destructiveHint`) | no |

# Parameter typing

The CLI interprets every `key=value` argument as **JSON** when it can. The translator
therefore serialises every value with `json.dumps`: a string becomes `"true"` and stays the
string `true`, not the boolean. Without the quotes the parameter would reach the app as a
different type — and the method would do something else **instead of failing**. It is the
only truly delicate point of the translation and it is covered by a pure case, with no
processes: numbers, strings that look like booleans, strings with an `=` inside, lists,
`null`.

# Fault and fallback

* A fault of the app **is not a fault of the bridge**: it arrives as `isError` with the
  CLI message at the top and below it the diagnosis the CLI cannot produce (which CLI,
  which exit, and whether the control file's port still answers). Measured: `ui_click` with
  a non-existent label →
  `pdfcraft-cli: ui.click: no enabled clickable widget labelled "NonEsisteDavvero" (try ui.inspect with query)`.
* A tool that does not exist → `-32602`, with no process started.
* If the window disappears **mid-session** the call returns `isError` with the diagnosis
  (`la finestra non risponde piu' sulla porta del file di controllo: …`), not an empty
  answer that looks successful. Proved by the suite, which shuts down the fake PdfCraft
  under the open session.
* **Without a window** the translator delegates to the vendor's **headless** MCP server
  (`pdfcraft-cli mcp`) and the bytes pass both ways with no rewriting: the choice is made
  once and declared on stderr. With `--require-bridge` it exits 3 instead of falling back.
  It is the same rule as the shim, applied to an app that has no bridged mode — see
  [Shim modes](../architecture/shim-modes.md).

# Interface

```
python tools/craft-bridge-ui.py --slug pdfcraft              # the MCP server (stdio)
python tools/craft-bridge-ui.py --slug pdfcraft --list        # mode, channel, catalogue, then exits
python tools/craft-bridge-ui.py --slug pdfcraft --where       # where it looks, no probe
python tools/craft-bridge-ui.py --slug pdfcraft --call state  # one method, outcome verbatim
```

| Option | Meaning |
|---|---|
| `--slug` | app to serve (default `pdfcraft`) |
| `--control` | control file written by the app (default `~/.craft-bridge/<slug>-control.json`) |
| `--cli` | a CLI other than the one the system registers (a test build, a fake server) |
| `--headless-args` | how the headless server is requested from that CLI (default `mcp`) |
| `--timeout` | seconds per CLI invocation (default 30) |
| `--require-bridge` | exits 3 if the window does not answer, instead of falling back |
| `--list` / `--where` | they do not open the server: they report mode, channel and catalogue, and where it looks |

The CLI is resolved from the **system registry** (`App Paths`), as for the shim: `--where`
declares it (`pdfcraft-cli.exe` from `registro App Paths (macchina)`), so an app that moves
is followed without touching the configuration — see
[Where the app is](../architecture/app-locations.md).

# The catalogue is compared with the app

As for the shim, the table of methods **is not taken at its word**: the app lists its own
catalogue when it receives a method it does not know, and `--list` compares it. A method
removed or added by the app is visible instead of staying a promise in the document:
`catalogo: 15 metodi nostri, 15 dall'app: coincide`.

# Cost

One CLI process per call: `initialize` and `tools/list` cost ~0.2 s once, then `ui_state`
0.05 s and `ui_screenshot` 0.20 s (197 KB PNG, returned as base64). There is no shared
state between calls: it is the price of the translation, and it is what makes it possible
without touching the app.

# Measurement of 13 October 2026

* Window alive on port 48129 (pid 42336), `1440.0x920.0` points, CLI `pdfcraft-cli 0.7.1`
  from the registry, **15 methods as the app declares them**.
* From the MCP server: `serverInfo pdfcraft-ui`, 15 tools, `ui_state` (with the panels),
  `ui_commands` **192 commands**, `ui_inspect` **107 widgets**, `ui_screenshot` →
  [reports/pdfcraft-finestra.png](../../reports/pdfcraft-finestra.png) (197 KB).
* Fallback: with the control file missing the declared mode is `headless` and the frames of
  the vendor's server reach the client through the translator, intact.
* Window shut down mid-session: `isError` with the diagnosis, verified by the suite.
* Missing from the documentation until today: PdfCraft was counted among the apps **not**
  driveable over MCP. Now it is, by translation and not by attach.

# What it does not do

* It does not open a second window or an engine of its own: **it drives the one that is
  there**, and if there is none it falls back (or exits 3 with `--require-bridge`).
* It does not attach to the control channel: it does not speak PdfCraft's JSON-lines
  protocol and does not know the token — it lets the CLI use the control file. One
  implementation per question.
* It does not rewrite the frames of the headless server: those are already conformant.
  Rewriting protocol fields is needed for the other case, [artcraft-mcp-proxy](artcraft-mcp-proxy.md).
* **It does not merge the two catalogues.** With the window open the entry exposes the
  **15 window methods**; with the window closed it delegates to the vendor's headless
  server, which exposes **161** (`reports/mcp-tools-report.md`: the inventory of the 13
  servers went from 764 to 618 tools). It is the same choice as the shim — one mode or the
  other, declared — but here the switch is visible in the number of tools too, because the
  two catalogues really are different.

# Relations

- **it fixes the gap of** [craft-bridge-mcp](craft-bridge-mcp.md) - the apps with no bridge flag
- **it decides like** [Shim modes](../architecture/shim-modes.md) - bridged or headless, declared
- **it talks with** [Control channel](../architecture/control-channel.md) - through the CLI
- **the paths are resolved by** [Where the app is](../architecture/app-locations.md)
- **installed by** [craft-bridge-config](craft-bridge-config.md) and watched by [craft-bridge-doctor](craft-bridge-doctor.md)
- **started with the app by** [craft-bridge-launch](craft-bridge-launch.md) - the apps served by the translator
- **proved by** [craft-bridge-tests](craft-bridge-tests.md) - three cases without apps and one live
