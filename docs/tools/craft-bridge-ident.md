---
type: Tool
title: "craft-bridge-ident - chi risponde e quale build"
description: "Risponde a due domande: chi ascolta su una porta (app riconosciuta dal catalogo dei comandi) e quale versione ci gira (PID, eseguibile, riga di avvio)."
resource: ../../tools/craft-bridge-ident.py
tags: [strumento, identita, build]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-ident.py
  title: sorgente
- resource: ../../docs/architecture/identity.md
  title: il meccanismo
- resource: ../../docs/reference/craft-bridge.md
  title: Manuale tecnico completo
---

# Cosa fa

Apre il canale, fa l'handshake, chiede il catalogo dei comandi e confronta; legge
poi il processo in ascolto per la build. E' il perito che `doctor`, `launch` e lo
shim interrogano quando c'e' un dubbio su chi sta parlando.

# Interfaccia

```
python tools/craft-bridge-ident.py --slug gridcraft        # una app (porta dedotta)
python tools/craft-bridge-ident.py --all                   # tutte le porte di ogni app
python tools/craft-bridge-ident.py --all --json
python tools/craft-bridge-ident.py --slug gridcraft --expect-version 0.6.1   # uscita 1 se diversa
python tools/craft-bridge-ident.py --slug gridcraft --record                  # registra l'impronta
```

| Opzione | Significato |
|---|---|
| `--slug` / `--port` | bersaglio singolo |
| `--all` | tutte le app della config |
| `--config` | config da usare (default `~/.agents/mcp.json`) |
| `--token-file`, `--token-field` | credenziale PhotoCraft (`token` o `key`) |
| `--timeout`, `--wait` | attesa della risposta / della comparsa del canale |
| `--no-identity`, `--no-build`, `--build-only` | selezionano la domanda |
| `--expect-version` | pretende una versione precisa |
| `--record` | scrive l'impronta in `~/.craft-bridge/builds.json` |
| `--json` | solo JSON |

# Esiti

| Uscita | Significato |
|---|---|
| 0 | peer riconosciuto, build coerente |
| 1 | porta chiusa / peer estraneo / app sbagliata / build diversa |
| 2 | errore d'uso |
| 3 | config o tabella illeggibili |

# Relazioni

- **meccanismo in** [Identita' e build](../architecture/identity.md)
- **usato da** [craft-bridge-doctor](craft-bridge-doctor.md), [craft-bridge-launch](craft-bridge-launch.md)
- **provato da** [craft-bridge-tests](craft-bridge-tests.md)
