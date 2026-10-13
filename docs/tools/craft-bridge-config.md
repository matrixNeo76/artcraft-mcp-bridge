---
type: Tool
title: "craft-bridge-config - installer idempotente"
description: "Installa le copie dello shim e di ident, riscrive le entry bridged nella config dei connettori con backup, e riallinea i file quando il sorgente cambia."
resource: ../../tools/craft-bridge-config.py
tags: [strumento, installazione, config]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-config.py
  title: sorgente
- resource: ../../docs/reference/craft-bridge.md
  title: Manuale tecnico completo
- resource: ../../docs/architecture/installation-layout.md
  title: installato contro sorgente
---

# Cosa fa

* installa `craft-bridge-mcp.py` e `craft-bridge-ident.py` in
  `%LOCALAPPDATA%\Programs\craft-bridge` (default, sovrascrivibile con `--install-dir`);
* riscrive le entry dei connettori in `~/.agents/mcp.json` (default, `--config`),
  ognuna col comando giusto e il canale di controllo sulla porta attesa;
* e' idempotente: al secondo giro non riscrive nulla, e dice sempre cosa cambierebbe.

# Interfaccia

```
python tools/craft-bridge-config.py                        # mostra cosa cambierebbe
python tools/craft-bridge-config.py --apply                # scrive (con backup)
python tools/craft-bridge-config.py --apply --port photocraft=7981
python tools/craft-bridge-config.py --restore              # torna alle entry headless
python tools/craft-bridge-config.py --json
```

# Allineamento dei file

Il difetto corretto il 13 ottobre: prima copiava i due file **solo** se una entry
cambiava, quindi con la config gia' a posto l'installato restava indietro. Ora
confronta i byte e riallinea - vedi
[file installati non allineati](../findings/stale-installed-files.md).

# Relazioni

- **installa** [craft-bridge-mcp](craft-bridge-mcp.md) e [craft-bridge-ident](craft-bridge-ident.md)
- **scenario completo in** [Installato, sorgente e MCP globale](../architecture/installation-layout.md)
- **usato dalle azioni di** [craft-bridge-doctor](craft-bridge-doctor.md)
- **provato da** [craft-bridge-tests](craft-bridge-tests.md) su una copia della config, mai sulla vera
