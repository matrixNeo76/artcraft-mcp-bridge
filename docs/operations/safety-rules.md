---
type: Policy
title: "Regole di sicurezza del progetto"
description: "Le regole che valgono sempre: cosa non si modifica, quali file sono sacri, come si prova senza toccare la configurazione vera."
resource: ../../README.md
tags: [policy, sicurezza, regole]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../docs/reference/craft-bridge.md
  title: Manuale tecnico completo
- resource: ../../tools/craft-bridge-tests.py
  title: La suite che prova gli strumenti
---

# File che non si toccano a mano

* `~/.agents/mcp.json` (la config dei connettori): la scrive solo
  `craft-bridge-config.py --apply`, che fa il backup prima.
* `%LOCALAPPDATA%\Programs\craft-bridge\*`: sono copie; si aggiornano con
  `--apply`, non a mano.
* `~/.craft-bridge/photocraft.token`: lo scrive l'app. Il valore non si stampa mai,
  non finisce in chat e non entra nel repo.

# Regole delle prove

* La configurazione **vera** non viene mai usata come cavia: i test la riguardano su
  una copia temporanea con `--config`.
* L'unico file vero che la suite tocca e' la copia installata dello shim, dentro un
  `try/finally` che la rimette a posto; se serve, `--apply` la riallinea.
* Le app si avviano **solo su porte libere**; una porta occupata fa saltare il caso,
  non autorizza a uccidere processi altrui.
* Temporanei, log e token di prova si cancellano alla fine.

# Sorgente contro installato

Modificare shim o `ident` nel repo **non** cambia quello che Freebuff esegue: serve
`python tools/craft-bridge-config.py --apply`. La diagnosi segnala la differenza -
vedi [Installato, sorgente e MCP globale](../architecture/installation-layout.md).

# Relazioni

- **applicate da** [craft-bridge-tests](../tools/craft-bridge-tests.md)
- **verificate da** [craft-bridge-doctor](../tools/craft-bridge-doctor.md)
