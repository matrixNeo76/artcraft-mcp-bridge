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

Otto controlli in un comando, ognuno `ok` / `FIX` / `nota`: repo, copie installate,
entry di config, percorsi citati, eseguibili delle app, **quello che il fornitore
pubblica** contro quello installato, credenziali, e - sulle porte in ascolto - chi
risponde e quale build ci gira.

Degli otto, uno solo non e' un guasto possibile: la riga `pubblicato`. Un'app indietro
rispetto alla release del launcher resta una `nota` con l'azione "aggiorna dal launcher",
perche' il ponte funziona anche con la versione precedente; un launcher assente non
cambia il verdetto, perche' senza feed non c'e' un termine di paragone. Il dettaglio di
quel confronto sta in [craft-bridge-feed](craft-bridge-feed.md).

Poi mette in fondo **solo i problemi, numerati, con l'azione che li risolve**. Il
doctor non modifica niente da solo: consiglia, e l'azione la esegui tu (o la suite).

# Interfaccia

```
python tools/craft-bridge-doctor.py                # tutto, comprese le app aperte
python tools/craft-bridge-doctor.py --no-live      # salta le porte (~1 s)
python tools/craft-bridge-doctor.py --json         # checks / problems / actions
python tools/craft-bridge-doctor.py --install-dir <dir> --config <file>
python tools/craft-bridge-doctor.py --feed-dir <cartella>   # feed del launcher di prova
```

# Esiti

| Uscita | Significato |
|---|---|
| 0 | niente da sistemare |
| 1 | almeno un problema (le azioni dicono quali) |
| 2 | errore d'uso |
| 3 | config o tabella delle app illeggibili |

# Costo

~0,9 s con le app chiuse, confronto con il feed compreso (le versioni degli eseguibili
si leggono una volta sola e le usano due controlli); qualche secondo in piu' con app
aperte (una lettura del catalogo per porta occupata).

# Relazioni

- **usa** [craft-bridge-ident](craft-bridge-ident.md) per la domanda sulla build
- **usa** [craft-bridge-config](craft-bridge-config.md) per le entry attese (una sola fonte)
- **usa** [craft-bridge-feed](craft-bridge-feed.md) per la release pubblicata, contro la build installata
- **verificato da** [craft-bridge-tests](craft-bridge-tests.md) - ogni `FIX` provato iniettando il guasto
- **nel runbook** [Diagnosi e verifica](../operations/diagnosis.md)
