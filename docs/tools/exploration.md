---
type: Tool
title: "Strumenti esplorativi: recon, probe, pilot"
description: "I tre strumenti con cui il ponte e' stato scoperto e poi dimostrato: recon legge i binari, probe interroga un server MCP qualsiasi, pilot guida l'app e salva gli artefatti."
resource: ../../tools/craft-bridge-recon.py
tags: [strumento, esplorazione, recon, probe, pilot]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-recon.py
  title: recon
- resource: ../../tools/craft-bridge-probe.py
  title: probe
- resource: ../../tools/craft-bridge-pilot.py
  title: pilot
- resource: ../../docs/reference/craft-bridge.md
  title: Manuale tecnico completo
---

# craft-bridge-recon

Legge i binari delle app (read-only, nessuna app avviata) e cerca flag e indizi del
canale di controllo: e' cosi' che sono emersi `--control`, i nomi delle variabili e
le porte. `--matrix` mostra solo la presenza, `--all-context` piu' contesto.

```
python tools/craft-bridge-recon.py --app gridcraft --json
python tools/craft-bridge-recon.py --matrix --needle control
```

# craft-bridge-probe

Sonda MCP generica: lancia un server qualsiasi, fa `initialize`, `tools/list` e
facoltativamente una chiamata, e riferisce l'esito in JSON. Serve a distinguere "il
server non risponde" da "il server risponde ma il tool non esiste".

```
python tools/craft-bridge-probe.py --cmd "<app>-cli.exe" --args mcp --tool ui_screenshot --tool-args '{"max_side":512}'
```

# craft-bridge-pilot

Esegue una sequenza di chiamate sull'app aperta e **salva gli artefatti immagine**:
e' la prova che un agente puo' guidare la finestra, non solo elencarne i tool.

```
python tools/craft-bridge-pilot.py --cmd "<app-cli>" --args mcp \
    --step '{"tool":"ui_screenshot","args":{"max_side":512},"artifact":"shot.png"}' \
    --out reports/pilot.json
```

# Relazioni

- **recon ha prodotto** [Canale di controllo](../architecture/control-channel.md)
- **pilot dimostra** [Modi dello shim](../architecture/shim-modes.md) sulla finestra viva
- **artefatti in** [Report e baseline](../architecture/reports.md)
- **racconto completo in** [Manuale tecnico](../reference/craft-bridge.md)
