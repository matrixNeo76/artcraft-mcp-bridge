---
type: Tool
title: "artcraft-mcp-proxy - shim di conformita' per l'MCP generativo"
description: "Riespone i tool dell'MCP generativo ArtCraft con i nomi in camelCase attesi dai client, correggendo i nomi snake_case che alcuni client rifiutano."
resource: ../../tools/artcraft-mcp-proxy.py
tags: [strumento, conformita, artcraft]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/artcraft-mcp-proxy.py
  title: sorgente
- resource: ../../install/install-craft-mcp.ps1
  title: l'installer che lo registra
- resource: ../../docs/reference/analisi.md
  title: Analisi dell'ecosistema MCP
---

# Cosa fa

Si mette fra il client e l'MCP generativo ArtCraft: inoltra le richieste e riscrive i
nomi dei tool nella forma attesa dal client. E' lo shim di conformita' citato come
soluzione del difetto snake_case.

# Come si usa

```
python tools/artcraft-mcp-proxy.py          # server stdio da registrare nella config
```

L'entry viene creata da `install/install-craft-mcp.ps1` (parametro `ProxyScript`), che
la installa in `%LOCALAPPDATA%\Programs\artcraft-mcp` e la registra nei client
rilevati.

# Relazioni

- **registrato da** [install-craft-mcp.ps1](../../install/install-craft-mcp.ps1)
- **contesto in** [Analisi dell'ecosistema](../reference/analisi.md)
- **riguarda l'MCP generativo**, non il ponte delle app: vedi [Panoramica](../overview.md)
