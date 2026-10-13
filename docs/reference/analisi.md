---
type: Reference
title: "Analisi dell'ecosistema MCP ArtCraft"
description: "Inventario dei 13 server MCP configurati, ambiente di lavoro, decisioni prese e stato del ponte."
resource: ../../docs/reference/analisi.md
tags: [analisi, mcp, inventario]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:23:21Z }
status: stable
---

# ArtCraft — Analisi per l'integrazione MCP globale

**Data analisi:** 13 ottobre 2026 — aggiornata il 13 ottobre 2026 con la sperimentazione della modalità bridged (§10)
**Macchina:** Windows x64, utente `auresystem`
**Stato:** documento di analisi — **nessuna modifica applicata**, in attesa di conferma

---

## 1. Contesto e obiettivo

L'utente ha:

1. installato il **launcher di ArtCraft** (`artcraft-launcher-0.3.2-windows-x64.msi`);
2. scompattato l'**MCP ArtCraft v1.1.0** in `C:\Users\auresystem\Downloads\artcraft-mcp-v1.1.0`.

Obiettivo dichiarato: capire **come renderlo disponibile globalmente a Freebuff e agli altri framework** (Claude, Codex, dsh harness), se serve **una skill per ogni applicativo della suite** o basta l'MCP v1.1.0, e cosa è **realmente installato** sulla macchina.

Riferimenti forniti: <https://github.com/storytold/artcraft> · <https://github.com/theCosmicCrafter/artcraft-mcp>

---

## 2. Metodo

Tutto ciò che segue è stato **verificato direttamente sulla macchina** (registro Windows, tabelle MSI, feed del launcher, config dei client, esecuzione del binario) e integrato con la documentazione ufficiale dei repository. Le affermazioni non verificabili sono marcate esplicitamente.

Test eseguito sul binario (handshake MCP reale):

```
echo '{"jsonrpc":"2.0","id":1,"method":"initialize",...}' | bin\artcraft-mcp.exe
→ {"result":{"protocol_version":"2025-03-26","server_info":{"name":"artcraft-mcp","version":"0.1.0"}}}
tools/list → 61 tool
```

---

## 3. Inventario di ciò che è realmente installato

### 3.1 Launcher — INSTALLATO (via MSI)

| Voce | Valore verificato |
|---|---|
| ProductName | `ArtCraft Launcher` |
| Versione | `0.3.2` |
| Publisher | `Learning Machines LLC` |
| ProductCode | `{252C0C55-6539-443D-A917-D873F8E3A822}` |
| Installazione | `%LOCALAPPDATA%\Programs\ArtCraft Launcher\artcraft-launcher.exe` |
| Dati/stato | `%LOCALAPPDATA%\ArtCraft Launcher\` (`feed.json`, `releases.json`, `downloads\`) |
| Contenuto MSI | **un solo file**: `artcraft-launcher.exe` |

### 3.2 Che cosa installa il launcher (feed ufficiale)

`feed.json` elenca **13 app** — il launcher più **12 Crafting Apps**:

| App | Repo | Tag |
|---|---|---|
| ArtCraft Launcher | storytold/craft-launcher | v0.3.2 |
| CADCraft | storytold/cadcraft | v0.6.2 |
| DeckCraft | storytold/deckcraft | v0.6.1 |
| DesignCraft | storytold/designcraft | v0.7.1 |
| EffectCraft | storytold/effectcraft | v0.9.2 |
| FilmCraft | storytold/filmcraft | v0.7.2 |
| GridCraft | storytold/gridcraft | v0.6.1 |
| LightCraft | storytold/lightcraft | v0.7.1 |
| PdfCraft | storytold/pdfcraft | v0.7.1 |
| PhotoCraft | storytold/photocraft | v0.8.2 |
| SoundCraft | storytold/soundcraft | v0.6.1 |
| VectorCraft | storytold/vectorcraft | v0.10.0 |
| WordCraft | storytold/wordcraft | v0.6.1 |

> Nota: il sito elenca anche **FigCraft**; nel feed locale del launcher non compare (verificato: 13 voci esatte).

### 3.3 Stato effettivo della suite — TUTTE E 12 LE APP INSTALLATE

> **⚠️ Correzione (13 ott 2026, post-verifica).** Una prima ricognizione concludeva "nessuna app installata": era **sbagliata**. Cercavo soltanto in `%LOCALAPPDATA%\Programs`, mentre le Crafting Apps sono installate **machine-wide in `C:\Program Files\<App>\`**. Verifica corretta:

Registro Windows (`Uninstall`): `CADCraft 0.6.2`, `DeckCraft 0.6.1`, `DesignCraft 0.7.1`, `EffectCraft 0.9.2`, `FilmCraft 0.7.2`, `GridCraft 0.6.1`, `LightCraft 0.7.1`, `PdfCraft 0.7.1`, `PhotoCraft 0.8.2`, `SoundCraft 0.6.1`, `VectorCraft 0.10.0`, `WordCraft 0.6.1`.

Ogni app installa **due eseguibili** in `C:\Program Files\<App>\`:

| File | Ruolo |
|---|---|
| `<app>.exe` | applicazione desktop (GUI) |
| `<app>-cli.exe` | CLI headless, che espone il sottocomando **`mcp`** |

| App | CLI | Versione | MCP |
|---|---|---|---|
| CADCraft | `cadcraft-cli.exe` | 0.6.2 | ✅ Connected |
| DeckCraft | `deckcraft-cli.exe` | 0.6.1 | ✅ Connected |
| DesignCraft | `designcraft-cli.exe` | 0.7.1 | ✅ Connected |
| EffectCraft | `effectcraft-cli.exe` | 0.9.2 | ✅ Connected |
| FilmCraft | `filmcraft-cli.exe` | 0.7.2 | ✅ Connected |
| GridCraft | `gridcraft-cli.exe` | 0.6.1 | ✅ Connected |
| LightCraft | `lightcraft-cli.exe` | 0.7.1 | ✅ Connected |
| PdfCraft | `pdfcraft-cli.exe` | 0.7.1 | ✅ Connected |
| PhotoCraft | `photocraft-cli.exe` | 0.8.2 | ✅ 25 tool |
| SoundCraft | `soundcraft-cli.exe` | 0.6.1 | ✅ Connected |
| VectorCraft | `vectorcraft-cli.exe` | 0.10.0 | ✅ Connected |
| WordCraft | `wordcraft-cli.exe` | 0.6.1 | ✅ 16 tool |

- Le CLI **non sono nel PATH**: la config MCP deve usare il **path assoluto**.
- L'app desktop **generativa** ArtCraft (`storytold/artcraft`) **non** è installata: assenti `%LOCALAPPDATA%\ai.artcraft.app\` e le credenziali in `~\Artcraft\credentials\`.

**Conclusione corretta:** la suite Crafting Apps è **completamente installata e operativa**.

### 3.4 Pacchetto MCP v1.1.0 — estratto, non registrato

| Voce | Valore |
|---|---|
| Percorso | `C:\Users\auresystem\Downloads\artcraft-mcp-v1.1.0` |
| Binario | `bin\artcraft-mcp.exe` (10,26 MB, Rust, self-contained, zero dipendenze) |
| Tool esposti | **61** (verificato con `tools/list`) |
| Protocol | `2025-03-26` |
| Autenticazione | cookie/sessione ArtCraft (NON presente → il server parte ma le chiamate falliranno) |
| Skill incluse | `skills/artcraft-mcp/SKILL.md` + 6 reference; `skills/open-source-contributor/` |

Discrepanze interne al pacchetto da conoscere (non bloccanti):

- `AGENTS.md` cita anche `artcraft-mcp-server.exe`: **non esiste**, c'è solo `artcraft-mcp.exe`. Seguire il binario presente.
- `ArtCraft-MCP-Setup-Guide.md` dice "40+ tool / protocol 2025-03-26": il pacchetto reale ne espone 61.
- `setup_mcp.py` copre **solo Windsurf, Claude Desktop, Cursor**.

### 3.5 Difetto di conformità dell'MCP generativo (bloccante, verificato)

`artcraft-mcp.exe` risponde a `initialize` con chiavi **snake_case** anziché camelCase:

```json
{"result":{"protocol_version":"2025-03-26","server_info":{"name":"artcraft-mcp",...}}}
```

La specifica MCP richiede `protocolVersion` e `serverInfo`. I client **rigorosi** rifiutano quindi il server. Verificato su Claude Code:

```
artcraft: ...\artcraft-mcp.exe - ✘ Failed to connect — INVALID_RESULT:
  Invalid result for initialize: expected string at path ["protocolVersion"],
                                 expected object at path ["serverInfo"]
```

Mappa completa dei campi non conformi (verificata interrogando il server):

| Metodo | Campo inviato dal server | Campo richiesto dallo standard MCP |
|---|---|---|
| `initialize` | `protocol_version` | `protocolVersion` |
| `initialize` | `server_info` | `serverInfo` |
| `initialize` | `capabilities.tools.list_changed` | `listChanged` |
| `tools/list` | `tools[].input_schema` | `inputSchema` |
| `tools/call` | `result.is_error` | `isError` |

**Stato: RISOLTO** con [artcraft-mcp-proxy.py](../../tools/artcraft-mcp-proxy.py) — uno shim stdio che riscrive **solo** questi campi di protocollo (senza toccare gli schemi dei tool, che usano correttamente le keyword JSON Schema) e inoltra tutto al binario reale in UTF-8 binario, senza traduzione di newline.

Verifica: `artcraft -> ✔ Connected`, `initialize` con `protocolVersion`/`serverInfo` corretti, `tools/list` = 61 tool.

---

## 4. Distinzione CRITICA: due ecosistemi diversi

Questo è il punto che chiarisce la domanda "skill per app o basta l'MCP v1.1.0".

```
┌──────────────────────────────────────────────────────────────────┐
│ A) PIATTAFORMA GENERATIVA ArtCraft  (api.storyteller.ai)         │
│    • app desktop "ArtCraft" (storytold/artcraft)                 │
│    • UN MCP:  artcraft-mcp v1.1.0  → 61 tool                     │
│      (repo TERZO: theCosmicCrafter/artcraft-mcp)                 │
│    • genera immagini/video/3D/audio via cloud a crediti          │
└──────────────────────────────────────────────────────────────────┘
                              ⚡ NON lo stesso prodotto ⚡
┌──────────────────────────────────────────────────────────────────┐
│ B) CRAFTING APPS SUITE  (storytold/*, installata dal launcher)   │
│    • 12 app desktop native (PhotoCraft, FilmCraft, CADCraft…)    │
│    • OGNI app ha la PROPRIA CLI e il PROPRIO MCP:                │
│        photocraft-cli mcp / filmcraft-cli mcp / cadcraft-cli mcp │
│    • funziona in locale; niente crediti cloud ArtCraft           │
└──────────────────────────────────────────────────────────────────┘
```

**Conseguenze pratiche**

1. **`artcraft-mcp` v1.1.0 NON copre la suite Crafting Apps.** Sono mondi separati: owner GitHub diverso, backend diverso (cloud a crediti vs app locali).
2. Il pacchetto `theCosmicCrafter/artcraft-mcp` è, da quanto documentato pubblicamente, **un progetto terzo/community** per la piattaforma generativa: non risulta un componente ufficiale della suite né dei repo `storytold/*`. Va trattato come dipendenza di terze parti (supply chain).
3. Se in futuro installi le Crafting Apps, ognuna richiede la **propria** registrazione MCP.

---

## 5. Dove ogni client legge gli MCP (verificato sulla macchina)

| Client | Stato | File di config MCP | Skill |
|---|---|---|---|
| **Freebuff** | installato (`@codebufffreebuff-desktop`) | **`~\.agents\mcp.json`** (via `McpConfigStore` dell'orchestrator); pannello UI **Connectors** + pulsante **Refresh** | `~\.agents\skills\<nome>\SKILL.md`; skill account cloud in `%USERPROFILE%\.config\freebuff-desktop\account-skills\...` |
| **Claude Code** | v2.1.296 | `~\.claude.json` → chiave `mcpServers` (scope utente); progetto: `.mcp.json`; CLI: `claude mcp add -s user` | `~\.claude\skills\<nome>\SKILL.md` |
| **Claude Desktop** | installato | `%APPDATA%\Claude\claude_desktop_config.json` → `mcpServers` (attualmente **vuoto**) | — |
| **dsh (DeepSeek Harness)** | v0.11.1 | `%APPDATA%\dsh-desktop\harness` — server MCP nelle patch `cordis.patch.yml` (livello home + livello profilo, id plugin `dsh-mcp-client`) | `$DSH_HOME\skills` / skill gestite dal profilo |
| **Codex** | **NON installato** | `~\.codex\config.toml` → `[mcp_servers.<nome>]` (da documentare, non eseguibile ora) | AGENTS.md |
| **Antigravity** | installato | `~\.gemini\config\mcp_config.json` → `mcpServers` (contiene già `notebooklm`) | — |
| Altri presenti | Trae, OpenCode, OpenClaw, OpenFang, Rowboat, Continue, Qoder, Vibe, `.codeium` | propri file | — |

### 5.1 Come Freebuff carica davvero gli MCP (verificato nel bundle dell'app)

Analizzando `resources\orchestrator\orchestrator.js`, il processo che esegue realmente il lavoro:

```js
var agentsConfigPath = (home = homedir()) => join(home, ".agents", "mcp.json");
var CONFIG_DISPLAY_PATH = "~/.agents/mcp.json";
var stdioEntry = z.object({ type: z.literal("stdio").optional(), command, args, env, cwd })
```

- La classe **`McpConfigStore`** legge **`~\.agents\mcp.json`** e valida ogni entry con `stdioEntry` / `remoteEntry`.
- La UI si chiama **Connectors** e ha un pulsante **Refresh** che ricarica la configurazione (l'messaggio d'errore del bundle dice: *"...then press Refresh in Connectors"*).
- Esiste un **sidecar** `~\.freebuff\mcp.json`, ma è **stato interno** (`serverId`, `launchHash`, `manifestHash`), **non** configurazione utente: non va duplicato nulla lì.
- Trasporti accettati: `stdio` e `http`. Il tipo `sse` è rifiutato; gli URL remoti devono essere `https`.
- **Variabili d'ambiente**: Freebuff risolve solo `HOME`, `PATH`, `SHELL`, `USER`, `LANG`, `TMPDIR`. Per tutte le altre **non legge i segreti dalla shell**: i valori vanno scritti **letteralmente** dentro `env`.

**Conseguenza pratica (verificata campo per campo):** le 13 entry scritte sono valide per questo schema — `type: "stdio"`, `command`, `args` (array di stringhe), `env` (mappa stringa→stringa).

> Nota: il bundle SDK (`app.asar`) contiene anche un loader multi-directory (`<cwd>\.agents`, `<parent>\.agents`, `~\.agents`) usato **solo dai suoi test**, non dall'app desktop: a runtime conta il `McpConfigStore`.

L'API dell'orchestrator risponde su `http://127.0.0.1:57631` ma `/api/mcp` e `/api/connectors` restituiscono **401** senza il token dell'app, quindi la verifica programmatica va fatta dal pannello Connectors.

Stato attuale dei server MCP globali:
- Claude Code: `blender`, `drawio`, `railway`
- Antigravity: `notebooklm`
- Freebuff: nessun `~\.agents\mcp.json`
- dsh: nessun server configurato

**Conclusione sul "globale":** non esiste un unico punto di registrazione MCP condiviso da tutti i client. "Globale" = **stesso binario + stessa entry replicata nei file di config di ciascun client**, quindi serve uno script d'installazione multi-client (il `setup_mcp.py` fornito non basta).

---

## 6. Risposte sintetiche alle domande

**D1 — Come implementarlo globalmente (Freebuff + Claude + Codex + dsh)?**
Non c'è un registro MCP unico. Servono: (a) binario in **path stabile** (non `Downloads`), (b) credenziali fuori dal pacchetto, (c) la **stessa entry `artcraft`** scritta nei file di config di ogni client. dsh ha un `dsh-config-manager` che gestisce/backuppa MCP e skill, ma nel verso **altri agenti → DSH** (import/backup), quindi **non** è un hub che scrive verso gli altri client.

**D2 — Skill per ogni app della suite o basta l'MCP v1.1.0?**
Sono due cose diverse:
- la piattaforma **generativa** = **UN** MCP (v1.1.0) → basta **UNA** skill `artcraft-mcp` (già fornita nel pacchetto);
- le **Crafting Apps** = 12 MCP (uno per app) → ha senso una skill **per app**, ma conviene crearle man mano, solo per le app che usi davvero.

Raccomandazione: **una skill globale** per l'MCP generativo ora; skill per-app in seguito, on demand. Gli MCP sono auto-descrittivi (schema per ogni tool), quindi la skill è un'ottimizzazione, non un requisito.

**D3 — Suite installata con MSI + software/CLI? Oppure serve la CLI che installa l'MCP 1.1.0?**
- **Sì, la suite è installata**: launcher + **tutte e 12** le Crafting Apps, ognuna con la propria CLI in `C:\Program Files\<App>\<app>-cli.exe` che espone il sottocomando `mcp`. Installazione machine-wide (richiede privilegi elevati; l'utente le ha installate).
- **Non esiste** una "CLI che installa l'MCP 1.1.0". `setup_mcp.py` **non installa nulla**: individua un binario già presente e modifica i JSON di config, e solo per 3 client. Per Freebuff/Claude Code/dsh/Codex è servito lo script dedicato [install-craft-mcp.ps1](../../install/install-craft-mcp.ps1).

---

## 7. Gap e blocchi da risolvere prima dell'uso

| # | Gap | Impatto | Mitigazione |
|---|---|---|---|
| G1 | **Credenziali ArtCraft assenti** | Il server parte ma ogni tool fallisce in auth | Creare `~\Artcraft\credentials\artcraft_session.txt` + `artcraft_avt.txt` (cookie da artcraft.ai) **oppure** usare `ARTCRAFT_API_KEY` / `ARTCRAFT_MCP_PRIVATE_SESSION_TOKEN` |
| G2 | Binario dentro **`Downloads`** | Path volatile, rischio pulizia | Copiare in path stabile per-utente |
| G3 | `setup_mcp.py` copre solo 3 client | Freebuff/Codex/dsh non configurati | Script d'installazione multi-client dedicato |
| G4 | **Codex non installato** | Non configurabile ora | Documentare la config target; applicare quando installato |
| G5 | Dipendenza **terza parte** (community repo) | Supply chain / fiducia | Pin di versione, hashing, esecuzione per-utente |
| G6 | `~\.agents\skills` è un **symlink** a `~\repos\craft-skills-flow\skills` | Scrivervi = scrivere in quel repo | Decidere: scrivere nel repo o sostituire con cartella reale |
| G7 | Tool di **billing** esposti (checkout/subscription) | Un agente potrebbe avviare acquisti | Restringere i tool / policy in `AGENTS.md` / skill |
| G8 | dsh espone i MCP via `cordis.patch.yml` | Editing manuale rischioso | Usare la UI/import di dsh |

---

## 8. Rischi

1. **Confusione tra i due ecosistemi** → si rischia di generare skill/MCP per le Crafting Apps pensando che l'MCP v1.1.0 le copra.
2. **Segreti nei file di config** → i cookie di sessione sono credenziali: non devono finire in git né nei `SKILL.md`.
3. **Costo** → generazione a crediti: `artcraft_estimate_cost` va imposto come passo obbligatorio prima di ogni generazione (la skill lo prevede).
4. **Duplicazione skill** → molte skill quasi identiche aumentano il rumore nel contesto del modello.

---

## 9. Esito dell'installazione (13 ott 2026)

Eseguito [install-craft-mcp.ps1](../../install/install-craft-mcp.ps1) — **13 server MCP** registrati in **4 client** (52 registrazioni).

| Client | File | Esito |
|---|---|---|
| Freebuff | `~\.agents\mcp.json` | ✅ 13 server (file creato) |
| Claude Desktop | `%APPDATA%\Claude\claude_desktop_config.json` | ✅ 13 server, `preferences`/`coworkUserFilesPath` preservati |
| Antigravity | `~\.gemini\config\mcp_config.json` | ✅ 13 server, `notebooklm` preservato |
| Claude Code | `~\.claude.json` (via CLI) | ✅ 13 server; `blender`/`drawio` preservati |

Verifica reale con `claude mcp list`:

```
cadcraft, deckcraft, designcraft, effectcraft, filmcraft, gridcraft,
lightcraft, pdfcraft, photocraft, soundcraft, vectorcraft, wordcraft  ->  ✔ Connected
artcraft (via proxy)  ->  ✔ Connected
```

| Asse | Esito |
|---|---|
| Idempotenza (re-run) | ✅ `added=0, unchanged=13` su ogni client, nessun nuovo backup |
| Backup preventivi | ✅ `.bak.20261013-130016` per i 2 config preesistenti |
| Binario stabile | ✅ `%LOCALAPPDATA%\Programs\artcraft-mcp\artcraft-mcp.exe` |
| MCP delle 12 app | ✅ funzionanti e verificati |
| MCP generativo | ✅ conforme e connesso via proxy (§3.5) |
| dsh / Codex | ⚠️ manuali (non automatizzati) |

---

## 10. Modalità bridged: guidare le app aperte invece di sessioni headless

Le 12 entry MCP usano `*-cli.exe mcp`, cioè una sessione **headless**: motore in-process, nessuna finestra. Ma ogni app sa esporre un **canale di controllo** sulla finestra vera, e la CLI sa collegarsi a quel canale:

```
<app>.exe --control PORT            # l'app apre il canale di controllo
<app>-cli.exe mcp --connect PORT    # il server MCP guida quella finestra
```

Sperimentato dal vivo su **tutte e 12 le app**: le 11 con canale su porta passano a bridged, ognuna con una chiamata riuscita sulla finestra vera — LightCraft passa da 326 a **502** tool (176 solo in bridged), EffectCraft da 27 a 36, CADCraft da 11 a 14. Il bridged restituisce lo stato UI (`ui_inspect`), accetta modifiche di stato (in PhotoCraft `brushSize` 20 → 33 rileggibile), crea documenti nell'app aperta e cattura screenshot reali della finestra. PdfCraft fa eccezione: la sua app si guida via file di controllo, ma il suo server MCP non ha un flag di bridge (verificato: `unknown option --connect`).

Tre app verificano una credenziale sul canale di controllo:

| App | Credenziale | Handshake | Rifiuto senza credenziale |
|---|---|---|---|
| PhotoCraft | `control-token` 64-hex (`--control-token`, `--control-token-file`, env `PHOTOCRAFT_CONTROL_TOKEN`/`_FILE`) | `{"method":"auth","params":{"token":"…"}}` | `{"error":"authentication required"}` |
| WordCraft | `control key` 64-hex, file `control-key.local-<porta>` scritto dall'app (env `WORDCRAFT_CONTROL_KEY`) | `{"method":"auth","params":{"key":"…"}}` | `{"error":"unauthorized"}` |
| PdfCraft | `token` (32 char) nella **porta dinamica** + file di controllo con `pid`/`port`/`token` | `{"method":"auth","params":{"token":"…"}}` | `{"error":{"code":-32001,"message":"authenticate first: auth {token}"}}` |

Dettagli che contano: il gate è **nel processo dell'app**, non nella CLI (un token sbagliato non passa); PhotoCraft **genera e scrive da sé** il token se il file non esiste, quindi il segreto non deve transitare in chat né in configurazione.

Per le altre app il canale è una porta loopback senza credenziale (PdfCraft fa eccezione: usa un *file* di controllo con port+token e il suo MCP non ha un flag di bridge). Con l'app chiusa e nessuno in ascolto il bridged **non ripiega**: GridCraft esce 1 con `cannot connect to the GridCraft app at …`, PhotoCraft risponde per chiamata `… the request was not sent`. Con una porta occupata da qualcun altro che accetta la connessione e poi tace, però, il ripiego silenzioso esisteva (misurato su DeckCraft: 25 tool headless e nessun errore). Da qui l'**handshake** con cui lo shim decide il modo: chiede al peer di parlare il protocollo (un metodo inesistente, di cui si attende l'errore) e va in headless se ottiene silenzio o byte estranei, invece di dichiarare bridged e ripiegare al primo tool. E siccome al canale si puo' chiedere **quale** app sia — dichiara il proprio catalogo di comandi, che il CLI installato conosce: copertura 1.00 per l'app giusta, ≤ 0.15 per qualunque altra — lo shim riconosce anche l'app sbagliata sulla porta, che un CLI da solo non contesta (`deckcraft-cli mcp --connect 7975` sulla porta di GridCraft risponde 25 tool e nessun errore). La prova che dietro la porta ci sia l'app è quindi la riga di log che l'app scrive **più** la risposta dell'handshake — non l'esito della connessione. Da qui lo shim [craft-bridge-mcp.py](../../tools/craft-bridge-mcp.py), che sonda la porta all'avvio e sceglie bridged o headless, rendendo la stessa entry MCP valida in entrambi i casi.

**Applicata il 13 ott 2026** su `~\.agents\mcp.json`: 11 entry passano ora dallo shim ([craft-bridge-config.py](../../tools/craft-bridge-config.py)), con backup `mcp.json.bak-20261013-135250`; `pdfcraft` e `artcraft` non toccati. Verifica col comando esattamente come configurato ([craft-bridge-verify.py](../../tools/craft-bridge-verify.py)): **13/13 entry OK** — con le app chiuse le 11 entry shim vanno headless, con GridCraft/PhotoCraft/WordCraft aperte sulle porte attese le stesse entry vanno **bridged**. Re-run dell'installer: 0 modifiche.

**Rapporto completo, matrice per app e prove misurate: [craft-bridge.md](./craft-bridge.md).**

---

## 11. Documenti collegati

- [spec.md](./spec.md) — requisiti e architettura target
- [piano.md](./piano.md) — fasi di esecuzione, verifiche, rollback
- [install-craft-mcp.ps1](../../install/install-craft-mcp.ps1) — installer idempotente multi-client
- [artcraft-mcp-proxy.py](../../tools/artcraft-mcp-proxy.py) — shim di conformità MCP per l'MCP generativo
- [report-mcp-tools.py](../../tools/report-mcp-tools.py) — genera l'inventario reale dei tool di tutti i server
- [mcp-tools-report.md](../../reports/mcp-tools-report.md) — **report dei tool disponibili** (13/13 server, 764 tool)
- [craft-bridge.md](./craft-bridge.md) — **modalità bridged delle Crafting Apps** (matrice, control-token, prove)
- [craft-bridge-mcp.py](../../tools/craft-bridge-mcp.py) — shim stdio bridged/headless
- [craft-bridge-config.py](../../tools/craft-bridge-config.py) — installer idempotente delle entry bridged (installa shim **e** strumento di identità accanto a lui, e riallinea i file quando il repo cambia)
- [craft-bridge-recon.py](../../tools/craft-bridge-recon.py) · [craft-bridge-probe.py](../../tools/craft-bridge-probe.py) · [craft-bridge-pilot.py](../../tools/craft-bridge-pilot.py) — recon, sonda MCP, pilota dell'app
- [craft-bridge-sweep.py](../../tools/craft-bridge-sweep.py) — passa in rassegna le app e misura ogni entry headless **e** bridged ([report](../../reports/craft-bridge-sweep.json))
- [craft-bridge-verify.py](../../tools/craft-bridge-verify.py) — verifica le entry MCP col comando reale scritto in config
- [craft-bridge-tests.py](../../tools/craft-bridge-tests.py) — **le sei iniezioni di guasto, eseguibili**: rompe qualcosa di proposito e pretende il verdetto giusto da doctor, ident e launcher ([report](../../reports/craft-bridge-tests.md) con il confronto sull'esecuzione precedente)
- [craft-bridge-doctor.py](../../tools/craft-bridge-doctor.py) — **un verdetto solo su tutto l'assieme** (repo, shim installato, entry di config, eseguibili, credenziali, build che gira sulle porte), con le azioni da fare
- [craft-bridge-launch.py](../../tools/craft-bridge-launch.py) — avvia una o più app col canale di controllo già attivo sulle porte attese
- [craft-bridge-ident.py](../../tools/craft-bridge-ident.py) — handshake e identita': chi risponde dietro la porta di controllo (app dal catalogo dei comandi) **e quale build** vi gira (PID della porta, eseguibile, versione dichiarata dall'app; impronta in `~/.craft-bridge/builds.json` con `--record`)

