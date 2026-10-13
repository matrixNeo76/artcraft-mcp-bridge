---
type: Finding
title: "App sbagliata e build diversa sulla porta"
description: "Aprire il canale non basta: la porta puo' essere di un'altra app o di un'altra versione. L'identita' si prova col catalogo dei comandi, la versione col processo che ascolta."
resource: ../../tools/craft-bridge-ident.py
tags: [difetto, identita, build]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-ident.py
  title: chi lo rileva
- resource: ../../docs/architecture/identity.md
  title: il meccanismo
---

# App sbagliata

La porta attesa puo' essere occupata da un'altra Crafting App. Misurato: l'app giusta
copre **1.00** del proprio catalogo di comandi, qualunque altra sta **sotto 0.15**.
Con la app sbagliata lo shim va headless e il launcher esce 1.

# Build diversa

Misurato con una seconda build vera della stessa app (0.5.0 contro 0.6.1) sulla porta
attesa di 0.6.1: la copertura del catalogo resta 1.00 - per l'identita' per app e'
"l'app giusta" - ma la build risulta `different`, con `ident` e launcher in uscita 1,
e lo shim che avvisa all'avvio ma procede bridged.

Provato anche il caso in cui l'eseguibile viene aggiornato **sotto** il processo:
vale la versione dichiarata dal processo, con la nota che il file su disco ora e'
un'altra cosa.

# Limite che resta

L'eseguibile dice la versione, non il contenuto: due build con la stessa versione -
e senza revisione nella riga di avvio - sono indistinguibili. Non e' una verifica di
integrita': nessun hash del binario.

# Copertura

Casi *build diversa* e *altra app sulla porta* nella
[suite dei guasti](../tools/craft-bridge-tests.md).

# Relazioni

- **meccanismo in** [Identita' e build](../architecture/identity.md)
- **usato da** [craft-bridge-doctor](../tools/craft-bridge-doctor.md) e [craft-bridge-launch](../tools/craft-bridge-launch.md)
