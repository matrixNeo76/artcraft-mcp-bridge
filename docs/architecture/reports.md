---
type: Mechanism
title: "Report generati e confronto fra esecuzioni"
description: "Tutti gli artefatti generati stanno in reports/ ed e' il default degli strumenti; la suite confronta da sola l'esecuzione corrente con la precedente."
resource: ../../reports/craft-bridge-tests.json
tags: [report, baseline, confronto]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-tests.py
  title: chi produce il report con confronto
- resource: ../../reports/craft-bridge-sweep.json
  title: il report dello sweep
---

# Dove finiscono

| File | Prodotto da | Contenuto |
|---|---|---|
| `reports/craft-bridge-tests.json` | suite dei guasti | casi, esiti, durata, impronte degli strumenti, confronto |
| `reports/craft-bridge-tests.md` | suite dei guasti | gli stessi dati leggibili, con la sezione di confronto |
| `reports/craft-bridge-sweep.json` | sweep | per ogni app: tool headless, tool bridged, nomi solo-app |
| `reports/mcp-tools-report.md` | report-mcp-tools | inventario dei server e dei loro tool |
| `reports/photocraft-pilot-report.json` | pilot | i passi della guida dell'app e gli artefatti immagine |
| `reports/photocraft-live-*.png` | pilot | le immagini catturate dalla finestra viva |
| `reports/okf-graph.html` | `uvx okfgen visualize docs` | il bundle come grafo interattivo: nodi, relazioni, tipi |

Gli strumenti scrivono li' per **default**, non nella cartella da cui li invochi:
cosi' due esecuzioni fatte da posti diversi restano confrontabili.

# Il confronto

Il report della suite e' anche la sua baseline: l'esecuzione corrente legge il json
che sta per sovrascrivere e ne deduce le differenze - casi cambiati d'esito,
comparse, sparizioni, impronte degli strumenti - che finiscono nel markdown e nel
campo `changes` del json. La durata e' contesto, non una differenza. Per confrontare
due report qualsiasi: `--compare vecchio.json`.

# Relazioni

- **prodotto da** [craft-bridge-tests](../tools/craft-bridge-tests.md)
- **prodotto da** [craft-bridge-sweep](../tools/craft-bridge-sweep.md)
- **prodotto da** [report-mcp-tools](../tools/report-mcp-tools.md)
