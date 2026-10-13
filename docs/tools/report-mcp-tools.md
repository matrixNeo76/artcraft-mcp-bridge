---
type: Tool
title: "report-mcp-tools - inventario dei tool dei server"
description: "Avvia ogni server MCP configurato, fa l'handshake e chiede tools/list: produce l'elenco reale dei tool disponibili, server per server."
resource: ../../tools/report-mcp-tools.py
tags: [strumento, inventario, tool]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/report-mcp-tools.py
  title: sorgente
- resource: ../../reports/mcp-tools-report.md
  title: il report prodotto
- resource: ../../docs/reference/analisi.md
  title: Analisi dell'ecosistema MCP
---

# Cosa fa

Legge `~/.agents/mcp.json` (la stessa config del pannello Connectors), avvia ogni
server stdio, fa l'handshake e chiede `tools/list`. Scrive un report Markdown. E' di
sola lettura: non modifica nessuna configurazione.

Ultimo esito: **13/13 server connessi, 764 tool** inventariati.

# Interfaccia

```
python tools/report-mcp-tools.py                       # -> reports/mcp-tools-report.md
python tools/report-mcp-tools.py --timeout 120 --out reports/miei-tool.md
```

# Perche' serve

La differenza fra "il server risponde" e "il server espone i tool giusti" si vede
solo qui: e' il modo in cui sono stati contati i tool bridged (per esempio
`lightcraft 502`, `effectcraft 36`, `cadcraft 14`) e confrontati con gli headless.

# Relazioni

- **inventario citato in** [Analisi dell'ecosistema](../reference/analisi.md)
- **complementare a** [craft-bridge-sweep](craft-bridge-sweep.md)
