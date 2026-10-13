---
type: Tool
title: "craft-bridge-mcp - lo shim stdio"
description: "Il server MCP che Freebuff avvia: sceglie bridged o headless con l'handshake e inoltra le richieste all'app viva."
resource: ../../tools/craft-bridge-mcp.py
tags: [strumento, shim, stdio]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-mcp.py
  title: sorgente
- resource: ../../docs/reference/craft-bridge.md
  title: Manuale tecnico completo
- resource: ../../docs/architecture/shim-modes.md
  title: la decisione bridged/headless
---

# Cosa fa

E' la voce registrata in `~/.agents/mcp.json` per ogni app. Parla MCP su stdio e
inoltra verso l'app quando il ponte c'e', altrimenti esegue la CLI headless.

# Interfaccia

```
python tools/craft-bridge-mcp.py --slug gridcraft --port 7975
python tools/craft-bridge-mcp.py --slug photocraft --port 7976 --token-file ~/.craft-bridge/photocraft.token
python tools/craft-bridge-mcp.py --dump-apps      # tabella delle app (JSON), usata da config e doctor
python tools/craft-bridge-mcp.py --slug gridcraft --require-bridge
```

| Opzione | Significato |
|---|---|
| `--slug` | app da servire (scelte dalla tabella interna) |
| `--port` | porta del canale di controllo |
| `--token-file` | file del control-token (solo PhotoCraft) |
| `--host` | host della sonda (default `127.0.0.1`) |
| `--require-bridge` | esce 3 se il ponte non c'e', invece di ripiegare |
| `--dump-apps` | stampa la tabella delle app e termina |

# Regola sui guasti

Un errore di rete **non solleva**: si restituisce quello che si e' letto e il
verdetto arriva lo stesso. Lo schema opposto (lasciar salire l'eccezione) avrebbe
potuto far perdere il server MCP all'avvio - vedi
[credenziale rifiutata](../findings/auth-refused-crash.md).

# Relazioni

- **decide secondo** [Modi dello shim](../architecture/shim-modes.md)
- **parla con** [Canale di controllo](../architecture/control-channel.md)
- **installato da** [craft-bridge-config](craft-bridge-config.md)
- **dichiarato da** [craft-bridge-verify](craft-bridge-verify.md)
