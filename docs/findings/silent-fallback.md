---
type: Finding
title: "Il bridged ripiegava in silenzio su un peer muto"
description: "Con un socket che accetta e tace, lo shim dichiarava bridged e la CLI rispondeva 25 tool senza errore: un headless travestito, indistinguibile dalla lista dei tool."
resource: ../../tools/craft-bridge-mcp.py
tags: [difetto, shim, handshake]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-mcp.py
  title: il codice corretto
- resource: ../../docs/architecture/shim-modes.md
  title: la decisione attuale
- resource: ../../docs/reference/craft-bridge.md
  title: Manuale tecnico completo
---

# Sintomo

Al posto dell'app, un socket che **accetta la connessione e poi tace**. Lo shim
dichiarava `modalita' bridged`, e la CLI dell'app rispondeva `25 tool, nessun
errore`. Nessuno se ne accorgeva guardando la lista dei tool.

# Causa

La scelta del modo non era verificata: bastava che la porta fosse aperta. Un peer
muto era trattato come peer vivo.

# Correzione

La decisione si prende con l'**handshake**: `peer=silent` o `peer=foreign` portano in
**headless**, e lo shim lo scrive su stderr. Il launcher esce 1, `ident` da' il
verdetto. `--require-bridge` trasforma il ripiego in uscita 3, per chi vuole la
certezza.

# Come e' coperto oggi

Caso *porta chiusa* e casi con peer muto/estraneo nella
[suite dei guasti](../tools/craft-bridge-tests.md).

# Relazioni

- **regola attuale in** [Modi dello shim](../architecture/shim-modes.md)
- **misurato con** [craft-bridge-ident](../tools/craft-bridge-ident.md)
- **raccontato in** [Manuale tecnico](../reference/craft-bridge.md)
