# ArtCraft MCP Bridge

Ponte fra le **Crafting Apps** (CADCraft, DeckCraft, DesignCraft, FilmCraft, GridCraft,
LightCraft, PhotoCraft, SoundCraft, VectorCraft, WordCraft, EffectCraft) e i client MCP:
invece di ripiegare sulla CLI senza interfaccia, l'app viva viene guidata nel suo
**canale di controllo**, così i tool agiscono sulla finestra aperta.

## Il problema

Ogni Crafting App espone un server MCP headless (`<app>-cli.exe mcp`). Molti tool però
hanno senso solo sull'app viva: disegnare, fotografare la tela, muovere un cursore. In
headless quei tool spariscono o falliscono, e il client non può sapere perché.

## Come funziona

1. l'app viene avviata con `--control <porta>` (e, per PhotoCraft, `--control-token-file`);
2. lo **shim** registrato nei connettori fa un **handshake** su quella porta;
3. se il peer parla il protocollo **ed è l'app giusta** (catalogo dei comandi, soglia
   0,9) va in **bridged** e inoltra le richieste all'app; altrimenti va in **headless**
   e lo dichiara su stderr. Con `--require-bridge` esce 3 invece di ripiegare.

Nessun ripiego silenzioso: il modo scelto è sempre dichiarato, e chi risponde sulla
porta è identificato (app **e** build in esecuzione).

## Struttura

```
tools/     gli strumenti (Python): shim, ident, doctor, config, launch, verify, sweep, tests, esplorativi
install/   install-craft-mcp.ps1 (registrazione multi-client dell'MCP generativo)
reports/   artefatti generati: report della suite, dello sweep, inventario tool, immagini
docs/      documentazione in formato OKF v0.2 (nodi e relazioni) - vedi docs/index.md
```

## Avvio rapido

```bash
# 1. installa le copie dello shim e riscrive le entry dei connettori (con backup)
python tools/craft-bridge-config.py --apply
# 2. in Freebuff: Connectors -> Refresh

# 3. avvia le app col canale di controllo (le finestre restano aperte)
python tools/craft-bridge-launch.py

# 4. verifica: un verdetto sull'assieme, poi ogni entry col suo comando reale
python tools/craft-bridge-doctor.py
python tools/craft-bridge-verify.py
```

Ripristino headless: `python tools/craft-bridge-config.py --restore`.

## Stato verificato (13 ottobre 2026)

| Prova | Esito |
|---|---|
| App guidabili in bridged, con una chiamata riuscita sulla finestra | 11 su 12 (PdfCraft: MCP senza ponte) |
| Entry della config eseguite col comando reale | 13/13 |
| Suite di guasti (10 casi, guasti iniettati) | 10/10, due giri di fila identici |
| Inventario tool dei server | 13/13 server, 764 tool |
| Diagnosi complessiva | `tutto in ordine` |

## Documentazione

La documentazione vive in [docs/index.md](docs/index.md): è un bundle **OKF v0.2**, un
nodo per concetto con relazioni esplicite fra i nodi (architettura, strumenti,
operazioni, difetti trovati). Il testo lungo e completo, con tutte le misure, è
[docs/reference/craft-bridge.md](docs/reference/craft-bridge.md).

```bash
uvx okfgen validate docs --strict                      # conforme: 28 concetti, 0 errori
uvx okfgen visualize docs -o reports/okf-graph.html    # grafo interattivo del bundle
```

Il grafo generato è in [reports/okf-graph.html](reports/okf-graph.html): 28 nodi, 109 relazioni.

## Limiti dichiarati

- **Windows**: la suite e il launcher usano `taskkill` e `DETACHED_PROCESS`.
- La cattura della finestra richiede la finestra visibile; un'app in background può
  restituire un timeout che sembra un guasto del ponte e non lo è.
- La versione dell'eseguibile non è il suo contenuto: due build con la stessa versione
  e senza revisione nella riga di avvio sono indistinguibili (nessun hash del binario).
- L'uso reale da parte di un agente dentro Freebuff, attraverso l'interfaccia, non è
  stato osservato: le prove parlano ai binari via protocollo.

## Licenza

Da decidere prima della pubblicazione (nessun file `LICENSE` è ancora presente).
