---
type: Project Overview
title: "Craft Bridge - guidare le Crafting Apps nella loro finestra"
description: "Il ponte che rende complete le Crafting Apps come server MCP: invece di ripiegare su una CLI senza interfaccia, l'app viva viene guidata nel suo canale di controllo."
resource: ../../README.md
tags: [bridge, mcp, panoramica]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../README.md
  title: README del progetto
- resource: ../../docs/reference/craft-bridge.md
  title: Manuale tecnico completo
- resource: ../../docs/reference/analisi.md
  title: Analisi dell'ecosistema MCP
---

# Cos'e'

Le Crafting Apps (CADCraft, DeckCraft, DesignCraft, FilmCraft, GridCraft,
LightCraft, PhotoCraft, SoundCraft, VectorCraft, WordCraft, EffectCraft) espongono
una CLI MCP (`<app>-cli.exe mcp`) che funziona **senza interfaccia**. Molti tool
hanno pero' senso solo sulla finestra viva: disegnare, fotografare la tela,
muovere un cursore. In headless quei tool spariscono o falliscono.

Il ponte aggiunge un secondo modo: l'app viene avviata con `--control <porta>` e il
server MCP stdio (lo shim) parla con lei su quel canale. Il risultato sono tool che
agiscono **sulla finestra aperta**.

# Cosa c'e' dentro

| Pezzo | Ruolo |
|---|---|
| Shim stdio | la voce che Freebuff vede come server MCP: sceglie bridged o headless |
| Canale di controllo | protocollo JSON-lines sulle porte 7971-7980 e 9877 |
| Identita' | chi risponde davvero sulla porta e quale build ci gira |
| Diagnosi | `doctor`: un verdetto sull'assieme e le azioni per ripararlo |
| Prove | `verify`, `sweep`, `tests`: misure ripetibili, non dichiarazioni |

# Stato

* 11 app su 12 guidabili e verificate dal vivo con una chiamata riuscita.
* PdfCraft resta l'eccezione strutturale: app guidabile, MCP senza ponte.
* 13 server MCP in `~/.agents/mcp.json`, verificati uno per uno col comando reale.
* 4 difetti veri trovati misurando, corretti alla causa e coperti dalla suite di guasti.

# Relazioni

- **descritto in dettaglio da** [Manuale tecnico](reference/craft-bridge.md) - il testo lungo con tutte le misure
- **si appoggia a** [Canale di controllo](architecture/control-channel.md) - il protocollo su cui tutto poggia
- **si verifica con** [Diagnosi e verifica](operations/diagnosis.md) - i comandi che dicono se e' sano
- **inventario dell'ambiente in** [Analisi dell'ecosistema](reference/analisi.md)
