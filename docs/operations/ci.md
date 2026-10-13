---
type: Runbook
title: "Integrazione continua: cosa controlla ogni push"
description: "Il workflow .github/workflows/checks.yml: controlli portabili su un runner hosted, suite completa su un runner self-hosted, e cosa significa --ci."
resource: "../../.github/workflows/checks.yml"
tags: [ci, workflow, controlli, badge]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:47:19Z }
status: stable
sources:
- resource: "../../.github/workflows/checks.yml"
  title: "Il workflow"
- resource: "../../tools/craft-bridge-tests.py"
  title: "La suite che il workflow esegue"
- resource: "../../README.md"
  title: "Badge di stato"
---

# Perche' due job

La suite di questo progetto **prova una macchina**, non solo del codice: `stato pulito`
pretende che `doctor` non abbia azioni da fare, `shim installato stantio` tocca la copia
installata, gli altri casi parlano alle app. Su un runner GitHub-hosted non c'e' nulla di
tutto questo, quindi la suite intera li' non puo' che fallire - e un badge rosso per
sempre non dice niente a nessuno.

Percio' il workflow ha due job:

| Job | Dove | Cosa fa |
|---|---|---|
| `controlli` | `windows-latest` (GitHub) | tutto cio' che non dipende dalla macchina, piu' la suite con `--ci` |
| `ponte-completo` | runner **self-hosted** con le app | `doctor` e la suite intera, dove il ponte esiste davvero |

Il secondo si attiva impostando la variabile di repository `CRAFTBRIDGE_SELF_HOSTED=1`
(Settings → Secrets and variables → Actions → Variables) e registrando un runner con le
etichette `self-hosted`, `windows`, `craftbridge`. Se la variabile non c'e', il job viene
saltato e non colora il badge.

# Gli step del job hosted

| Step | Cosa verifica | Perche' |
|---|---|---|
| Sintassi | `py_compile` su tutti gli strumenti | un errore di sintassi non deve arrivare a un agente che li invoca |
| Interfacce | `--help` di ogni strumento con `argparse` | l'interfaccia esiste e risponde (i server stdio sono saltati: un `--help` li farebbe partire in attesa di stdin) |
| Tabella delle app | le 11 app e le porte documentate | la tabella e' una sola fonte: config e diagnosi leggono questa |
| Installer deterministico | due giri di `--json` identici, 11 entry | idempotenza: due esecuzioni non devono produrre piani diversi |
| Bundle OKF | `uvx --from "okfgen==0.1.3" okfgen validate docs --strict` | la documentazione resta consumabile da un altro strumento; versione fissata per non dipendere dal rilascio piu' recente |
| Suite | `craft-bridge-tests.py --static --ci` | i casi eseguibili senza ponte, con i salti motivati |
| Artefatto | `reports/craft-bridge-tests.*` | il report della run resta scaricabile, anche se la run fallisce |

# Cosa significa `--ci`

`--ci` salta i casi che richiedono il ponte **spiegando perche'** (`ambiente assente su
questo runner: config assente (...)`), invece di fallire. La regola e' stretta: cambia
cosa e' un *ambiente assente*, non cosa e' un *guasto*.

La prova di questa distinzione si fa in tre modi, tutti eseguiti prima di pubblicarla:

1. su una macchina con il ponte, `--static --ci` da' **6/6 e nessun salto**;
2. con l'ambiente puntato a una cartella vuota, da' **1 passato + 5 saltati** ed esce 0;
3. con lo shim installato manomesso (un byte in piu'), da' **FAIL** ed esce 1 anche con
   `--ci`.

# Come si provano gli step senza pubblicare

Gli step sono stati eseguiti in locale **estraendoli dal file del workflow**
(`powershell -NoProfile -ExecutionPolicy Bypass -File step.ps1`), cosi' cio' che gira in CI
e cio' che e' stato verificato sono lo stesso testo; poi la CI stessa, al primo push, ha
finito il lavoro. Le tre cose che questo ha trovato:

* in PowerShell `"$slug: ..."` viene letto come **variabile con drive**
  (`InvalidVariableReferenceWithDrive`): va scritto `"${slug}: ..."`. Lo step moriva con
  quell'errore invece di dire cosa non andava;
* il conteggio delle proprieta' di un oggetto JSON richiede `Measure-Object`, non `.Count`
  (che stampava un `1` per riga);
* **`uvx` non esiste sui runner GitHub**: serve il passo `astral-sh/setup-uv`, e la versione
  del validatore va fissata (`okfgen==0.1.3`), altrimenti un suo rilascio puo' far fallire
  un push in cui non e' cambiato niente. Questo l'ha trovato la CI stessa, al primo push.

# Relazioni

- **esegue** [craft-bridge-tests](../tools/craft-bridge-tests.md) in modalita' `--ci`
- **esegue** [craft-bridge-doctor](../tools/craft-bridge-doctor.md) nel job self-hosted
- **valida** [Report e baseline](../architecture/reports.md) come artefatto della run
- **badge in** [README](../../README.md)
- **regole di sicurezza in** [Regole di sicurezza](safety-rules.md)
