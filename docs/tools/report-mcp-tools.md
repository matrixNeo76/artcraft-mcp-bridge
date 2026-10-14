---
type: Tool
title: "report-mcp-tools - inventory of the servers' tools"
description: "Starts every configured MCP server, performs the handshake and asks tools/list: it produces the real list of available tools, server by server."
resource: ../../tools/report-mcp-tools.py
tags: [tool, inventory, tools]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/report-mcp-tools.py
  title: source
- resource: ../../reports/mcp-tools-report.md
  title: the report it produces
- resource: ../../docs/reference/analysis.md
  title: MCP ecosystem analysis
---

# What it does

It reads `~/.agents/mcp.json` (the same config the Connectors panel uses), starts every
stdio server, performs the handshake and asks `tools/list`. It writes a Markdown report.
It is read-only: it modifies no configuration.

Last outcome: **14/14 servers connected, 636 tools** inventoried (for `pdfcraft` the 15
methods of the window: see [craft-bridge-ui](craft-bridge-ui.md); for `figcraft` 18, the
same list headless and bridged).

# Interface

```
python tools/report-mcp-tools.py                       # -> reports/mcp-tools-report.md
python tools/report-mcp-tools.py --timeout 120 --out reports/my-tools.md
```

# Why it is needed

The difference between "the server answers" and "the server exposes the right tools" is
only visible here: it is how the bridged tools were counted (for instance
`lightcraft 502`, `effectcraft 36`, `cadcraft 14`) and compared with the headless ones.

# Relations

- **the inventory is quoted in** [Ecosystem analysis](../reference/analysis.md)
- **complementary to** [craft-bridge-sweep](craft-bridge-sweep.md)
