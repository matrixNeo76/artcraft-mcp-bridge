---
type: Runbook
title: "Installare e riparare il ponte"
description: "Da zero a ponte funzionante, e come tornare indietro: installazione delle copie, entry dei connettori, avvio delle app, ripristino headless."
resource: ../../tools/craft-bridge-config.py
tags: [runbook, installazione, ripristino]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-config.py
  title: installer
- resource: ../../tools/craft-bridge-launch.py
  title: avvio
- resource: ../../docs/reference/craft-bridge.md
  title: Manuale tecnico completo
---

# Installare le copie e le entry

```
# 1. cosa cambierebbe (nessuna scrittura)
python tools/craft-bridge-config.py

# 2. applicare: copia shim e ident in %LOCALAPPDATA%\Programs\craft-bridge
#    e riscrive le entry in ~/.agents/mcp.json (backup automatico)
python tools/craft-bridge-config.py --apply

# 3. In Freebuff: Connectors -> Refresh
```

Le app chiuse restano usable in headless; quelle aperte col canale di controllo
diventano guidabili.

# Avviare le app col canale attivo

```
python tools/craft-bridge-launch.py                        # tutte le app in config
python tools/craft-bridge-launch.py --apps gridcraft --verify
```

PhotoCraft ha bisogno del file del token scritto dall'app
(`~/.craft-bridge/photocraft.token`): per le altre app basta il primo comando.

# Tornare indietro

```
python tools/craft-bridge-config.py --restore    # entry headless, come prima del ponte
```

# Controllare che sia tutto a posto

```
python tools/craft-bridge-doctor.py        # un verdetto sull'assieme
python tools/craft-bridge-verify.py        # ogni entry col suo comando reale
```

# Relazioni

- **installa** [craft-bridge-config](../tools/craft-bridge-config.md)
- **avvia** [craft-bridge-launch](../tools/craft-bridge-launch.md)
- **spiega i due posti** [Installato, sorgente e MCP globale](../architecture/installation-layout.md)
- **se qualcosa non torna** [Diagnosi e verifica](diagnosis.md)
