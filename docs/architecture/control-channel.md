---
type: Protocol
title: "Canale di controllo delle Crafting Apps"
description: "Il protocollo JSON-lines che le app aprono con --control: messaggi, credenziale, porte attese e insidie misurate."
resource: ../../tools/craft-bridge-ident.py
tags: [protocollo, porte, canale-di-controllo]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-ident.py
  title: implementazione dell'handshake
- resource: ../../tools/craft-bridge-mcp.py
  title: lo shim che lo usa
- resource: ../../docs/reference/craft-bridge.md
  title: Manuale tecnico completo
---

# Come si presenta

Una app avviata con `--control <porta>` apre un socket TCP su `127.0.0.1:porta` e
parla **JSON-lines**: una riga JSON per messaggio, con `id`, `method`, `params`, e
una risposta `result` oppure `error`.

Prima di fare qualunque domanda si fa un **handshake**: e' lui che dice se dietro la
porta c'e' una app che parla questo protocollo, un'estraneita' (per esempio un
server HTTP) o il silenzio. E' la ragione per cui lo shim non ripiega piu' in
silenzio su un peer muto.

# Credenziale

PhotoCraft pretende un token: l'app lo **scrive lei** in
`~/.craft-bridge/photocraft.token`, e la config lo passa con
`--control-token-file`. Il valore non viene mai stampato dagli strumenti: si legge
solo l'esito dell'`auth`.

# Porte attese

| App | Porta | App | Porta |
|---|---|---|---|
| cadcraft | 7971 | soundcraft | 7977 |
| deckcraft | 7972 | wordcraft | 7978 |
| designcraft | 7973 | vectorcraft | 7979 |
| filmcraft | 7974 | lightcraft | 7980 |
| gridcraft | 7975 | effectcraft | 9877 |
| photocraft | 7976 | | |

Le ultime tre sono i default documentati dalle rispettive CLI; le altre vengono
dalla tabella dello shim, che e' una **sola fonte** per config e diagnosi
(`--dump-apps`).

# Insidie misurate

* La fine di un messaggio va riconosciuta **parsando**, non cercando un a capo: le
  app lasciano un `\n` isolato dopo la risposta precedente, e fermarsi li' faceva
  leggere un byte vuoto al posto del catalogo (identita' "sconosciuta" a intermittenza).
* Il catalogo dei comandi e' un corpo grosso (100-120 KB misurati): con il timeout
  snello dell'handshake, sotto carico la risposta non arrivava in tempo. Per il
  catalogo la scadenza e' piu' larga.
* Una credenziale rifiutata fa **chiudere la connessione**: la scrittura successiva
  alza `ConnectionAbortedError` - vedi [difetto](../findings/auth-refused-crash.md).

# Relazioni

- **usato da** [Modi dello shim](shim-modes.md) - per decidere il modo e per parlare con l'app
- **interrogato da** [craft-bridge-ident](../tools/craft-bridge-ident.md) - identita' e build
- **provato da** [craft-bridge-tests](../tools/craft-bridge-tests.md) - peer muto, peer estraneo, credenziale rifiutata
