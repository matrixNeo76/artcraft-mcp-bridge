---
type: Tool
title: "craft-bridge-launch - avvia le app col canale attivo"
description: "Avvia una o piu' app staccate dalla shell, con --control sulla porta che la config si aspetta, aspetta i canali in parallelo e dice chi risponde (e con quale build)."
resource: ../../tools/craft-bridge-launch.py
tags: [strumento, avvio, launcher]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-launch.py
  title: sorgente
- resource: ../../docs/reference/craft-bridge.md
  title: Manuale tecnico completo
- resource: ../../tools/craft-bridge-tests.py
  title: La suite che prova gli strumenti
---

# Cosa fa

Salta le app il cui canale e' gia' su, avvia le altre **staccate dalla shell**
(le finestre restano aperte dopo il ritorno del comando) con `--control <porta>` e
`--control-token-file` dove serve, aspetta tutti i canali in parallelo, e chiede al
peer chi e' per ognuno.

# Interfaccia

```
python tools/craft-bridge-launch.py                     # tutte le app della config
python tools/craft-bridge-launch.py --apps gridcraft,photocraft
python tools/craft-bridge-launch.py --list              # tabella e stato, non avvia
python tools/craft-bridge-launch.py --dry-run           # mostra i comandi, non avvia
python tools/craft-bridge-launch.py --apps gridcraft --verify
```

| Opzione | Significato |
|---|---|
| `--apps` | slug separati da virgola (default: tutte le app in config) |
| `--port slug=porta` | porta diversa da quella attesa (ripetibile) |
| `--wait` | secondi di attesa per canale (default 45) |
| `--list` / `--dry-run` | non avvia niente |
| `--verify` | chiede anche allo shim in quale modo partirebbe |
| `--record-builds` | registra le impronte delle build incontrate |
| `--json` | report JSON |

# Esiti

| Uscita | Significato |
|---|---|
| 0 | ogni app richiesta ha il canale attivo **e la build configurata** |
| 1 | almeno una no: la riga `diagnosi` dice perche', con la coda del log |
| 2 | errore d'uso (slug sconosciuto, porta duplicata) |
| 3 | config o tabella delle app illeggibili |

# Relazioni

- **verifica con** [craft-bridge-ident](craft-bridge-ident.md)
- **config attesa da** [craft-bridge-config](craft-bridge-config.md)
- **provato su tutte le app in** [Manuale tecnico](../reference/craft-bridge.md)
- **nel runbook** [Installare e riparare](../operations/install-and-repair.md)
