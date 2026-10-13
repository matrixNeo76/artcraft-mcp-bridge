---
type: Design Decision
title: "Bridged o headless: come lo shim sceglie"
description: "Lo shim non finge: fa l'handshake e decide. Peer assente, muto o estraneo portano in headless, dichiarandolo su stderr."
resource: ../../tools/craft-bridge-mcp.py
tags: [shim, bridged, headless, decisione]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-mcp.py
  title: lo shim stdio
- resource: ../../docs/reference/craft-bridge.md
  title: Manuale tecnico completo
- resource: ../../tools/craft-bridge-tests.py
  title: La suite che prova gli strumenti
---

# La scelta

A ogni avvio di un server MCP lo shim:

1. prova l'handshake sulla porta attesa per quell'app e, se c'e', col file del token;
2. se il peer parla il protocollo **ed e' l'app giusta** (catalogo dei comandi), va
   in **bridged**: inoltra le richieste all'app viva;
3. altrimenti va in **headless**, lanciando `<app>-cli.exe mcp`, e lo **scrive su
   stderr** invece di tacere.

`--require-bridge` cambia la regola: se il ponte non c'e', esce 3 invece di
ripiegare. Serve a chi vuole la certezza di guidare la finestra davvero.

# Perche' conta

E' il difetto piu' insidioso del progetto: con un socket che **accetta la
connessione e poi tace** al posto dell'app, lo shim dichiarava `modalita' bridged` e
la CLI rispondeva `25 tool, nessun errore`. Un headless travestito, indistinguibile
guardando la lista dei tool. Vedi [Ripiego silenzioso sul peer muto](../findings/silent-fallback.md).

# Costo

L'handshake aggiunge una richiesta all'avvio: millisecondi con l'app viva, fino a
~4,5 s con un peer muto prima di dichiarare headless (timeout raddoppiato).

# Relazioni

- **decide usando** [Canale di controllo](control-channel.md) - l'handshake sul protocollo
- **riconosce l'app con** [Identita' e build](identity.md) - la copertura del catalogo
- **verificato da** [craft-bridge-tests](../tools/craft-bridge-tests.md) - peer muto, app sbagliata, build diversa
- **dichiarato in** [craft-bridge-verify](../tools/craft-bridge-verify.md) - il modo reale di ogni entry
