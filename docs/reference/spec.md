---
type: Reference
title: "Spec del progetto"
description: "Requisiti, vincoli e criteri di accettazione del ponte tra le Crafting Apps e i client MCP."
resource: ../../docs/reference/spec.md
tags: [spec, requisiti]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:23:21Z }
status: stable
---

# ArtCraft MCP — Specifica di integrazione globale

**Riferimento:** [analisi.md](./analisi.md) · **Piano:** [piano.md](./piano.md)
**Data:** 13 ottobre 2026 · **Stato:** proposta, in attesa di conferma

---

## 1. Obiettivo

Rendere il server **`artcraft-mcp` (61 tool)** disponibile in modo **stabile, idempotente e sicuro** a tutti i client MCP presenti sulla macchina, con **una sola definizione di verità** (path binario + credenziali) replicata nei singoli file di config.

Ambito A: **MCP della piattaforma generativa ArtCraft**. Ambito B: i **12 MCP delle Crafting Apps** (§8), che sono un ecosistema distinto con 12 server propri. Entrambi sono stati **implementati**.

---

## 2. Requisiti

### 2.1 Funzionali

| ID | Requisito |
|---|---|
| FR1 | Il binario risiede in un **path stabile per-utente**, non in `Downloads` |
| FR2 | Le **credenziali** sono risolte da un'unica fonte esterna al pacchetto |
| FR3 | La entry `artcraft` è registrata, **idempotentemente**, in ogni client rilevato |
| FR4 | Ogni scrittura di config crea un **backup** preservabile e ripristinabile |
| FR5 | Lo script è **ri-eseguibile** senza duplicare o corrompere le entry esistenti |
| FR6 | Viene prodotta una **skill globale** `artcraft-mcp` per i client che supportano le skill |
| FR7 | È presente una **verifica end-to-end** (handshake + `tools/list` + una chiamata account) |
| FR8 | Codex è gestito in modalità **"documentato, non applicato"** finché non installato |

### 2.2 Non funzionali

| ID | Requisito |
|---|---|
| NFR1 | **Nessun privilegio amministrativo** (installazione per-utente) |
| NFR2 | **Nessun segreto** nei file tracciati da git né negli output/log |
| NFR3 | **Nessuna** modifica distruttiva: mai cancellare server MCP preesistenti |
| NFR4 | Script **fail-safe**: in caso di errore non lascia config parziali |
| NFR5 | Determinismo dei path: nessuna dipendenza da `HOME`/`USERPROFILE` a mano |
| NFR6 | Tracciabilità: log di cosa è stato scritto e dove |

---

## 3. Architettura target

```
                 ┌───────────────────────────────────────────┐
                 │  SORGENTE UNICA DI VERITÀ                  │
                 │  · BIN : %LOCALAPPDATA%\Programs\           │
                 │          artcraft-mcp\artcraft-mcp.exe      │
                 │  · CRED: ~\Artcraft\credentials\*.txt       │
                 │          oppure env ARTCRAFT_*              │
                 └───────────────────┬───────────────────────┘
                                     │  installer idempotente
        ┌───────────────┬────────────┼────────────┬────────────────┐
        ▼               ▼            ▼            ▼                ▼
   Freebuff        Claude Code   Claude Desktop   dsh          Antigravity
 ~\.agents\      ~\.claude.json  %APPDATA%\Claude  cordis.patch  ~\.gemini\config\
  mcp.json        (mcpServers)   \claude_desktop_  .yml          mcp_config.json
                                  config.json
        └───────────────┴────────────┴────────────┴────────────────┘
                                     │
                              Codex: solo doc
                         (~\.codex\config.toml)
```

### 3.1 Livelli di scope

| Scope | Dove | Uso consigliato |
|---|---|---|
| **Globale/utente** | i file di §5 | default: disponibile in ogni progetto |
| **Progetto** | `<progetto>\.agents\mcp.json`, `<progetto>\.mcp.json` | override per singolo repo |

Scelta consigliata: **globale/utente**, per soddisfare la richiesta "usarlo con tutti i framework".

---

## 4. Contratti

### 4.1 Entry canonica (forma generica `mcpServers`)

```json
{
  "mcpServers": {
    "artcraft": {
      "type": "stdio",
      "command": "C:\\Users\\auresystem\\AppData\\Local\\Programs\\artcraft-mcp\\artcraft-mcp.exe",
      "args": [],
      "env": {}
    }
  }
}
```

Note di compatibilità:
- **Freebuff** legge `~\.agents\mcp.json` e supporta `type: "stdio"` + `command`/`args`/`env`.
- **Claude Code / Claude Desktop / Antigravity** usano `command`/`args`/`env` nella medesima forma.
- Chiavi extra come `description`/`enabled` (generate da `setup_mcp.py`) sono **innocue** ma non necessarie.

### 4.2 Credenziali — ordine di risoluzione del server

1. `ARTCRAFT_MCP_PRIVATE_SESSION_TOKEN`
2. `ARTCRAFT_API_KEY`
3. `ARTCRAFT_SESSION` + `ARTCRAFT_AVT`
4. `~\Artcraft\credentials\artcraft_session.txt` + `artcraft_avt.txt`
5. cookie store dell'app desktop `%LOCALAPPDATA%\ai.artcraft.app\.cookies`

**Scelta consigliata:** metodo **4** (file di credenziali) — disaccoppia l'MCP dal client e non mette segreti nei JSON di config.

### 4.3 Config Codex (solo documentazione)

```toml
# %USERPROFILE%\.codex\config.toml
[mcp_servers.artcraft]
command = "C:\\Users\\auresystem\\AppData\\Local\\Programs\\artcraft-mcp\\artcraft-mcp.exe"
args = []
```

### 4.4 dsh (DeepSeek Harness)

dsh non usa un `mcp.json` ma **patch `cordis.patch.yml`** (livello home `%APPDATA%\dsh-desktop\harness\cordis.patch.yml` e livello profilo) con l'id plugin `dsh-mcp-client` e `config.serverName/command/args/env`.

Strategia consigliata: **non editare a mano**; aggiungere il server dalla **UI di dsh** e, se serve portabilità, usare il plugin `dsh-config-manager` (import/backup).

---

## 5. Mappa client → azione

| Client | File | Azione | Note |
|---|---|---|---|
| Freebuff | `~\.agents\mcp.json` | crea/merge chiave `artcraft` | attualmente assente → creare da zero |
| Claude Code | `~\.claude.json` → `mcpServers` | merge preservando `blender/drawio/railway` | preferibile `claude mcp add -s user artcraft -- <bin>` |
| Claude Desktop | `%APPDATA%\Claude\claude_desktop_config.json` | merge in `mcpServers` (vuoto) | — |
| Antigravity | `~\.gemini\config\mcp_config.json` | merge preservando `notebooklm` | opzionale |
| dsh | `cordis.patch.yml` via UI | aggiunta da UI | non automatizzare |
| Codex | `~\.codex\config.toml` | **solo doc** | non installato |

---

## 6. Strategia skill

**Decisione di progetto: UNA sola skill globale** per l'ambito A.

- Fonte: `skills/artcraft-mcp/` del pacchetto (`SKILL.md` + `references/`).
- Destinazioni:
  - Freebuff: `~\.agents\skills\artcraft-mcp\`
  - Claude Code: `~\.claude\skills\artcraft-mcp\`
  - (altri client con supporto skill: stessa struttura `<root>\skills\artcraft-mcp\SKILL.md`)
- ⚠️ `~\.agents\skills` è un **symlink** a `~\repos\craft-skills-flow\skills`: va deciso se scrivere là dentro (versionato) o usare una cartella reale.
- La skill è **opzionale ma raccomandata**: abilita le buone pratiche di scelta modello, aspect ratio e **stima costi obbligatoria** prima di ogni generazione.
- **Non** creare una skill per ogni Crafting App se le app non sono installate.

---

## 7. Criteri di accettazione

| ID | Criterio | Verifica |
|---|---|---|
| AC1 | `artcraft-mcp.exe` esiste nel path stabile | `Test-Path` |
| AC2 | Handshake MCP riuscito | `initialize` → `protocol_version: 2025-03-26` |
| AC3 | 61 tool esposti | `tools/list` → count = 61 |
| AC4 | Auth funzionante | `artcraft_get_credits` restituisce un saldo |
| AC5 | Entry presente in ogni client rilevato | rilettura dei JSON |
| AC6 | Config preesistenti intatte | `blender/drawio/railway`, `notebooklm` ancora presenti |
| AC7 | Backup creati | file `.bak.<timestamp>` accanto ai config |
| AC8 | Re-run idempotente | seconda esecuzione → nessuna differenza |
| AC9 | Skill leggibile dai client | il client elenca `artcraft-mcp` tra le skill |
| AC10 | Nessun segreto in git | `git status` / grep sui file scritti |

---

## 8. Ambito B (implementato) — Crafting Apps

Le 12 Crafting Apps sono installate in `C:\Program Files\<App>\`, ognuna con `<app>-cli.exe` che espone il sottocomando `mcp`. La spec per l'ambito B è quindi:

```json
{
  "mcpServers": {
    "photocraft": {
      "type": "stdio",
      "command": "C:\\Program Files\\PhotoCraft\\photocraft-cli.exe",
      "args": ["mcp"]
    }
  }
}
```

Regole applicate:
- **una entry per app**, con `args: ["mcp"]` e **path assoluto** (le CLI non sono nel PATH);
- naming: `cadcraft`, `deckcraft`, `designcraft`, `effectcraft`, `filmcraft`, `gridcraft`, `lightcraft`, `pdfcraft`, `photocraft`, `soundcraft`, `vectorcraft`, `wordcraft`;
- scoperta automatica: la entry viene creata **solo se** `<App>\<app>-cli.exe` esiste;
- nessuna credenziale richiesta (motore locale).

Opzioni avanzate non attivate (da valutare per uso reale):
- **sandbox filesystem**: `--automation-read-root` / `--automation-write-root` restringono i file accessibili dall'agente;
- **bridged mode**: `mcp --bridge 127.0.0.1:<porta>` verso l'app desktop avviata con `<app> --control <porta>`, con `--control-token` per l'autorizzazione;
- **skill per app**: da creare solo per le app effettivamente usate.

### 8.1 Impatto sul contesto

12 server MCP sommati all'MCP generativo aumentano sensibilmente il numero di tool esposti a **ogni** client. Per questo l'installer espone le opzioni `-SkipSuite` e `-SkipGenerative`, e le entry possono essere rimosse selettivamente.

---

### 8.2 Shim di conformità MCP (Ambito A)

L'MCP generativo `artcraft-mcp.exe` non è conforme alla specifica (campi snake_case). Requisiti dello shim:

| ID | Requisito | Stato |
|---|---|---|
| SH1 | Trasparente: il client parla MCP standard, il server resta invariato | ✅ |
| SH2 | Riscrivere **solo** i campi di protocollo noti, mai gli schemi dei tool | ✅ |
| SH3 | Idempotente (se il campo è già camelCase non tocca nulla) | ✅ |
| SH4 | I/O UTF-8 **binario**, nessuna traduzione di newline (framing line-delimited) | ✅ |
| SH5 | Messaggi non-JSON inoltrati verbatim, mai scartati | ✅ |
| SH6 | Nessun deadlock: pump stdout e stderr su thread separati | ✅ |
| SH7 | Propagare la chiusura di stdin e il codice di uscita del figlio | ✅ |
| SH8 | Percorso del binario sovrascrivibile via `ARTCRAFT_MCP_BIN` | ✅ |

Campi riscritti: `protocol_version`→`protocolVersion`, `server_info`→`serverInfo`, `list_changed`→`listChanged`, `input_schema`→`inputSchema`, `output_schema`→`outputSchema`, `is_error`→`isError`.

Registrazione risultante:

```json
"artcraft": {
  "type": "stdio",
  "command": "C:\\Users\\auresystem\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
  "args": ["C:\\Users\\auresystem\\AppData\\Local\\Programs\\artcraft-mcp\\artcraft-mcp-proxy.py"]
}
```

---

## 9. Fuori scope

- Modifica/compilazione del sorgente Rust dell'MCP.
- Pubblicazione di pacchetti o upload su registry.
- Acquisti/crediti (i tool di billing restano esposti ma non automatizzati).
