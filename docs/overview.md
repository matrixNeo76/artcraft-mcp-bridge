---
type: Project Overview
title: "Craft Bridge - driving the Crafting Apps inside their own window"
description: "The bridge that completes the Crafting Apps as MCP servers: instead of falling back to an interface-less CLI, the running app is driven through its control channel."
resource: ../../README.md
tags: [bridge, mcp, overview]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../README.md
  title: project README
- resource: ../../docs/reference/craft-bridge.md
  title: complete technical manual
- resource: ../../docs/reference/analysis.md
  title: MCP ecosystem analysis
---

# What it is

The Crafting Apps (CADCraft, DeckCraft, DesignCraft, EffectCraft, FigCraft, FilmCraft,
GridCraft, LightCraft, PdfCraft, PhotoCraft, SoundCraft, VectorCraft, WordCraft) ship an MCP CLI
(`<app>-cli.exe mcp`) that works **without a user interface**. Many tools, though, only
make sense on the live window: drawing, capturing the canvas, moving a cursor. In
headless those tools disappear or fail.

The bridge adds a second mode: the app is launched with `--control <port>` and the stdio
MCP server (the shim) talks to it over that channel. The result is tools that act **on
the open window**.

# What is inside

| Piece | Role |
|---|---|
| stdio shim | the voice Freebuff sees as an MCP server: it chooses bridged or headless |
| Window translator | the PdfCraft entry, which has no bridge: one MCP method = one CLI invocation |
| Control channel | JSON-lines protocol on ports 7971-7981 and 9877 |
| Identity | who really answers on the port and which build is running |
| Diagnosis | `doctor`: one verdict on the assembly and the actions to repair it |
| Proofs | `verify`, `sweep`, `tests`: repeatable measurements, not claims |

# State

* 13 of 13 apps are driveable and verified live with a successful call (12 bridged
  through the shim, `figcraft` being the newest; PdfCraft by translation).
* PdfCraft has no bridge flag in its MCP server, but its window is driven all the same:
  [craft-bridge-ui](tools/craft-bridge-ui.md) exposes the 15 methods the app declares as
  as many tools, invoking the CLI once per call. Measured live: 15 methods matching the
  app's own, 192 commands, 107 widgets, a screenshot of the window.
* 14 MCP servers in `~/.agents/mcp.json`, verified one by one with the real command.
* 4 real defects found by measuring, fixed at the cause and covered by the fault suite.
* 12 of 13 apps compared with the release published by the launcher (feed of 13 October),
  read by [craft-bridge-feed](tools/craft-bridge-feed.md): the installed version is not
  just what the executable claims to be, it is compared with the vendor's. The feed does
  not name `figcraft` yet, so for it the comparison is *absent*, and the diagnosis says so
  instead of counting it among the aligned ones.

# Relations

- **described in detail by** [Technical manual](reference/craft-bridge.md) - the long text with every measurement
- **rests on** [Control channel](architecture/control-channel.md) - the protocol everything sits on
- **for the app without a bridge** [craft-bridge-ui](tools/craft-bridge-ui.md) - the PdfCraft window methods as MCP tools
- **is verified with** [Diagnosis and verification](operations/diagnosis.md) - the commands that say whether it is healthy
- **environment inventory in** [Ecosystem analysis](reference/analysis.md)
