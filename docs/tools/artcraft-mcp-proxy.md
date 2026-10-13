---
type: Tool
title: "artcraft-mcp-proxy - conformance shim for the generative MCP"
description: "Re-exposes the ArtCraft generative MCP tools under the camelCase names clients expect, fixing the snake_case names some clients refuse."
resource: ../../tools/artcraft-mcp-proxy.py
tags: [tool, conformance, artcraft]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/artcraft-mcp-proxy.py
  title: source
- resource: ../../install/install-craft-mcp.ps1
  title: the installer that registers it
- resource: ../../docs/reference/analysis.md
  title: MCP ecosystem analysis
---

# What it does

It sits between the client and the ArtCraft generative MCP: it forwards the requests and
rewrites the tool names into the shape the client expects. It is the conformance shim
quoted as the fix for the snake_case defect.

# How it is used

```
python tools/artcraft-mcp-proxy.py          # stdio server to register in the config
```

The entry is created by `install/install-craft-mcp.ps1` (parameter `ProxyScript`), which
installs it in `%LOCALAPPDATA%\Programs\artcraft-mcp` and registers it in the detected
clients.

# Relations

- **registered by** [install-craft-mcp.ps1](../../install/install-craft-mcp.ps1)
- **context in** [Ecosystem analysis](../reference/analysis.md)
- **it concerns the generative MCP**, not the app bridge: see [Overview](../overview.md)
