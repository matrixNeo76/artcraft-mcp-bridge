---
type: Mechanism
title: "Identita' dell'app e build che gira"
description: "Due domande distinte: chi risponde sulla porta (catalogo dei comandi, soglia 0,9) e quale versione gira davvero (PID, eseguibile, riga di avvio, builds.json)."
resource: ../../tools/craft-bridge-ident.py
tags: [identita, build, misura]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-ident.py
  title: implementazione
- resource: ../../tools/craft-bridge-doctor.md
  title: chi la usa per il verdetto
- resource: ../../tools/craft-bridge-tests.py
  title: La suite che prova gli strumenti
---

# Chi risponde

Aprire un canale non basta: la porta giusta puo' essere occupata da un'altra app.
L'identita' si stabilisce confrontando il **catalogo dei comandi** dichiarato dal
peer con quello dell'app attesa:

| Copertura | Significato |
|---|---|
| 1.00 | e' l'app giusta |
| <= 0.15 | e' un'altra app |

Sotto la soglia di 0,9 il peer non e' considerato questa app: lo shim va headless e
il launcher esce 1.

# Quale build

La versione non si chiede al catalogo: si legge dal **processo che ascolta** (PID
della porta), dall'eseguibile di quel processo e dalla riga di avvio che l'app scrive
da sola nel log. `--record` registra l'impronta in `~/.craft-bridge/builds.json`,
cosi' il confronto successivo e' contro un valore noto e non contro se stesso.

Misurato su due build vere della stessa app (0.5.0 contro 0.6.1): la copertura del
catalogo resta **1.00** - per l'identita' per app e' "l'app giusta" - e la build
risulta `different`, con `ident` e launcher in uscita 1.

# Limite dichiarato

L'eseguibile dice la **versione**, non il contenuto: due build con la stessa versione
e senza revisione nella riga di avvio sono indistinguibili. Il confronto non e' una
verifica di integrita' (nessun hash del binario).

# Relazioni

- **usata da** [Modi dello shim](shim-modes.md) - per non guidare l'app sbagliata
- **usata da** [craft-bridge-doctor](../tools/craft-bridge-doctor.md) - per il verdetto sulle porte
- **provata da** [craft-bridge-tests](../tools/craft-bridge-tests.md) - build 0.5.0 e app sbagliata iniettate
- **usata da** [craft-bridge-launch](../tools/craft-bridge-launch.md) - `--verify`, `--record-builds`
