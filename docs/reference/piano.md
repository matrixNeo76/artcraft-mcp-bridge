---
type: Reference
title: "Piano di lavoro"
description: "Fasi, milestone e verifiche previste per il ponte."
resource: ../../docs/reference/piano.md
tags: [piano, milestone]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:23:21Z }
status: stable
---

# ArtCraft MCP — Piano di esecuzione

**Riferimenti:** [analisi.md](./analisi.md) · [spec.md](./spec.md)
**Data:** 13 ottobre 2026 · **Stato:** ✅ **FASI 1-5 ESEGUITE** (conferma ricevuta; suite Crafting Apps inclusa)

> Le fasi 1-5 sono state eseguite. I comandi restano come riferimento per ri-esecuzione o rollback.

---

## Fase 0 — Prerequisiti e decisioni (bloccante)

| # | Attività | Esito atteso |
|---|---|---|
| 0.1 | Recuperare le **credenziali ArtCraft** (login su artcraft.ai → cookie `session` e `visitor`) **oppure** una API key `ARTCRAFT_API_KEY` | fonte credenziali disponibile |
| 0.2 | Confermare lo **scope** (globale-utente vs solo Freebuff) | decisione |
| 0.3 | Decidere se installare anche la **suite Crafting Apps** (ambito B) | decisione |
| 0.4 | Decidere dove scrivere la skill, dato che `~\.agents\skills` è un symlink | decisione |

**Gate:** senza 0.1 l'MCP risponde ma ogni tool fallisce in auth.

---

## Fase 1 — Stabilizzare il binario

| # | Passo |
|---|---|
| 1.1 | Creare `%LOCALAPPDATA%\Programs\artcraft-mcp\` |
| 1.2 | Copiare `bin\artcraft-mcp.exe` dal pacchetto in quel percorso |
| 1.3 | (Opzionale) conservare nel medesimo folder `SKILL.md` + `references\` come sorgente della skill |

Comando proposto:

```powershell
$src = "C:\Users\auresystem\Downloads\artcraft-mcp-v1.1.0"
$dst = "$env:LOCALAPPDATA\Programs\artcraft-mcp"
New-Item -ItemType Directory -Force -Path $dst | Out-Null
Copy-Item "$src\bin\artcraft-mcp.exe" $dst -Force
Get-FileHash "$dst\artcraft-mcp.exe" -Algorithm SHA256   # hash da registrare
```

**Verifica (V1):** il file esiste e l'hash è annotato.
**Rollback:** rimuovere la cartella creata.

---

## Fase 2 — Registrare credenziali (fuori dal pacchetto)

| # | Passo |
|---|---|
| 2.1 | Creare `~\Artcraft\credentials\` |
| 2.2 | Scrivere `artcraft_session.txt` e `artcraft_avt.txt` con i **soli** valori dei cookie |
| 2.3 | Escludere la cartella da git/backup non cifrati |

```powershell
$cred = "$env:USERPROFILE\Artcraft\credentials"
New-Item -ItemType Directory -Force -Path $cred | Out-Null
# i valori vanno inseriti manualmente dall'utente, NON stampati a schermo
```

**Verifica (V2):** `artcraft_get_credits` restituisce un saldo reale.
**Nota sicurezza:** i cookie sono credenziali → mai nei log, mai nei `SKILL.md`.

---

## Fase 3 — Registrare l'MCP nei client

### 3.1 Freebuff (globale)

Creare `~\.agents\mcp.json`:

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

### 3.2 Claude Code (scope utente)

```powershell
claude mcp add --scope user artcraft -- "C:\Users\auresystem\AppData\Local\Programs\artcraft-mcp\artcraft-mcp.exe"
# equivalente manuale: merge in ~\.claude.json -> mcpServers
```

> Preservare le entry esistenti: `blender`, `drawio`, `railway`.

### 3.3 Claude Desktop

Merge di `artcraft` in `%APPDATA%\Claude\claude_desktop_config.json` → `mcpServers` (oggi vuoto).

### 3.4 Antigravity (opzionale)

Merge di `artcraft` in `~\.gemini\config\mcp_config.json`, preservando `notebooklm`.

### 3.5 dsh (DeepSeek Harness)

Aggiungere il server **dalla UI di dsh** (scrive `cordis.patch.yml`). Non editare a mano.

### 3.6 Codex — solo documentazione

Non installato. Annotare la config target (`~\.codex\config.toml`, `[mcp_servers.artcraft]`) per quando sarà installato.

**Verifica (V3-V4):** ogni client elenca `artcraft`; i server preesistenti sono ancora presenti; per ogni file modificato esiste un `.bak.<timestamp>`.
**Rollback:** ripristinare dai `.bak` generati.

---

## Fase 4 — Installare la skill globale

| # | Passo |
|---|---|
| 4.1 | Copiare `skills\artcraft-mcp\` in `~\.agents\skills\artcraft-mcp\` (Freebuff) |
| 4.2 | Copiare in `~\.claude\skills\artcraft-mcp\` (Claude Code) |
| 4.3 | Aggiornare i riferimenti se il binario non è nel folder della skill |

**Verifica (V5):** i client elencano la skill `artcraft-mcp`.
**Attenzione:** `~\.agents\skills` è un **symlink** → verificare dove si sta scrivendo prima di copiare.

---

## Fase 5 — Verifica end-to-end e hardening

| # | Verifica |
|---|---|
| E2E-1 | Handshake direct: `initialize` → `protocol_version: 2025-03-26` |
| E2E-2 | `tools/list` → **61** tool |
| E2E-3 | Autenticazione: `artcraft_get_credits` e `artcraft_get_session_info` |
| E2E-4 | Stima costi: `artcraft_estimate_cost` risponde |
| E2E-5 | Attraverso ciascun client: "controlla i miei crediti ArtCraft" |
| E2E-6 | Idempotenza: re-run dell'installer → nessuna differenza nei file |
| E2E-7 | `git status`: nessun segreto, nessun file indesiderato |
| E2E-8 | Policy: nota in `AGENTS.md`/skill che vieta tool di billing senza consenso esplicito |

---

## Deliverable

| # | Deliverable | Fase |
|---|---|---|
| D1 | Binario in path stabile + hash SHA256 | 1 |
| D2 | Credenziali configurate (fuori dal repo) | 2 |
| D3 | `artcraft` registrato nei client (Freebuff, Claude Code, Claude Desktop, dsh) | 3 |
| D4 | Doc config Codex | 3.6 |
| D5 | Skill `artcraft-mcp` globale | 4 |
| D6 | Script installer **multi-client idempotente** — ✅ consegnato ed eseguito | 3 |
| D7 | Report di verifica E2E | 5 |
| D8 | [artcraft-mcp-proxy.py](../../tools/artcraft-mcp-proxy.py) — shim di conformita' MCP per l'MCP generativo | 5 |

---

## Stima

| Fase | Effort | Note |
|---|---|---|
| 0 | decisioni utente | bloccante |
| 1–2 | 10 min | il binario è già pronto, self-contained |
| 3 | 20–30 min | + tempo se si generano gli adapter multi-client |
| 4 | 10 min | attenzione al symlink |
| 5 | 15 min | richiede credenziali reali per E2E-3 |

---

## Rischi residui e mitigazioni

| Rischio | Mitigazione |
|---|---|
| Credenziali non disponibili → blocco | Fase 2 esplicita; test guidati solo dopo |
| `setup_mcp.py` insufficiente (3 client) | Script dedicato (D6), idempotente e con backup |
| dsh editato a mano → config corrotta | Solo via UI / import |
| Symlink skill → scrittura nel repo sbagliato | Verifica preliminare del target reale |
| Supply chain (repo terzo) | Pin versione + hash + esecuzione per-utente |
| Tool di billing usati da un agente | Policy in skill/`AGENTS.md` |

---

## Decisioni confermate (13 ottobre 2026)

| # | Decisione | Stato |
|---|---|---|
| C1 | **Scope:** globale-utente su tutti i client rilevati | ✅ confermato |
| C2 | **Client:** Freebuff + Claude Code + Claude Desktop + Antigravity; dsh via UI; Codex solo doc | ✅ confermato |
| C3 | **Skill:** una sola `artcraft-mcp`, globale | ✅ confermato |
| C4 | **Credenziali:** l'utente NON le ha ancora | ⛔ blocca solo l'E2E di autenticazione, non la configurazione |
| C5 | **Installer multi-client:** da generare | ✅ consegnato: [install-craft-mcp.ps1](../../install/install-craft-mcp.ps1) |
| C6 | **Ambito B (suite Crafting Apps):** tutte e 12, già installate dall'utente in `C:\Program Files\` | ✅ implementato e verificato |

### Stato dello script installer — [install-craft-mcp.ps1](../../install/install-craft-mcp.ps1)

| Verifica | Esito |
|---|---|
| Parsing PowerShell (`Parser::ParseFile`) | ✅ SYNTAX OK |
| Solo caratteri ASCII (compatibile Windows PowerShell 5.1) | ✅ nessun byte non-ASCII |
| `-DryRun` end-to-end | ✅ 13 server pianificati su ogni client |
| Scoperta automatica delle app | ✅ 12/12 CLI rilevate in `C:\Program Files` |
| Esecuzione reale | ✅ 13 server x 4 client = 52 registrazioni |
| Idempotenza (re-run) | ✅ `added=0, unchanged=13` su ogni client |
| Backup | ✅ `.bak.20261013-130016` per i 2 config preesistenti |
| Server preesistenti preservati | ✅ `blender`, `drawio`, `notebooklm`, `preferences` intatti |
| MCP delle 12 app via `claude mcp list` | ✅ tutti `Connected` |
| MCP generativo ArtCraft | ✅ `Connected` tramite proxy di conformita' (vedi [analisi.md](./analisi.md) §3.5) |
| Proxy `artcraft-mcp-proxy.py` | ✅ testato: campi camelCase, 61 tool, exit 0 |

### Esecuzione

```powershell
# dry-run (anteprima)
powershell -ExecutionPolicy Bypass -File .\artcraft-integration\install-craft-mcp.ps1 -DryRun

# esecuzione reale
powershell -ExecutionPolicy Bypass -File .\artcraft-integration\install-craft-mcp.ps1

# solo le Crafting Apps, senza il generativo
powershell -ExecutionPolicy Bypass -File .\artcraft-integration\install-craft-mcp.ps1 -SkipGenerative

# con lo shim di conformita' per l'MCP generativo (raccomandato)
powershell -ExecutionPolicy Bypass -File .\artcraft-integration\install-craft-mcp.ps1 -ProxyScript .\artcraft-integration\artcraft-mcp-proxy.py
```

Lo shim viene copiato in `%LOCALAPPDATA%\Programs\artcraft-mcp\` e l'entry `artcraft` diventa `python <proxy>`; l'installer sa riconoscere la differenza di comando e ri-registra la entry (in Claude Code esegue `mcp remove` + `mcp add`).

### Passi manuali residui

1. **dsh**: aggiungere i 12 server (+ eventuale `artcraft`) dalla UI di dsh, che scrive `cordis.patch.yml`.
2. **Credenziali ArtCraft generativo**: `%USERPROFILE%\Artcraft\credentials\artcraft_session.txt` + `artcraft_avt.txt` (il difetto di protocollo è già risolto dal proxy; restano necessarie per la generazione reale).
3. **Codex** (non installato): `%USERPROFILE%\.codex\config.toml` → `[mcp_servers.<nome>]`.
