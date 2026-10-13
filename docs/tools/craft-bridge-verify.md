---
type: Tool
title: "craft-bridge-verify - ogni entry col suo comando reale"
description: "Legge la config e interroga ogni entry eseguendo esattamente il comando scritto li' - shim compreso - e riferisce modo, tool disponibili ed esito di una chiamata."
resource: ../../tools/craft-bridge-verify.py
tags: [strumento, verifica, entry]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-verify.py
  title: sorgente
- resource: ../../docs/reference/craft-bridge.md
  title: Manuale tecnico completo
---

# Cosa fa

Non si fida della config: la **esegue**. Per ogni entry lancia il comando scritto
nel file, fa l'handshake MCP, chiede `tools/list` e - se richiesto - chiama un tool.

E' la prova che il percorso vero (Freebuff che avvia lo shim) funziona: 13/13 entry
verificate l'ultima volta, 11 con lo shim.

# Interfaccia

```
python tools/craft-bridge-verify.py                       # tutte le entry
python tools/craft-bridge-verify.py --expect bridged      # pretende il ponte
python tools/craft-bridge-verify.py --only gridcraft,photocraft
python tools/craft-bridge-verify.py --skip pdfcraft
python tools/craft-bridge-verify.py --tool ui_screenshot --tool-args '{"max_side":512}'
```

# Esiti

| Uscita | Significato |
|---|---|
| 0 | ogni entry verificata ha risposto |
| 1 | almeno una entry non risponde o non e' nel modo atteso |

# Relazioni

- **verifica** [craft-bridge-mcp](craft-bridge-mcp.md) attraverso la config reale
- **complementare a** [craft-bridge-doctor](craft-bridge-doctor.md) (assieme) e a [craft-bridge-sweep](craft-bridge-sweep.md) (per app)
- **nel runbook** [Diagnosi e verifica](../operations/diagnosis.md)
