---
type: Tool
title: "craft-bridge-feed - cosa il fornitore pubblica, contro cosa e' installato"
description: "Legge il feed del launcher di ArtCraft (release, repository di provenienza, sha256 dei pacchetti) e lo confronta con la build installata: distingue un numero di versione dalla release che il fornitore distribuisce."
resource: ../../tools/craft-bridge-feed.py
tags: [strumento, release, confronto, launcher]
generated: { by: process:freebuff-buffy, at: 2026-10-13T18:10:00Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-feed.py
  title: sorgente
- resource: ../../tools/craft-bridge-ident.py
  title: da dove viene la build installata
- resource: ../../tools/craft-bridge-doctor.py
  title: chi lo interroga dentro il verdetto
---

# Il problema

La versione di un eseguibile dice cosa quell'eseguibile **dichiara** di essere. Non dice
se e' la release che il fornitore distribuisce: due build con lo stesso numero di
versione sono indistinguibili, ed e' un limite dichiarato del ponte. Il launcher di
ArtCraft pero' tiene sul disco l'elenco che usa per aggiornare le app, e in quell'elenco
c'e' la risposta.

# Da dove vengono le due risposte

| Lato | Dove sta | Cosa dice |
|---|---|---|
| **pubblicato** | `%LOCALAPPDATA%\ArtCraft Launcher\feed.json`, con `releases.json` accanto | repository di provenienza, ultima release (versione, tag, data), e per ogni artefatto sistema, architettura, tipo di pacchetto e **sha256** |
| **installato** | tabella dello shim, letta da [craft-bridge-ident](craft-bridge-ident.md) | versione dichiarata dall'eseguibile di config, oppure l'impronta registrata la prima volta che l'app e' stata vista girare |

Il confronto e' una funzione pura: tabella, feed e versioni installate entrano, righe
escono. Le prove la esercitano con un feed finto, quindi senza rete e senza app.

# Interfaccia

```
python tools/craft-bridge-feed.py                 # installata contro pubblicata
python tools/craft-bridge-feed.py --packages      # anche i pacchetti per questo sistema
python tools/craft-bridge-feed.py --downloads     # e i byte dei pacchetti gia' scaricati
python tools/craft-bridge-feed.py --json
python tools/craft-bridge-feed.py --feed-dir <cartella>   # feed di prova, o altro disco
```

# Cosa distingue, in concreto

| Riga | Significato |
|---|---|
| `0.8.2 = 0.8.2 (storytold/photocraft, installata da eseguibile di config)` | allineata, e la fonte della versione installata e' dichiarata |
| `0.6.2 < 0.6.3 (storytold/cadcraft, ...)` | l'app installata e' indietro rispetto alla pubblicata |
| `0.6.2 > 0.6.3` | il ponte e' avanti: build di prova, o feed vecchio |
| `installata non leggibile` | il feed risponde, l'eseguibile no: si avvia l'app una volta |
| `download <file>: byte diversi da quelli pubblicati` | l'unico caso accusato: il file scaricato non corrisponde al suo sha256 |
| `feed coerente` | `feed.json` e `releases.json` non concordano sulla stessa app |

# Esiti

| Uscita | Significato |
|---|---|
| 0 | nessuno scostamento |
| 1 | almeno uno scostamento: un'app indietro o avanti, oppure byte diversi |
| 2 | errore d'uso |
| 3 | feed assente o illeggibile |

# Costo

~0,9 s, quasi tutto nella lettura delle versioni degli eseguibili (un solo giro di
PowerShell). `doctor --no-live`, che ora include questo confronto, resta sotto il
secondo: la lettura delle versioni era gia' necessaria e non viene ripetuta.

# Misura del 13 ottobre 2026

* 11 app su 11 allineate alla release pubblicata, con la versione letta dall'eseguibile
  (GridCraft dall'impronta registrata).
* 2 voci del feed fuori dal ponte: `pdfcraft` 0.7.1 (MCP senza ponte) e
  `artcraft-launcher` 0.3.2 (e' il launcher, non una app da guidare).
* Cartella dei download vuota: niente byte da confrontare, e questo **non** e' un
  successo, e' una lacuna dichiarata.

# Cosa non fa

* Non scarica niente. Il feed pubblica lo sha256 dell'**artefatto** (installer MSI,
  pacchetto portabile, AppImage), non dell'eseguibile che ci sta dentro: i byte del
  `<app>-cli.exe` installato non si possono confrontare con quelli del pacchetto senza
  decomprimerlo. Per questo `--downloads` confronta solo i file che il launcher ha gia'
  scaricato.
* Non decide se un aggiornamento va fatto adesso: dice che c'e'. Dentro
  [craft-bridge-doctor](craft-bridge-doctor.md) un'app indietro e' una `nota`, non un
  `FIX`, perche' il ponte funziona anche con la versione precedente.
* Gli altri percorsi del feed (macOS, Linux) sono quelli **attesi** dalle rispettive
  piattaforme, non misurati su questa macchina: altrove si usa `--feed-dir`.

# Relazioni

- **usa** [craft-bridge-ident](craft-bridge-ident.md) per la build installata
- **usato da** [craft-bridge-doctor](craft-bridge-doctor.md) - la riga `pubblicato` del verdetto
- **provato da** [craft-bridge-tests](craft-bridge-tests.md) - un caso unitario con feed finto e uno statico sugli esiti 3
- **stessa tabella delle app** [craft-bridge-mcp](craft-bridge-mcp.md) - nessuna seconda tabella
