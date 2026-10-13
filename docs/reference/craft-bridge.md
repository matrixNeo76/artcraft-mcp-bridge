---
type: Reference
title: "Craft Bridge - manuale tecnico"
description: "Il canale di controllo delle Crafting Apps: protocollo, shim bridged/headless, identita' e build, comandi e prove."
resource: ../../docs/reference/craft-bridge.md
tags: [bridge, protocollo, manuale]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:23:21Z }
status: stable
---

# Crafting Apps — modalità bridged degli MCP (sperimentazione)

**Data:** 13 ottobre 2026 · **Macchina:** Windows x64, utente `auresystem`
**Stato:** sperimentato dal vivo su 3 app su 12; protocollo e credenziali ricavati dai binari installati.

Riferimenti: [analisi.md](./analisi.md) · [spec.md](./spec.md) · [piano.md](./piano.md)

---

## 1. Che cos'è la modalità bridged

Ogni Crafting App ha due eseguibili nella stessa cartella (`C:\Program Files\<App>\`):

- `<app>.exe` — l'applicazione desktop;
- `<app>-cli.exe` — la CLI headless, che sa anche fare da **server MCP su stdio**.

Le 12 entry di `~\.agents\mcp.json` usano oggi `*-cli.exe mcp`, cioè una **sessione headless**: motore in-process, nessuna finestra, nessuna visibilità su quello che l'utente ha aperto.

Tutte le app (tranne PdfCraft) sanno fare di meglio: avviate con `--control PORT` espongono un **canale di controllo JSON-lines su 127.0.0.1** che pilota la finestra vera, e la CLI si collega a quel canale con `mcp --connect` / `mcp --bridge`. È la modalità **bridged**: l'agente vede e muove l'app aperta — stato UI, tool `ui_*`, screenshot della finestra, documenti aperti.

```
<app>.exe --control PORT            # l'app apre il canale di controllo
<app>-cli.exe mcp --connect PORT    # il server MCP guida quella finestra
```

---

## 2. Matrice per app

Tutto ricavato dai binari installati (`craft-bridge-recon.py`) e confermato dall'help delle CLI.

| App | Avvio dell'app | Flag bridge della CLI | Porta shim | Credenziale | Provato |
|---|---|---|---|---|---|
| `cadcraft` | `--control` (env `CADCRAFT_CONTROL_PORT`) | `mcp --connect HOST:PORT` | 7971 | — | ✅ bridged, 11→14 tool |
| `deckcraft` | `--control PORT` | `mcp --connect PORT` | 7972 | — | ✅ bridged, screenshot live |
| `designcraft` | `--control` (env `DESIGNCRAFT_CONTROL_PORT`) | `mcp --connect PORT` | 7973 | — | ✅ bridged, screenshot live |
| `effectcraft` | `--control <port>` | `mcp --bridge PORT` | 9877 | — | ✅ bridged, 27→36 tool |
| `filmcraft` | `--control <port>` (env `FILMCRAFT_CONTROL_PORT`) | `mcp --bridge 127.0.0.1:PORT` | 7974 | — | ✅ bridged, `render_preview` live |
| `gridcraft` | `--control 7979` | `mcp --connect PORT` | 7975 | — | ✅ bridged, `inspect_workbook` + screenshot |
| `lightcraft` | `--control PORT` (env `LIGHTCRAFT_CONTROL_PORT`) | `mcp --connect [ADDR]` | 7980 | — | ✅ bridged, 326→**502** tool |
| `pdfcraft` | `--control FILE` (**file**, non porta) | **assente**: `mcp [--root DIR]` | porta dinamica nel file | **token nel file** | ✅ app guidata dalla CLI · ❌ MCP non bridgeabile |
| `photocraft` | `--control <port>` (env `PHOTOCRAFT_CONTROL_PORT`) | `mcp --bridge 127.0.0.1:PORT` | 7976 | **control-token 64-hex** | ✅ bridged, `ui_inspect` live |
| `soundcraft` | `--control` (env `SOUNDCRAFT_CONTROL_PORT`) | `mcp --connect PORT` | 7977 | — | ✅ bridged, screenshot live |
| `vectorcraft` | `--control 7979` | `mcp --connect ADDR` | 7979 | — | ✅ bridged, `inspect_ui` live |
| `wordcraft` | `--control 7981` | `mcp --connect HOST:PORT` | 7978 | **control key 64-hex** | ✅ bridged, `ui_inspect` live |

Note dalla matrice:

- **Solo 10 app su 12** espongono `--control` come porta; PdfCraft usa un *file di controllo* e il suo server MCP **non ha** un flag di bridge.
- VectorCraft è l'unica che dichiara un **fallback automatico** all'headless quando l'app non c'è; le altre, se l'app manca, **falliscono** (verificato: GridCraft, PhotoCraft).
- `--automation-read-root` / `--automation-write-root` confinano i file letti/scritti dall'agente, ma **solo in headless**: con `--connect` l'app applica i propri root (WordCraft lo dice esplicitamente, VectorCraft pure). È una differenza di sicurezza da tenere presente.

---

## 3. Il protocollo di controllo

Il canale è JSON-lines su TCP loopback. Due app verificano una credenziale.

### 3.1 PhotoCraft — `control-token` (verificato)

Token di **64 caratteri esadecimali**. Fonti, in ordine di precedenza per l'app:

```
--control-token <64-hex>
--control-token-file <path>          # PHOTOCRAFT_CONTROL_TOKEN_FILE
PHOTOCRAFT_CONTROL_TOKEN             # oppure la variabile con il file
```

Comportamento verificato del ciclo di vita del token:

| Avvio dell'app | Esito |
|---|---|
| `--control 7982` (nessun token) | genera un token casuale e lo **stampa**: `photocraft: control token: 71ae898c…77e3` |
| `--control-token-file` su un file **inesistente** | genera il token e **scrive il file** (65 byte: 64 hex + newline) |
| `--control-token-file` su un file esistente | usa quello |

Il **client** (`photocraft-cli`) pretende una credenziale: senza, esce subito con

```
error: bridge mode needs --control-token, --control-token-file,
PHOTOCRAFT_CONTROL_TOKEN, or PHOTOCRAFT_CONTROL_TOKEN_FILE
```

Handshake, misurato su socket grezzo:

```json
→ {"id":1,"method":"auth","params":{"token":"<64-hex>"}}
← {"id":1,"ok":true,"result":{"authenticated":true}}
```

Senza `auth` (o con token sbagliato) ogni metodo è rifiutato:

```json
← {"error":"authentication required","id":null,"ok":false}
```

Quindi il gate è **nel processo dell'app**, non nella CLI: un token sbagliato di formato valido non passa.

### 3.2 WordCraft — `control key` (verificato)

Stessa idea, nome diverso. Avviata con `--control 7981` l'app scrive la chiave da sola:

```
wordcraft::control_server: control server listening on 127.0.0.1:7981,
  key in C:\Users\auresystem\AppData\Roaming\WordCraft\control-key.local-7981
```

Il file `control-key.local-<porta>` contiene 64 caratteri esadecimali. La CLI lo trova da sé; in alternativa si passa la chiave con `WORDCRAFT_CONTROL_KEY`. Handshake:

```json
→ {"id":1,"method":"auth","params":{"key":"<64-hex>"}}     ← campo `key`, non `token`
← {"id":1,"ok":true,"result":{}}
```

Senza autenticazione: `{"error":"unauthorized","id":1,"ok":false}`. Attenzione: se l'app non ha una cartella di impostazioni scrivibile, la chiave **non viene scritta** e le richieste vengono rifiutate (`control key file not written`).

### 3.3 PdfCraft — file di controllo (verificato)

PdfCraft non usa una porta sulla riga di comando: `pdfcraft --control FILE` apre il canale su una **porta casuale** e ne scrive i dettagli in un file JSON. Misurato:

```json
{ "pid": 6228, "port": 37902, "token": "<32 caratteri>" }
```

La CLI lo legge con `ui --control FILE <method>`: `state` restituisce lo stato UI della finestra, `screenshot --out x.png` ha prodotto un PNG `1440x920` (197 KB). Anche qui il token è verificato dall'app:

```json
→ senza token      ← {"error":{"code":-32001,"message":"authenticate first: auth {token}"}}
→ {"method":"auth","params":{"token":"…"}}   ← {"result":{"ok":true}}
```

**Ma il server MCP di PdfCraft non è bridgeabile**: `pdfcraft-cli mcp --connect 127.0.0.1:37902` risponde `mcp: unknown option --connect`. L'app si può guidare, l'entry MCP no: resta headless per costruzione.

Riepilogo: **tre app su dodici** verificano una credenziale sul canale (PhotoCraft `token`, WordCraft `key`, PdfCraft `token`).

### 3.4 L'handshake: chi c'e' dietro la porta (verificato)

Un `connect()` riuscito non dice che il peer parli il canale. Misurato: con un socket che **accetta e poi tace** al posto dell'app, lo shim dichiarava `bridged` e la CLI di DeckCraft rispondeva `25 tool, nessun errore` — una sessione headless indistinguibile da quella vera per lista di tool. Ora la scelta del modo si fa con una richiesta vera:

```json
→ {"id":1,"method":"__craft_bridge_ident__","params":{}}
← {"error":"unknown method `__craft_bridge_ident__`","id":1,"ok":false}
```

Il metodo è **inesistente di proposito**: la risposta attesa è l'errore, e quello prova il protocollo senza dipendere da un metodo che ogni app dovrebbe avere. Firma = oggetto JSON con l'`id` ripetuto e uno fra `ok`/`error`/`result`.

| Esito dell'handshake | Significato | Esito di una `connect()` |
|---|---|---|
| `craft` | il peer parla il canale di controllo | — |
| `silent` | la porta è in ascolto ma non risponde | **indistinguibile** (è il caso che ingannava) |
| `foreign` | ha risposto, ma non con la firma del canale (es. HTTP) | indistinguibile |
| `unreachable` | connessione rifiutata / host irraggiungibile | distinguibile |

Dove c'è una credenziale l'handshake fa un secondo passo: `auth` con il token della config. `autenticato` significa che il peer non è solo «un canale Craft», è **il nostro**. Non serve nessuna conoscenza per-app: le app della famiglia rispondono tutte alla stessa richiesta, e l'errore non autenticato cambia solo di testo (`authentication required` per PhotoCraft, `unauthorized` per WordCraft).

**Un errore mio, trovato misurando.** Al primo giro il token *giusto* risultava rifiutato: mandavo l'`auth` come seconda richiesta, sulla connessione già rifiutata per mancanza di credenziale. Su quel socket l'app non ascolta più. Ora l'`auth` va **per prima, su una connessione sua**, e il token corretto è riconosciuto. Il caso negativo resta coperto: token sbagliato → `auth rifiutata`.

Lo stesso controllo vive in due posti, con lo stesso esito: [craft-bridge-ident.py](../../tools/craft-bridge-ident.py) come strumento di diagnosi, e dentro [craft-bridge-mcp.py](../../tools/craft-bridge-mcp.py) come criterio per scegliere bridged/headless (nessuna dipendenza: lo shim si installa come file singolo).

### 3.5 Chi e', e quale build: il catalogo e l'eseguibile in ascolto (verificato)

L'handshake dice che il peer parla il protocollo, non **quale** app sia. Il canale non
lo dichiara: su 40 nomi candidati (`app.version`, `version`, `about`, `app.info`,
`hello`, `identify`, `whoami`, …) nessuno esiste. L'unica cosa che dice di sé e' il
proprio **catalogo di comandi**:

```json
→ {"id":2,"method":"engine.commands","params":{}}
← {"id":2,"ok":true,"result":[{"id":"file.new","label":"New Workbook",…}, …]}
```

Il catalogo e' specifico dell'app, e il CLI installato conosce il proprio
(`<cli> commands`). Il confronto e' quindi a due lati e senza tabelle da mantenere:

| Peer sulla porta | Copertura del catalogo locale |
|---|---|
| l'app giusta | **1.00**: ogni id che il CLI dichiara esiste anche nel canale (0 id locali assenti, tranne uno in `vectorcraft`); il canale ne ha di piu' — 33–273 in piu' |
| qualunque altra app | **≤ 0.15** (max misurato 0.15, tipico 0.01–0.09) |

Misurato su tutte e 11: `app` identificata con copertura 1.00 e la sua versione
(`cadcraft-cli 0.6.2`, `gridcraft-cli 0.6.1`, `lightcraft-cli 0.7.1`,
`vectorcraft-cli 0.10.0`, `SoundCraft CLI 0.6.1`, …). Due app non stampano JSON nel
proprio catalogo (`soundcraft` stampa una tabella, `photocraft`/`wordcraft` chiedono
la credenziale sul canale): la tabella si legge a parte e l'`auth` va fatta per prima.

**Il catalogo identifica l'APP, non la build.** Due build della stessa app coprono lo
stesso catalogo (misurato: copertura 1.00 anche con una build diversa sulla porta),
quindi l'app risulta giusta mentre l'eseguibile in ascolto non e' quello configurato:
il ponte guiderebbe una finestra che non e' quella che si crede. La build si legge
altrove, e il canale non ne dichiara nessuna:

| Fonte | Cosa dice |
|---|---|
| PID in ascolto → eseguibile del processo | la versione del **file** da cui il processo e' partito (risorsa di versione del PE, via `Get-Process`/`Get-Item`) |
| log dell'app, riga di avvio | cosa il **processo** dichiara di essere: `gridcraft: GridCraft 0.6.1…`, e dove c'e' anche la revisione — `cadcraft 0.6.2 (00c7613f…)` |
| eseguibile accanto alla CLI di config | la build che l'entry **avvierebbe** |
| `~/.craft-bridge/builds.json` | la build **verificata** l'ultima volta (`--record`) |
| `<cli> version` | la versione della **CLI**, che non e' quella dell'app in ascolto |

La riga di avvio vale per una porta solo perche' la segue, nello stesso log, la riga
`control … listening on …:<porta>`: e' quello che lega la dichiarazione a *quel*
processo. Il log ruota (`gridcraft.1.log`), quindi si cercano tutte le rotazioni.
Quando il file su disco e la dichiarazione divergono — un aggiornamento **sotto** un
processo gia' avviato — vale la dichiarazione, e si annota.

Il confronto e' fra la build **in esecuzione** e quella **di riferimento** (in
quest'ordine: `--expect-version`, l'impronta registrata, l'eseguibile di config):

| Esito | Significato | Uscita |
|---|---|---|
| `same` | stessa versione (se entrambe note, anche stessa revisione) | 0 |
| `same` + `da <altro file>` | stessa build, eseguita da un altro percorso: non e' un guasto, ma si dice | 0 |
| `different` | stessa app, **altra build**: l'entry avvierebbe un altro eseguibile | 1 |
| `unknown` | nessuna prova (PID sparito, versione illeggibile, nessun riferimento) | 0 |

```
[craft] gridcraft    porta=7990  senza credenziale | app=gridcraft (copertura 1.0)
  | cli gridcraft-cli 0.6.1 | build 0.5.0 != config 0.6.1 (NON e' la build configurata)
  | da C:\…\craft-bridge-test\gridcraft-old.exe
```

**Provato su una seconda build vera**, non simulata: l'eseguibile e' stato copiato e
la sua risorsa di versione riscritta a 0.5.0 (a lunghezza invariata), lasciando intatto
l'installazione. Sulla porta 7990 quell'eseguibile risponde col catalogo di GridCraft
(copertura **1.00** — per l'identita' per app e' "gridcraft", correttamente) e la sua
riga di avvio dice `GridCraft 0.5.0`. Con la build 0.6.1 come riferimento:
`build=different` e uscita 1; con l'aggiornamento sotto il processo (rinomino
l'eseguibile in esecuzione e ne metto uno nuovo allo stesso percorso) la versione in
esecuzione resta 0.5.0 — quella che il processo dichiara — con la nota
`l'eseguibile su disco ora dichiara 0.6.1: aggiornato sotto il processo`.

Dove finisce il verdetto: `craft-bridge-ident.py` (diagnosi, con `--build-only` per
la sola build senza handshake e `--record` per registrare quella verificata),
`craft-bridge-launch.py` (che esce 1 e dice *chi* ha trovato), e lo shim, che avvisa
all'avvio ma **procede bridged**: una build diversa parla lo stesso protocollo, mentre
il silenzio nasconderebbe esattamente il caso in cui si guida la finestra sbagliata.

**Limite che resta:** l'eseguibile dice la versione, non il contenuto: due build con la
stessa versione e senza revisione nel log sono indistinguibili.

**Perche' serve.** Messo sulla porta di un'altra app, un CLI ripiega in headless
**senza dirlo**: misurato, `deckcraft-cli mcp --connect 7975` (porta di GridCraft)
risponde `25 tool` e nessun errore. Con l'identita' il caso si vede all'avvio:

```
craft-bridge-mcp: gridcraft: sulla porta 7975 risponde un'altra app
  (copre 29/339 comandi di gridcraft): la CLI ripiegherebbe in headless senza dirlo.
  Vado headless
craft-bridge-mcp: gridcraft: modalita' headless (porta 7975, peer=craft, app estranea)
```

**Due errori miei, trovati misurando.** Il primo: la lettura delle risposte si
fermava al primo `\n`, e le app lasciano un a capo isolato dopo la risposta
precedente — la seconda richiesta leggeva un byte vuoto invece di un catalogo da
47 KB, e l'identita' risultava "sconosciuta" **a intermittenza** (dipendeva da come
i byte arrivavano). Ora la fine del messaggio si riconosce parsando il JSON. Il
secondo: `soundcraft-cli commands --json` stampa **vuoto** e il catalogo esiste solo
nella tabella testuale; senza leggerla, la sua identita' restava ignota pur essendo
verificabile.

---

## 4. Prove sperimentali

Metodo: avviare davvero l'app desktop con il canale di controllo, collegare il server MCP, e **chiamare un tool che tocca la finestra**. `tools/list` da solo non prova niente: PhotoCraft elenca gli stessi 25 tool anche puntando a una porta morta.

| # | Prova | Esito misurato |
|---|---|---|
| 1 | PhotoCraft `--control 7981 --control-token-file` | `control server listening on 127.0.0.1:7981`, PID distinto dall'app |
| 2 | bridge **senza** token | rifiuto immediato: `bridge mode needs --control-token …` |
| 3 | bridge con token corretto | 25 tool, `serverInfo` = `photocraft 0.8.2` |
| 4 | `ui_inspect` sull'app viva | stato UI reale: `brush.size 20.0`, dock, `frame: 7` |
| 5 | `ui_set {brushSize: 33}` poi `ui_inspect` | **20.0 → 33.0**: lo stato della finestra è cambiato |
| 6 | `doc_new 640x480 #204060` | `{"document":0}` — documento creato nell'app aperta |
| 7 | `ui_screenshot` | PNG reali `512x320` (21 485 B) e `640x400` (28 735 B), magic `89504e470d0a1a0a` |
| 8 | bridge con token **sbagliato** | `app: authentication required` |
| 9 | bridge verso porta **morta** | `bridge: 'ui.inspect' failed: cannot connect to 127.0.0.1:7999 …; the request was not sent` |
| 10 | GridCraft `--control 7979` + `mcp --connect 7979` | `control channel listening on 127.0.0.1:7979`; 21 tool; stderr `(connected to the GridCraft app at 127.0.0.1:7979)` |
| 11 | GridCraft `screenshot` | PNG `1440x900`, 152 171 B — la finestra vera |
| 12 | GridCraft verso porta morta | uscita **1**, `cannot connect to the GridCraft app at 127.0.0.1:7999: connection timed out` — **nessun fallback silenzioso** |
| 13 | WordCraft `--control 7981` + `mcp --connect` | 16 tool; `ui_inspect` → `canvasRect [22,184,1418,710]`, caret, pagine |
| 14 | WordCraft socket grezzo senza chiave | `{"error":"unauthorized"}` |
| 15 | App uccisa **durante** la sessione | errore per chiamata `… is not reachable: connection timed out`, il server MCP **resta vivo** |
| 16 | Wrapper con app chiusa / aperta | sceglie `headless` / `bridged`; screenshot identico (`sha256 c41932c8db312ce7`) fra bridge diretto e wrapper |

Artefatti lasciati nel repo come prova: `photocraft-live-1.png`, `photocraft-live-doc.png`, `photocraft-pilot-report.json`, `craft-photocraft-tools.json`.

### Nota di metodo

Scrivendo il wrapper ho introdotto e poi corretto un bug reale: `source.read(65536)` su una pipe **blocca** finché non ha 64 KB (o l'EOF), quindi i messaggi MCP — corti — non venivano mai inoltrati e il client andava in timeout. La copia ora usa `os.read`/`os.write` sui descrittori, senza buffering.

---

## 5. Cosa ho costruito

| File | Ruolo |
|---|---|
| [craft-bridge-recon.py](../../tools/craft-bridge-recon.py) | estrae dai binari i flag/credenziali del canale di controllo (read-only, nessuna app avviata) |
| [craft-bridge-probe.py](../../tools/craft-bridge-probe.py) | sonda MCP generica: `initialize`, `tools/list`, una chiamata, esito in JSON |
| [craft-bridge-pilot.py](../../tools/craft-bridge-pilot.py) | esegue una sequenza di chiamate sull'app aperta, salva gli artefatti immagine |
| [craft-bridge-mcp.py](../../tools/craft-bridge-mcp.py) | **shim stdio**: sceglie bridged o headless e lancia la CLI giusta |
| [craft-bridge-config.py](../../tools/craft-bridge-config.py) | installa shim e strumento di identità e riscrive le entry MCP (idempotente, con backup; riallinea i file anche quando le entry non cambiano) |
| [craft-bridge-verify.py](../../tools/craft-bridge-verify.py) | legge la config scritta e interroga **ogni entry col suo comando reale** |
| [craft-bridge-sweep.py](../../tools/craft-bridge-sweep.py) | avvia una app alla volta e misura la stessa entry headless **e** bridged |
| [craft-bridge-launch.py](../../tools/craft-bridge-launch.py) | **avvia una o più app** col canale già attivo sulle porte che la config si aspetta |
| [craft-bridge-ident.py](../../tools/craft-bridge-ident.py) | **chi risponde sulla porta e quale build ci gira**: handshake sul protocollo, app riconosciuta dal catalogo dei comandi, eseguibile in ascolto e versione dichiarata dall'app |
| [craft-bridge-doctor.py](../../tools/craft-bridge-doctor.py) | **un verdetto solo su tutto l'assieme**: repo, shim installato, entry di config, eseguibili, credenziali e build che gira sulle porte; in fondo le azioni da fare |
| [craft-bridge-tests.py](../../tools/craft-bridge-tests.py) | **le sei iniezioni di guasto, eseguibili**: rompe qualcosa di proposito, pretende il verdetto giusto da doctor/ident/launcher, rimette a posto e lascia il [report](../../reports/craft-bridge-tests.md) con il confronto sull'esecuzione precedente |

### Lo shim

`craft-bridge-mcp.py` chiede chi c'è sulla porta di controllo all'avvio e sceglie il modo: se risponde il canale dell'app guida la finestra, altrimenti usa la sessione headless. La stessa entry MCP funziona in entrambi i casi — cosa che le CLI da sole non fanno. La domanda non è una `connect()`: è un handshake sul protocollo (§3.4), perché una porta in ascolto non dice chi c'è dietro.

Il modo si sceglie **una volta sola**, di proposito: bridged e headless espongono liste di tool diverse (il bridged aggiunge `ui_*`), quindi cambiare modo a metà sessione lascerebbe il client con un `tools/list` stantio. Se l'app viene chiusa durante la sessione le chiamate danno errore esplicito, senza far morire il server.

```powershell
# entry di ~\.agents\mcp.json
{ "type": "stdio",
  "command": "C:\\Users\\auresystem\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
  "args": ["C:\\Users\\auresystem\\AppData\\Local\\Programs\\craft-bridge\\craft-bridge-mcp.py",
           "--slug", "lightcraft", "--port", "7980"] }
```

### Il configuratore

```powershell
python craft-bridge-config.py            # dry-run: dice cosa cambierebbe
python craft-bridge-config.py --apply    # installa lo shim, backup, riscrive le 11 entry
python craft-bridge-config.py --restore  # riporta le entry a `mcp` headless
```

Protegge ciò che non gli appartiene: `artcraft` (il proxy del protocollo) e `pdfcraft` (meccanismo diverso) **non vengono toccati**, e prima di scrivere crea `mcp.json.bak-<timestamp>`.

### Applicato il 13 ottobre 2026

```
da aggiornare (11): cadcraft, deckcraft, designcraft, effectcraft, filmcraft, gridcraft,
                    lightcraft, photocraft, soundcraft, vectorcraft, wordcraft
non toccate  : pdfcraft, artcraft
installato   : %LOCALAPPDATA%\Programs\craft-bridge\craft-bridge-mcp.py
backup       : ~\.agents\mcp.json.bak-20261013-135250
```

Re-run dell'installer: `da aggiornare (0), invariate (11)` — nessuna scrittura, nessun nuovo backup. Lo shim installato è **identico** alla copia nel repo (`md5 8c4250537950d10d457a2edacf9bcdfe`).

> Il 13 ott la copia installata è stata riallineata a mano più volte (dopo il docstring, dopo l'handshake di identità, dopo l'identità dal catalogo dei comandi). Le 11 entry della config non sono mai cambiate, quindi per l'installer restano invariate.
>
> Nota pratica: le entry MCP eseguono il file **installato**, non quello nel repo. Dopo ogni modifica allo shim: `cp craft-bridge-mcp.py "%LOCALAPPDATA%\Programs\craft-bridge\"` — altrimenti si misura la versione vecchia (è successo durante questa prova).

---

## 6. Verifica delle entry applicate

Ogni entry è stata esercitata **con il comando esattamente come è scritto in `~\.agents\mcp.json`**, non con una variante di comodo ([craft-bridge-verify.py](../../tools/craft-bridge-verify.py)).

**Tutte le app chiuse** — `--expect headless`: 13/13 OK, le 11 entry shim vanno headless, `artcraft` (61 tool) e `pdfcraft` (161 tool) continuano a rispondere dopo la riscrittura.

**Tre app aperte** sulle porte attese dalla config (GridCraft 7975, PhotoCraft 7976 col token della config, WordCraft 7978):

| Entry | Modo scelto | Tool | Chiamata sull'app aperta |
|---|---|---|---|
| `gridcraft` | **bridged** | 21 | `inspect_workbook` → `activeCell A1`, `mode Ready`; `screenshot` → PNG 1440x900 |
| `photocraft` | **bridged** | 25 | `ui_inspect` → stato UI della finestra |
| `wordcraft` | **bridged** | 16 | `ui_inspect` → `canvasRect [22,184,1418,710]`, caret |
| altre 8 | headless | 11–326 | — |

Run combinata: **13/13 entry OK**, 3 bridged e 8 headless nella stessa passata. In quella prova erano aperte solo quelle tre app: le altre otto erano headless *perché* chiuse, non perché incapaci di bridgeare — la prova completa è nel §6.1.

### Due trappole, entrambe corrette

Il primo `screenshot` su GridCraft è fallito con `GridCraft app at 127.0.0.1:7975 is not reachable: … mancata risposta dall'host connesso`, **mentre sullo stesso bridge `inspect_workbook` funzionava**. Isolando la variabile sono emerse due cause distinte, che ho corretto entrambe nell'harness:

1. **Occlusione della finestra.** I tool di cattura fotografano la finestra viva: se resta dietro le altre non ridisegna e la chiamata va in timeout. Portata in primo piano, il PNG `1440x900` è arrivato subito. Lo sweep ora porta la finestra davanti prima di chiamare.
2. **Argomento obbligatorio mancante.** Lo sweep chiamava `screenshot` con `{}`. Non basta: `GridCraft` vuole `path`, e con l'argomento vuoto il tool risponde senza catturare nulla. Il segnale che me l'ha rivelato è stato il caso 2 della sequenza — fallito **anche** a finestra in primo piano. Ora lo sweep legge lo schema e riempie `path`/`out` quando esistono.

**Conseguenza pratica per un agente:** prima di dichiarare "il bridge non funziona", controllare (a) che la finestra sia visibile e (b) di aver passato gli argomenti che lo schema del tool richiede. Un errore di timeout su `screenshot` non significa che il canale sia morto — `inspect_workbook` rispondeva.

Nota: le app non si comportano tutte uguale. `cadcraft` e `deckcraft` accettano `screenshot` senza `path` (scrivono in un percorso loro); `gridcraft`, `designcraft`, `effectcraft` e `soundcraft` vogliono il percorso.

### 6.1 Sweep su tutte le app

[craft-bridge-sweep.py](../../tools/craft-bridge-sweep.py) avvia una app alla volta sulla porta attesa, misura l'entry **prima** (app chiusa) e **dopo** (app aperta), scopre i tool che compaiono solo in bridged e ne chiama uno per davvero. **11/11 app shim passate a bridged**, ciascuna con una chiamata riuscita sulla finestra viva:

| App | Tool headless | Tool bridged | Tool solo-app | Chiamata riuscita |
|---|---|---|---|---|
| `cadcraft` | 11 | 14 | 3 | `screenshot` → PNG 1600x1000 |
| `deckcraft` | 25 | 25 | 0 | `screenshot` → 1440x900 |
| `designcraft` | 25 | 25 | 0 | `screenshot` → 1440x900 |
| `effectcraft` | 27 | **36** | 9 | `screenshot` → 1600x956 |
| `filmcraft` | 17 | 17 | 0 | `render_preview` → finestra viva |
| `gridcraft` | 21 | 21 | 0 | `screenshot` → 1440x900 (con `path`) |
| `lightcraft` | 326 | **502** | **176** | `ui_inspect` → stato UI |
| `photocraft` | 25 | 25 | 0 | `ui_inspect` → stato UI |
| `soundcraft` | 17 | 17 | 0 | `screenshot` |
| `vectorcraft` | 32 | 32 | 0 | `inspect_ui` → documenti/canvas |
| `wordcraft` | 16 | 16 | 0 | `ui_inspect` → `canvasRect`, caret |
| `pdfcraft` | 161 | — | — | MCP non bridgeabile (vedi §3.3) |

**Lezione: il numero di tool non è un indicatore.** Sette app su undici espongono la **stessa** lista di nomi in headless e in bridged — quello che cambia è *dove agiscono*. In headless `screenshot` renderizza il documento; in bridged fotografa la finestra. Un agente che confronta i conteggi conclude "non è cambiato niente" e sbaglia: la differenza si vede solo chiamando. Il segnale affidabile resta lo stderr dello shim, che dichiara `modalita' bridged` o `modalita' headless`.

Il report grezzo dello sweep è in [craft-bridge-sweep.json](../../reports/craft-bridge-sweep.json): per ogni app contiene i due elenchi di tool, i nomi solo-app, il comando di avvio usato e l'esito della chiamata.

---

## 7. Come si usa in pratica

1. **Un solo comando** avvia le app col canale già attivo sulla porta che lo shim
   si aspetta ([craft-bridge-launch.py](../../tools/craft-bridge-launch.py)):

   ```bash
   python craft-bridge-launch.py                          # tutte le app config
   python craft-bridge-launch.py --apps gridcraft,wordcraft
   python craft-bridge-launch.py --verify                 # + prova end-to-end dello shim
   python craft-bridge-launch.py --list                  # tabella e stato, non avvia
   python craft-bridge-launch.py --apps gridcraft --dry-run
   ```

   Le porte **non** sono scritte nello script: le legge dalla config dello shim
   (`~\.agents\mcp.json`), cioè dal `--port` che `craft-bridge-mcp.py --slug <app>
   --port <porta>` sonderà. Se un domani si cambia porta nella config, il comando
   segue da solo. Gli eseguibili e il flag del token vengono dalla tabella del
   wrapper (`--dump-apps`), quindi anche lì c'è una sola fonte.

   Cosa fa, in ordine: salta le app il cui canale è già su; avvia le altre
   **staccate dalla shell** (`DETACHED_PROCESS`, quindi le finestre restano aperte
   dopo il ritorno del comando) con `--control <porta>` e, per PhotoCraft,
   `--control-token-file` sullo **stesso** file della config; aspetta tutti i canali
   in parallelo; legge nel log di ogni app la riga con cui annuncia l'ascolto e
   chiede al peer chi è (handshake, §3.4).

   L'uscita, per ogni app: la riga di log con cui l'app annuncia il canale,
   l'identita' del peer (`peer=craft`, `app=<slug>` con la copertura del catalogo,
   la versione del binario, `autenticato` dove c'è una credenziale) e, con
   `--verify`, il modo dello shim.

   | Esito | Significato |
   |---|---|
   | 0 | ogni app richiesta ha il canale attivo (e in bridged, con `--verify`) **e la build configurata** |
   | 1 | almeno una no: la riga `diagnosi` dice perché, con la coda del log (o perché sulla porta gira un'altra build) |
   | 2 | errore d'uso (slug sconosciuto, porta duplicata) |
   | 3 | config o tabella delle app illeggibili |

   Il comando è **onesto su cosa ha provato**: «attivo» vuol dire che l'app ha
   scritto lei di essere in ascolto, oppure che il peer ha risposto all'handshake;
   una porta occupata da altro viene chiamata «occupata da altro (handshake: silent)»
   e fa uscire 1 — vedi §8. La riga `build` dice quale versione gira davvero su quella
   porta, e una build diversa da quella configurata fa uscire 1 anche col canale attivo
   (§3.5). Per sapere chi ascolta senza avviare nulla:
   `python craft-bridge-ident.py --all`.

   Se invece la domanda è «è tutto a posto?», la risposta sta in un comando solo:
   `python craft-bridge-doctor.py` — vedi sotto.

   ```bash
   python craft-bridge-ident.py --all                    # chi c'e' su ogni porta
   python craft-bridge-ident.py --slug photocraft --token-file ~/.craft-bridge/photocraft.token
   python craft-bridge-ident.py --all --wait 30          # aspetta che l'app risponda
   python craft-bridge-ident.py --all --record           # registra le build verificate
   python craft-bridge-ident.py --port 7975 --build-only # solo la build (PID + file, ~1 s)
   python craft-bridge-launch.py --apps gridcraft --record-builds   # registra avviando
   ```

   **Un comando per l'assieme.** I quattro controlli che tengono in piedi il bridge
   erano sparsi in quattro strumenti; [craft-bridge-doctor.py](../../tools/craft-bridge-doctor.py)
   li interroga tutti e chiude con una riga sola:

   ```
   craft-bridge doctor
     ok   repo            3 strumenti presenti (mcp d4539c25717c, ident 2893a81fc917, config 9a566d96d313)
     ok   shim installato 2 file identici al repo (…)
     ok   config          11 entry come le scriverebbe l'installer
     ok   percorsi        tutti i file citati dalle entry esistono
     ok   eseguibili      11 CLI e 11 app presenti (versioni: 0.10.0, 0.6.1, …)
     ok   porta 7975      gridcraft 0.6.1 = config (impronta registrata (…))
     ok   app aperte      1 su 11 porte in ascolto

   VERDETTO: tutto in ordine (nessuna azione)
   ```

   Non duplica niente: le entry attese le chiede a `craft-bridge-config.py` (la stessa
   funzione che le scrive) e le build a `craft-bridge-ident.py` (le stesse funzioni
   della diagnosi), quindi i tre non possono divergere. Le prove, tutte eseguite:
   shim installato alterato di un byte → `FIX shim installato` con l'hash diverso e
   l'azione che lo ripara (e `--apply` lo ripara davvero: il doctor poi conferma `ok`);
   entry cambiata e `command` inesistente → `FIX config` + `FIX percorsi`; eseguibile
   mancante → `FIX eseguibili`; **build 0.5.0** sulla porta di gridcraft → `FIX porta
   7975 … gira 0.5.0 invece di 0.6.1`; GridCraft sulla porta di deckcraft → `FIX porta
   7972 … risponde un'altra app (copre 0.11 dei suoi comandi)`; PhotoCraft avviato con
   un token **diverso** da quello della config → `FIX porta 7976 … l'app ha rifiutato
   la credenziale` (il valore non viene mai stampato, si vede solo l'esito).

   | Esito | Significato |
   |---|---|
   | 0 | niente da sistemare (le voci `nota` non contano: sono fatti, non guasti) |
   | 1 | almeno una cosa da sistemare, elencata in fondo con l'azione |
   | 2 | errore d'uso |
   | 3 | config o tabella delle app illeggibili |

   `--no-live` salta le porte (solo repo, shim, config, eseguibili: ~1 s), `--json`
   da' `checks`/`problems`/`actions` per un altro programma. Costo completo: ~1,3 s
   con le app chiuse, qualche secondo in più con quelle aperte (una lettura del
   catalogo per porta occupata).

   ### La suite: gli stessi guasti, eseguibili

   Le sei prove raccontate qui erano a mano, una per una. Ora stanno in
   [craft-bridge-tests.py](../../tools/craft-bridge-tests.py), che **rompe qualcosa di proposito**
   e pretende il verdetto giusto dai tre strumenti:

   ```
   craft-bridge tests
     ok   stato pulito               doctor: nessuna azione
     ok   shim installato stantio    accusato e riparato dall'azione indicata
     ok   entry di config sbagliata  doctor e installer concordano: 1 entry da aggiornare
     ok   percorso inesistente       FIX percorsi: cadcraft.command
     ok   eseguibile mancante        lightcraft app, lightcraft cli
     ok   porta chiusa               ident unreachable, shim headless (porta 7979)
     ok   app giusta sulla porta     gridcraft 7975: ident/doctor/launcher tutti d'accordo
     ok   build diversa              doctor, ident e launcher: tutti e tre exit 1 con 0.5.0 != 0.6.1
     ok   altra app sulla porta      GridCraft su 7972: doctor e ident lo riconoscono
     ok   credenziale rifiutata      token diverso: accusato da doctor e ident (valore mai stampato)

   10 passati, 0 falliti, 0 saltati
   ```

   `--static` esegue i soli casi che non avviano app (~10 s); la suite completa
   **avvia app vere su porte libere** e impiega ~45 s. Le regole di sicurezza sono
   nel docstring e valgono sempre: la config vera non viene mai scritta (i casi la
   riguardano su una copia con `--config`), l'unico file vero toccato e' lo shim
   installato — un byte in più, dentro un `try/finally` che lo rimette a posto, con
   il `--apply` che la suite stessa esegue; se una porta e' occupata il caso si
   **salta** invece di uccidere qualcosa che non ha avviato; file temporanei, log e
   token di prova vengono rimossi (verificato: seconda esecuzione di fila, 10/10).

   Ogni esecuzione lascia **due report** accanto a sé —
   [craft-bridge-tests.json](../../reports/craft-bridge-tests.json) per la macchina (esito,
   durata, impronte degli strumenti, casi) e
   [craft-bridge-tests.md](../../reports/craft-bridge-tests.md) per chi legge — e il confronto con
   l'esecuzione precedente è **automatico**: la baseline è il json che sta per essere
   sovrascritto, e le differenze (casi cambiati, comparsi o spariti, impronte degli
   strumenti) finiscono sia a video sia nel markdown, con la durata a parte come
   contesto, quindi due giri a distanza di giorni si leggono senza ricostruirli a
   memoria. Per confrontare due report qualsiasi: `--compare vecchio.json`;
   `--no-report` non scrive niente, `--no-compare` non legge niente. La destinazione
   si indica con `--report`, o con `--out` come negli altri strumenti del progetto.

   **Due difetti trovati proprio automatizzando.** Il primo, nei binari: con una
   credenziale rifiutata l'app **chiude la connessione**, e la `sendall` successiva
   alzava `ConnectionAbortedError` — `ident` moriva con un traceback e **nessun
   verdetto** (uscita 1, stdout vuoto); lo shim installato avrebbe potuto fare lo
   stesso all'avvio, cioe' perdere il server MCP. Ora un errore di rete non solleva:
   si torna quello che si e' letto, e il verdetto lo si da' lo stesso. Il secondo,
   di processo: dopo aver modificato shim o strumento, i file **installati** restano
   indietro finche' non si esegue `--apply` — la suite lo segnala subito come
   `FAIL stato pulito` con la riga del doctor che lo spiega.

2. In Freebuff: **Connectors → Refresh**. Le app aperte diventano guidabili; quelle chiuse restano headless.

Per le app senza credenziale basta il primo comando senza `--control-token-file`. Le porte attese sono la scala dello shim: `cadcraft 7971`, `deckcraft 7972`, `designcraft 7973`, `filmcraft 7974`, `gridcraft 7975`, `photocraft 7976`, `soundcraft 7977`, `wordcraft 7978`, `vectorcraft 7979`, `lightcraft 7980`, `effectcraft 9877` (le ultime tre sono i default documentati dalle rispettive CLI).

Lo stesso passo a mano, se serve una sola app e un comando esplicito:

```powershell
& "C:\Program Files\PhotoCraft\photocraft.exe" --control 7976 `
    --control-token-file "$HOME\.craft-bridge\photocraft.token"
```

Il file del token lo scrive l'app: non serve inventarlo né metterlo in chat.

---

## 8. Limiti e cosa non è verificato

- **11 app su 12 bridgeate e verificate dal vivo**, ognuna con una chiamata riuscita sulla finestra (§6.1). PdfCraft è l'eccezione strutturale: app guidabile, MCP senza bridge.
- **Avvio**: [craft-bridge-launch.py](../../tools/craft-bridge-launch.py) è stato provato **su tutte e 11 le app in una sola chiamata** (`--verify`: canale su, riga di log, **app identificata con copertura 1.00**, shim in bridged, 11/11, exit 0; i tool bridged coincidono con quelli misurati in §6.1 — `lightcraft 502`, `effectcraft 36`, `cadcraft 14`), sul rilancio a canale già attivo (non riavvia, non duplica) e sui casi difficili: peer muto, peer che parla un altro protocollo, **app sbagliata sulla porta**, token in config diverso da quello dell'app, `--dry-run`, `--json`, porte duplicate, slug sconosciuto. Le stesse prove parlano ai binari via protocollo, non alla chat di Freebuff: resta non osservato l'agente che usa quei server attraverso l'interfaccia.
- **Cattura della finestra**: richiede la finestra visibile (vedi §6). Un agente che chiama `screenshot` su un'app in background può ricevere un errore di timeout che sembra un guasto del bridge e non lo è.
- **Il bridged ripiegava in silenzio su un peer muto — ora non più** (misurato e corretto il 13 ott). Con un socket che **accetta la connessione e poi tace** al posto dell'app, lo shim dichiarava `modalita' bridged` e la CLI di DeckCraft rispondeva `25 tool, nessun errore`: headless travestito, indistinguibile per lista di tool. La scelta del modo ora si fa con l'handshake (§3.4): `peer=silent`/`foreign` → lo shim va **headless** e lo scrive su stderr; il launcher esce 1; `craft-bridge-ident.py` dice il verdetto. Provato nei tre casi: mute → headless, HTTP estraneo → headless, app vera → bridged.
  - L'**app sbagliata** sulla porta è riconosciuta anche lei (§3.5): l'handshake dice che il peer parla il protocollo, il catalogo dei comandi dice *quale* app è. Misurato: 1.00 di copertura per l'app giusta, ≤ 0.15 per qualunque altra; con la app sbagliata lo shim va headless e il launcher esce 1.
  - La **build** sulla porta è riconosciuta (§3.5): l'app si identifica col catalogo, la versione con il PID della porta, l'eseguibile di quel processo e la riga di avvio che l'app scrive da sola. Misurato su una seconda build vera della stessa app (0.5.0 contro 0.6.1): copertura del catalogo **1.00** — per l'identità per app è «l'app giusta» — e `build=different`, con `ident`/launcher in uscita 1 e lo shim che avvisa all'avvio ma procede bridged. Provato anche il caso in cui l'eseguibile viene aggiornato **sotto** il processo (rinomina + nuovo file allo stesso percorso): la versione in esecuzione resta quella dichiarata dal processo, con la nota che il file su disco ora è un'altra cosa.
  - Limite che resta: l'eseguibile dice la versione, non il contenuto. Due build con la stessa versione — e senza revisione nella riga di avvio — sono indistinguibili; il confronto non è una verifica di integrità (nessun hash del binario).
  - **Lo shim installato non seguiva il repo — ora sì** (trovato mettendo in funzione il controllo della build). `craft-bridge-config.py` copiava lo shim **solo** se una entry della config cambiava: con 11 entry già a posto il comando diceva «da aggiornare (0)» e lo shim installato restava quello vecchio (hash diversi, misurato). Ora confronta i file e li riallinea quando serve, e installa accanto allo shim anche [craft-bridge-ident.py](../../tools/craft-bridge-ident.py) — è lui che risponde alla domanda sulla build, quindi senza quel file lo shim installato non potrebbe farla. Idempotente: al secondo giro non riscrive nulla.
  - Costo: all'avvio di un server MCP l'handshake aggiunge una richiesta (millisecondi con l'app viva; fino a ~4.5 s con un peer muto, prima di dichiarare headless). Con `--require-bridge` un peer non identificato esce 3 invece di ripiegare.
- **Nessuna prova di persistenza**: ogni misura è su una app appena avviata, una alla volta. Il comportamento con più app aperte contemporaneamente e con l'utente che lavora dentro non è stato misurato.
- **PdfCraft non verificato**: usa un file di controllo con port+token e il suo MCP non ha `--connect`/`--bridge`. Resta fuori dalla configurazione bridged.
- **`--automation-read-root`/`--automation-write-root` non sono efficaci in bridged** (l'app applica i propri root): la configurazione dello shim non li passa, quindi in bridged i confini li decide l'app. Da valutare prima di dare a un agente accesso a file su una macchina condivisa.
- **Altri client non aggiornati**: la riscrittura riguarda solo `~\.agents\mcp.json` (Freebuff). Claude Code, Claude Desktop e Antigravity restano sulle entry headless: lì il bridged si aggiunge con una modifica equivalente ai loro file.
- **La chat/UI di Freebuff non è stata osservata**: gli esperimenti usano i binari e il protocollo, non l'interfaccia dell'app.
- I token di prova stanno in `~\.craft-bridge\` (creati durante gli esperimenti) e la chiave di WordCraft in `%APPDATA%\WordCraft\control-key.local-7981`: sono file locali dell'utente, fuori dal repo.
