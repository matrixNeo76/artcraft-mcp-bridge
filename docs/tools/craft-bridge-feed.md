---
type: Tool
title: "craft-bridge-feed - cosa il fornitore pubblica, contro cosa e' installato"
description: "Legge il feed del launcher di ArtCraft (release, repository di provenienza, sha256 dei pacchetti) e lo confronta con la build installata; con --bytes confronta l'eseguibile installato con quello dentro il pacchetto pubblicato, byte per byte."
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
python tools/craft-bridge-feed.py --bytes         # la CLI installata contro quella nel pacchetto
python tools/craft-bridge-feed.py --download soundcraft   # scarica quel pacchetto e confronta
python tools/craft-bridge-feed.py --json
python tools/craft-bridge-feed.py --feed-dir <cartella>   # feed di prova, o altro disco
```

# La domanda che la versione non puo' rispondere

`--bytes` confronta il `<slug>-cli.exe` installato con il file omonimo dentro il
pacchetto pubblicato. Sono tre domande in fila, e ognuna puo' fermare le altre:

| Passo | Se non torna |
|---|---|
| l'archivio sul disco e' quello pubblicato? (`sha256` del feed) | `FIX byte <slug>`: l'archivio non e' quello pubblicato, si cancella e si riscarica |
| la CLI installata c'e'? | `nota`: niente da confrontare, e il perche' e' scritto |
| il file dentro l'archivio e' identico a quello installato? | `FIX byte <slug>`: l'eseguibile installato non e' quello pubblicato — **questa e' la sola risposta che dice "questa e' la release" invece di "dichiara di esserla"** |

Gli archivi si cercano in `~/.craft-bridge/releases` e nella cartella dei download del
launcher. Se non ci sono, la riga dice **quale** file manca, **quanto** pesa e il
comando esatto per prenderlo: scaricarli tutti insieme sarebbero centinaia di MB, e
un'app alla volta e' una scelta, non una limitazione tecnica.

# Cosa si puo' aprire

| Tipo di pacchetto | Si legge? |
|---|---|
| `cli_zip` (archivio della sola CLI) | si', ed e' il primo che si sceglie quando c'e' — ma e' pubblicato **solo per macOS** |
| `portable_zip`, `tar_gz` | si': su Windows la CLI sta **dentro** il pacchetto portabile, quindi e' l'unico che risponde |
| `msi`, `dmg`, `deb`, `rpm`, `flatpak`, `app_image` | no: servono strumenti esterni, e lo strumento lo **dice** invece di fingere di aver confrontato |

# Cosa distingue, in concreto

| Riga | Significato |
|---|---|
| `0.8.2 = 0.8.2 (storytold/photocraft, installata da eseguibile di config)` | allineata, e la fonte della versione installata e' dichiarata |
| `0.6.2 < 0.6.3 (storytold/cadcraft, ...)` | l'app installata e' indietro rispetto alla pubblicata |
| `0.6.2 > 0.6.3` | il ponte e' avanti: build di prova, o feed vecchio |
| `installata non leggibile` | il feed risponde, l'eseguibile no: si avvia l'app una volta |
| `download <file>: byte diversi da quelli pubblicati` | il file scaricato non corrisponde al suo sha256 |
| `byte <slug>: <cli> e' <membro> dentro <archivio>, byte per byte` | l'eseguibile installato **e'** quello pubblicato |
| `byte <slug>: <a> != <b> dentro <archivio>` | l'eseguibile installato non e' quello pubblicato |
| `feed coerente` | `feed.json` e `releases.json` non concordano sulla stessa app |

# Esiti

| Uscita | Significato |
|---|---|
| 0 | nessuno scostamento |
| 1 | almeno uno scostamento: un'app indietro o avanti, un archivio scaricato che non corrisponde al suo sha256, oppure la CLI installata che non e' quella dentro il pacchetto |
| 2 | errore d'uso (per esempio `--download` su un'app fuori dalla tabella) |
| 3 | feed assente o illeggibile, o scaricamento fallito |

# Costo

~0,9 s senza archivi da leggere, quasi tutto nella lettura delle versioni degli
eseguibili (un solo giro di PowerShell). `doctor --no-live`, che include questo
confronto, resta sotto il secondo: la lettura delle versioni era gia' necessaria e non
viene ripetuta. Con `--bytes` si aggiunge la lettura di ogni archivio presente (uno
`sha256` da 14-120 MB) e l'apertura per il singolo membro: misurato su un archivio da
14,3 MB, pochi decimi di secondo. Con `--download` si aggiunge lo scaricamento: 14,3 MB
in 2 s sulla rete di questa macchina.

# Misura del 13 ottobre 2026

* 11 app su 11 allineate alla release pubblicata, con la versione letta dall'eseguibile
  (GridCraft dall'impronta registrata).
* **Byte per byte**: SoundCraft 0.6.1 — `soundcraft-cli.exe` installato e quello dentro
  `soundcraft-0.6.1-windows-x64-portable.zip` hanno lo stesso `sha256`
  (`915ee3abb121b7b9...`), e l'archivio scaricato corrisponde alla sua impronta
  pubblicata (`cd5f8d98257f7711...`). Le altre 10 app non hanno l'archivio sul disco:
  sono `nota` con il comando per prenderlo, non un confronto mancato.
* **Prova negativa**: un byte in piu' nell'archivio in cache → `FIX byte soundcraft:
  non e' quello pubblicato: a4228f8080b2... != cd5f8d98257f...`, uscita 1.
* 2 voci del feed fuori dal ponte: `pdfcraft` 0.7.1 (MCP senza ponte) e
  `artcraft-launcher` 0.3.2 (e' il launcher, non una app da guidare).
* Cartella dei download vuota: niente byte da confrontare, e questo **non** e' un
  successo, e' una lacuna dichiarata.

# Cosa non fa

* Non scarica niente da solo: solo con `--download <slug>`, un'app alla volta, dagli
  host del feed (GitHub) e in `https`. Lo `sha256` pubblicato si verifica prima di usare
  il file, che resta `.parte` finche' non torna.
* Non si applica a ogni contenitore: un MSI, un .dmg, un .deb, un .rpm o un AppImage
  non si aprono con la libreria standard, quindi per quelle app i byte restano non
  confrontati e la riga lo dichiara. Su Windows questo significa che la risposta arriva
  dal pacchetto **portabile**, che e' pubblicato sempre.
* Non decide se un aggiornamento va fatto adesso: dice che c'e'. Dentro
  [craft-bridge-doctor](craft-bridge-doctor.md) un'app indietro e' una `nota`, non un
  `FIX`, perche' il ponte funziona anche con la versione precedente.
* Gli altri percorsi del feed (macOS, Linux) sono quelli **attesi** dalle rispettive
  piattaforme, non misurati su questa macchina: altrove si usa `--feed-dir`.

# Relazioni

- **usa** [craft-bridge-ident](craft-bridge-ident.md) per la build installata
- **usato da** [craft-bridge-doctor](craft-bridge-doctor.md) - la riga `pubblicato` del verdetto
- **provato da** [craft-bridge-tests](craft-bridge-tests.md) - tre casi: confronto con feed finto, byte contro archivi finti, esiti 3 sugli errori del feed
- **scarica secondo** [Regole di sicurezza](../operations/safety-rules.md) - host, impronta, cache
- **stessa tabella delle app** [craft-bridge-mcp](craft-bridge-mcp.md) - nessuna seconda tabella
