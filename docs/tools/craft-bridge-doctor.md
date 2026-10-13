---
type: Tool
title: "craft-bridge-doctor - un verdetto sull'assieme"
description: "Controlla repo, copie installate, entry di config, eseguibili, credenziali e build in ascolto; in fondo elenca le azioni che risolvono i problemi trovati."
resource: ../../tools/craft-bridge-doctor.py
tags: [strumento, diagnosi, verdetto]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-doctor.py
  title: sorgente
- resource: ../../docs/reference/craft-bridge.md
  title: Manuale tecnico completo
- resource: ../../tools/craft-bridge-tests.py
  title: La suite che prova gli strumenti
---

# Cosa fa

Sette controlli in un comando, ognuno `ok` / `FIX` / `nota`: repo, copie installate,
entry di config, percorsi citati, eseguibili delle app, credenziali, e - sulle porte
in ascolto - chi risponde e quale build ci gira.

Poi mette in fondo **solo i problemi, numerati, con l'azione che li risolve**. Il
doctor non modifica niente da solo: consiglia, e l'azione la esegui tu (o la suite).

# Interfaccia

```
python tools/craft-bridge-doctor.py                # tutto, comprese le app aperte
python tools/craft-bridge-doctor.py --no-live      # salta le porte (~1 s)
python tools/craft-bridge-doctor.py --json         # checks / problems / actions
python tools/craft-bridge-doctor.py --install-dir <dir> --config <file>
```

# Esiti

| Uscita | Significato |
|---|---|
| 0 | niente da sistemare |
| 1 | almeno un problema (le azioni dicono quali) |
| 2 | errore d'uso |
| 3 | config o tabella delle app illeggibili |

# Costo

~1,3 s con le app chiuse; qualche secondo in piu' con app aperte (una lettura del
catalogo per porta occupata).

# Relazioni

- **usa** [craft-bridge-ident](craft-bridge-ident.md) per la domanda sulla build
- **usa** [craft-bridge-config](craft-bridge-config.md) per le entry attese (una sola fonte)
- **verificato da** [craft-bridge-tests](craft-bridge-tests.md) - ogni `FIX` provato iniettando il guasto
- **nel runbook** [Diagnosi e verifica](../operations/diagnosis.md)
