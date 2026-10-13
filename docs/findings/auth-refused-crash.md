---
type: Finding
title: "Credenziale rifiutata: crash e nessun verdetto"
description: "Con un token sbagliato l'app chiude la connessione e la scrittura successiva alza ConnectionAbortedError: ident moriva con un traceback e non stampava il verdetto."
resource: ../../tools/craft-bridge-ident.py
tags: [difetto, credenziale, rete]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-ident.py
  title: il codice corretto
- resource: ../../tools/craft-bridge-mcp.py
  title: lo shim con lo stesso schema
- resource: ../../tools/craft-bridge-tests.py
  title: La suite che prova gli strumenti
---

# Sintomo

Token diverso da quello dell'app: `craft-bridge-ident.py` usciva 1 con un traceback e
**stdout vuoto** - nessun verdetto, nessun JSON. Il caso e' emerso dalla suite dei
guasti, non da una prova a mano.

# Causa

L'app, rifiutata la credenziale, **chiude la connessione**. La `sendall` successiva
alzava `ConnectionAbortedError`, che non era gestita.

# Correzione

Un errore di rete non solleva piu': si torna quello che si e' letto e il verdetto si
da' lo stesso. Lo **stesso schema** c'era nello shim, dove sarebbe stato peggio -
un server MCP perso all'avvio - ed e' stato corretto anche li'.

# Conseguenza di processo

Dopo la correzione i file **installati** erano rimasti indietro rispetto al sorgente:
la suite lo ha segnalato da sola come `FAIL stato pulito`, citando la riga del doctor
che lo spiegava. Vedi [file installati non allineati](stale-installed-files.md).

# Relazioni

- **coperto da** [craft-bridge-tests](../tools/craft-bridge-tests.md) - caso *credenziale rifiutata*
- **riguarda** [Canale di controllo](../architecture/control-channel.md) - la chiusura su `auth` fallito
- **regola in** [Regole di sicurezza](../operations/safety-rules.md) - il valore del token non si stampa
