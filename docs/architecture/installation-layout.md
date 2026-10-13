---
type: Mechanism
title: "Installato, sorgente e MCP globale"
description: "L'MCP globale non punta a questo repo ma a copie installate in %LOCALAPPDATA%: per questo riorganizzare o spostare il progetto non rompe i connettori."
resource: ../../tools/craft-bridge-config.py
tags: [installazione, mcp-globale, deriva]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-config.py
  title: l'installer
- resource: ../../tools/craft-bridge-doctor.py
  title: chi rileva la deriva
- resource: ../../docs/reference/craft-bridge.md
  title: Manuale tecnico completo
---

# Due posti, due ruoli

| Dove | Cosa | Chi lo usa |
|---|---|---|
| questo repo | sorgente: strumenti, documentazione, report | chi sviluppa e verifica |
| `%LOCALAPPDATA%\Programs\craft-bridge` | copie installate dello shim e di `ident` | Freebuff, a ogni avvio di server MCP |
| `%LOCALAPPDATA%\Programs\artcraft-mcp` | MCP generativo ArtCraft e proxy di conformita' | Freebuff |
| `~/.agents/mcp.json` | le 13 entry dei connettori | Freebuff (pannello Connectors) |

Le entry della config puntano **alle copie installate**, mai al repo. E' la ragione
per cui riorganizzare o spostare questo progetto non tocca i connettori: l'MCP
globale continua a funzionare identico.

# Allineare, non duplicare

`craft-bridge-config.py --apply` installa le due copie e riscrive le entry (con
backup). Confronta i **file**, non solo le entry: se il sorgente cambia, riallinea le
copie - vedi [file installati non allineati](../findings/stale-installed-files.md).

`craft-bridge-doctor.py` e' il guardiano della deriva: dice se le copie installate
sono identiche al sorgente e quali entry non corrispondono.

# Conseguenza pratica

Chi modifica shim o `ident` nel repo deve poi eseguire
`python tools/craft-bridge-config.py --apply`, altrimenti la diagnosi segnala - a
ragione - che l'installato e' indietro.

# Relazioni

- **gestita da** [craft-bridge-config](../tools/craft-bridge-config.md)
- **controllata da** [craft-bridge-doctor](../tools/craft-bridge-doctor.md)
- **regola operativa in** [Regole di sicurezza](../operations/safety-rules.md)
- **installazione da zero in** [Installare e riparare](../operations/install-and-repair.md)
