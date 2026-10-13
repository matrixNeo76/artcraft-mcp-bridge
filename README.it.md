# ArtCraft MCP Bridge

[![checks](https://github.com/matrixNeo76/artcraft-mcp-bridge/actions/workflows/checks.yml/badge.svg)](https://github.com/matrixNeo76/artcraft-mcp-bridge/actions/workflows/checks.yml)

[English](README.md) · **Italiano** · [Español](README.es.md) · [中文](README.zh.md)

Ponte fra le **Crafting Apps** (CADCraft, DeckCraft, DesignCraft, FilmCraft, GridCraft, LightCraft,
PdfCraft, PhotoCraft, SoundCraft, VectorCraft, WordCraft, EffectCraft) e i client MCP: invece di
ripiegare sulla CLI senza interfaccia, l'app viva viene guidata nel suo **canale di controllo**,
così i tool agiscono sulla finestra aperta.

## Il problema

Ogni Crafting App espone un server MCP headless (`<app>-cli.exe mcp`). Molti tool però hanno senso
solo sull'app viva: disegnare, fotografare la tela, muovere un cursore. In headless quei tool
spariscono o falliscono, e il client non può sapere perché.

## Come funziona

1. l'app viene avviata con `--control <porta>` (e, per PhotoCraft, `--control-token-file`);
2. lo **shim** registrato nei connettori fa un **handshake** su quella porta;
3. se il peer parla il protocollo **ed è l'app giusta** (catalogo dei comandi, soglia 0,9) va in
   **bridged** e inoltra le richieste all'app; altrimenti va in **headless** e lo dichiara su
   stderr. Con `--require-bridge` esce 3 invece di ripiegare.

PdfCraft fa eccezione al punto 3: usa un *file* di controllo e il suo server MCP non ha un flag di
bridge (`mcp --connect` → `unknown option`). La sua finestra si guida lo stesso, per
**traduzione**: [craft-bridge-ui.py](tools/craft-bridge-ui.py) espone i 15 metodi che l'app dichiara
come altrettanti tool MCP, invocando `pdfcraft-cli ui --control FILE <metodo>` una volta per
chiamata.

Nessun ripiego silenzioso: il modo scelto è sempre dichiarato, e chi risponde sulla porta è
identificato (app **e** build in esecuzione). Lo stesso vale per la tabella: il flag di aggancio
che ogni app richiede non è una cosa che ricordiamo — lo chiediamo all'help della CLI, e quando
non lo conferma la diagnosi lo dice.

## Struttura

```
tools/     gli strumenti (Python): shim, traduttore finestra, ident, doctor, config, launch, verify, sweep, tests, esplorativi
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
| App guidabili con una chiamata riuscita sulla finestra | 12 su 12 (11 in bridged dallo shim, PdfCraft per traduzione) |
| Entry della config eseguite col comando reale | 13/13 |
| Suite di guasti (23 casi, guasti iniettati) | 23/23, due giri di fila identici |
| Installata contro la release pubblicata dal launcher | 12 su 12 allineate (feed del 13 ottobre) |
| Byte della CLI installata contro quelli pubblicati | 1 su 11 provata: SoundCraft identico (`sha256 915ee3abb121…`); per le altre l'archivio non è sul disco |
| Percorsi di app e CLI | 11 su 11 dal registro `App Paths` (la tabella conferma, non decide) |
| Metodi della finestra PdfCraft | 15 su 15 come li dichiara l'app; 192 comandi, 107 widget, screenshot della finestra |
| Flag di aggancio dichiarati dalla tabella | 12 su 12 confermati dall'help della CLI (11 agganci `--connect`/`--bridge`, PdfCraft senza flag e con `--control`) |
| Inventario tool dei server | 13/13 server, 618 tool (`pdfcraft`: i 15 metodi della finestra) |
| Diagnosi complessiva | `tutto in ordine` |

## Documentazione

La documentazione vive in [docs/index.md](docs/index.md): è un bundle **OKF v0.2**, un nodo per
concetto con relazioni esplicite fra i nodi (architettura, strumenti, operazioni, difetti trovati).
Il testo lungo e completo, con tutte le misure, è
[docs/reference/craft-bridge.md](docs/reference/craft-bridge.md) (in inglese).

```bash
uvx okfgen validate docs --strict                      # conforme: 32 concetti, 0 errori
uvx okfgen visualize docs -o reports/okf-graph.html    # grafo interattivo del bundle
```

Il grafo generato è in [reports/okf-graph.html](reports/okf-graph.html): 32 nodi, 162 relazioni.

## Cos'è installato, contro cosa è pubblicato

La versione di un eseguibile dice cosa dichiara di essere, non se è la release che il fornitore
distribuisce. Il launcher di ArtCraft tiene sul disco l'elenco che usa per aggiornare le app
(repository, ultima release, pacchetti con il loro `sha256`):
[craft-bridge-feed.py](tools/craft-bridge-feed.py) mette quell'elenco accanto alla build installata
e dice dove le due cose non coincidono. E con `--bytes` fa l'unica domanda che la versione non può
rispondere: confronta l'eseguibile installato con quello **dentro** il pacchetto pubblicato, letto
in memoria senza estrarre niente — `--download <slug>` prende il pacchetto (impronta del feed
verificata prima di usarlo, un'app alla volta, solo dagli host del feed). Dentro `doctor` una
versione indietro è una `nota`, non un `FIX`: il ponte funziona anche con la release precedente.
Dettagli in [docs/tools/craft-bridge-feed.md](docs/tools/craft-bridge-feed.md).

## Controlli automatici

A ogni push su `main` (e su ogni pull request) gira
[checks.yml](.github/workflows/checks.yml): sintassi degli strumenti, interfacce, coerenza della
tabella delle app con le porte documentate, determinismo dell'installer, conformità del bundle OKF
e la suite con `--ci` — che su un runner senza app salta i casi d'ambiente **motivandoli**, mentre
un guasto vero resta un FAIL. La suite intera gira su un runner self-hosted dove il ponte è
installato (variabile di repo `CRAFTBRIDGE_SELF_HOSTED=1`): è attiva sui push in `main` e sugli
avvii manuali, mai sulle pull request — il repository è pubblico, e il codice di uno sconosciuto
non gira sulla macchina che ha le app.
Dettagli in [docs/operations/ci.md](docs/operations/ci.md).

## Limiti dichiarati

- **Windows**: la suite e il launcher usano `taskkill` e `DETACHED_PROCESS`.
- La cattura della finestra richiede la finestra visibile; un'app in background può restituire un
  timeout che sembra un guasto del ponte e non lo è.
- La versione dell'eseguibile non è il suo contenuto: due build con la stessa versione e senza
  revisione nella riga di avvio sono indistinguibili (nessun hash del binario).
- L'uso reale da parte di un agente dentro Freebuff, attraverso l'interfaccia, non è stato
  osservato: le prove parlano ai binari via protocollo.

## Licenza

**MIT** — il testo completo è in [LICENSE](LICENSE): uso, modifica e ridistribuzione liberi, anche
dentro prodotti chiusi, purché l'avviso di copyright e la licenza restino insieme al software. Il
software è fornito così com'è, senza garanzie.
