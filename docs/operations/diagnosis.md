---
type: Runbook
title: "Diagnosi e verifica del ponte"
description: "I tre livelli di controllo - verdetto unico (doctor), entry reali (verify), guasti iniettati (tests) - e come leggere i report nel tempo."
resource: ../../tools/craft-bridge-doctor.py
tags: [runbook, diagnosi, verifica, report]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-doctor.py
  title: doctor
- resource: ../../tools/craft-bridge-verify.py
  title: verify
- resource: ../../tools/craft-bridge-tests.py
  title: La suite che prova gli strumenti
---

# I tre livelli

| Comando | Risponde a | Costo |
|---|---|---|
| `python tools/craft-bridge-doctor.py` | l'assieme e' sano? quali azioni servono? | ~1,3 s (app chiuse) |
| `python tools/craft-bridge-verify.py` | ogni entry della config risponde davvero? | decine di secondi |
| `python tools/craft-bridge-tests.py` | gli strumenti vedono i guasti quando ci sono? | ~44 s (10 s con `--static`) |
| `python tools/craft-bridge-feed.py` | l'app installata e' quella che il launcher pubblica? | ~0,9 s |

# Ordine consigliato

1. `doctor` - se dice `FIX`, esegui l'azione che indica (spesso
   `craft-bridge-config.py --apply`), poi rilancialo.
2. `verify` - se una entry non risponde, il problema e' nel percorso shim/app, non
   nella config.
3. `tests` - se hai toccato shim, ident o doctor, la suite dice subito se il
   comportamento e' cambiato.
4. `feed` - quando sospetti che la versione che gira non sia quella pubblicata:
   confronta le due cose e dice su quale app e su quale pacchetto si appoggia.

# Leggere i report nel tempo

La suite confronta ogni esecuzione con la precedente: esiti cambiati, casi comparsi o
spariti, impronte degli strumenti. Guarda la sezione *Confronto* di
`reports/craft-bridge-tests.md`. Vedi [Report e baseline](../architecture/reports.md).

# Sintomi tipici

| Sintomo | Prima cosa da guardare |
|---|---|
| il client MCP vede pochi tool | il modo scelto dallo shim: bridged o headless |
| `FIX shim installato` | il sorgente e' piu' nuovo dell'installato: `--apply` |
| `FIX porta N: gira una build diversa` | l'eseguibile installato non e' quello configurato |
| `nota pubblicato: il launcher pubblica altro` | c'e' un aggiornamento: il ponte funziona lo stesso, si aggiorna dal launcher |
| `nota pubblicato: nessun confronto` | il launcher non c'e' o il suo feed non si legge: non e' un guasto del ponte |
| `un'altra app` sulla porta | la porta e' occupata da una app diversa: chiudi o cambia porta |
| `l'app ha rifiutato la credenziale` | il token in config non e' quello dell'app |

# Relazioni

- **usa** [craft-bridge-doctor](../tools/craft-bridge-doctor.md), [craft-bridge-verify](../tools/craft-bridge-verify.md), [craft-bridge-tests](../tools/craft-bridge-tests.md), [craft-bridge-feed](../tools/craft-bridge-feed.md)
- **cosa non si tocca mai** [Regole di sicurezza](safety-rules.md)
- **contesto dei difetti** [Difetti trovati](../findings/silent-fallback.md)
