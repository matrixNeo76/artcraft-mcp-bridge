---
type: Finding
title: "File installati non allineati al sorgente"
description: "La config copiava shim e ident solo se una entry cambiava: con le entry a posto, l'installato restava vecchio mentre il sorgente andava avanti."
resource: ../../tools/craft-bridge-config.py
tags: [difetto, installazione, deriva]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-config.py
  title: il codice corretto
- resource: ../../docs/architecture/installation-layout.md
  title: i due posti
- resource: ../../tools/craft-bridge-tests.py
  title: La suite che prova gli strumenti
---

# Sintomo

Con 11 entry gia' a posto, `craft-bridge-config.py` diceva «da aggiornare (0)» e la
copia installata dello shim restava quella vecchia: hash diversi, misurati.

# Causa

La copia dei file era legata **all'evento** "una entry e' cambiata", non allo stato
dei file. Due cose diverse che sembravano la stessa.

# Correzione

L'installer confronta i **byte** dei file e li riallinea quando serve, entry cambiate
o no; e installa accanto allo shim anche `craft-bridge-ident.py`, che serve alla
domanda sulla build. Idempotente: al secondo giro non riscrive nulla.

# Chi se ne accorge

`craft-bridge-doctor.py`: la riga `shim installato` confronta le impronte e dice
`FIX` con l'azione `--apply`. La [suite dei guasti](../tools/craft-bridge-tests.md)
copre il caso iniettando un byte in piu' nella copia installata e pretendendo che
l'azione indicata la ripari.

# Relazioni

- **regola in** [Installato, sorgente e MCP globale](../architecture/installation-layout.md)
- **rilevato da** [craft-bridge-doctor](../tools/craft-bridge-doctor.md)
- **collegato a** [credenziale rifiutata](auth-refused-crash.md) - e' li' che e' emerso la prima volta
