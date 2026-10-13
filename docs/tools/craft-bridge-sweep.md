---
type: Tool
title: "craft-bridge-sweep - headless contro bridged"
description: "Avvia una app alla volta e misura gli stessi tool nei due modi, per provare che il ponte aggiunge capacita' sulla finestra invece di sostituire la CLI."
resource: ../../tools/craft-bridge-sweep.py
tags: [strumento, misura, confronto]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-sweep.py
  title: sorgente
- resource: ../../reports/craft-bridge-sweep.json
  title: il report prodotto
- resource: ../../docs/reference/craft-bridge.md
  title: Manuale tecnico completo
---

# Cosa fa

Per ogni app: esegue l'entry headless, raccoglie i tool; avvia l'app col canale di
controllo, rifa' la stessa raccolta in bridged, e mette a confronto i due elenchi -
inclusi i **nomi solo-app**, cioe' i tool che esistono solo guidando la finestra
viva. Poi chiude l'app.

# Interfaccia

```
python tools/craft-bridge-sweep.py                     # tutte le app in config
python tools/craft-bridge-sweep.py --apps gridcraft,photocraft --wait 60
python tools/craft-bridge-sweep.py --skip-tool         # solo gli elenchi, nessuna chiamata
python tools/craft-bridge-sweep.py --out reports/sweep.json
```

# Esito

Report in `reports/craft-bridge-sweep.json` (default): per ogni app i due elenchi di
tool, i nomi solo-app, il comando di avvio usato e l'esito della chiamata.

# Relazioni

- **misura l'effetto di** [Modi dello shim](../architecture/shim-modes.md)
- **complementare a** [craft-bridge-verify](craft-bridge-verify.md) (che guarda le entry, non le app)
- **misure raccontate in** [Manuale tecnico](../reference/craft-bridge.md)
