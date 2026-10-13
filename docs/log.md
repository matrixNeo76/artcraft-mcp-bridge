# Registro aggiornamenti

## 2026-10-13
* **Creazione**: bundle OKF v0.2 della documentazione (architettura, strumenti, operazioni, difetti) e file di radice README/AGENTS/ROADMAP.
* **Verifica**: il bundle e' conforme a OKF v0.2 secondo `uvx okfgen validate docs --strict` (28 concetti, 0 errori) e si vede come grafo interattivo in `reports/okf-graph.html` (28 nodi, 109 relazioni).
* **Correzione**: 28 frontmatter avevano `title`/`description` non quotati con `: ` dentro, YAML non valido per un parser rigoroso; ora sono quotati.
* **Riorganizzazione**: il progetto passa dalla cartella piatta a `tools/`, `install/`, `reports/`, `docs/`; i documenti lunghi diventano nodi `type: Reference` in `docs/reference/`.
* **Aggiunta**: gli artefatti generati vivono in `reports/` ed e' il default degli strumenti, non la cartella di invocazione.
* **Aggiunta**: la suite dei guasti scrive `reports/craft-bridge-tests.json` e `.md` con il confronto sull'esecuzione precedente (casi cambiati, comparsi, spariti, impronte, durata).
* **Correzione**: con una credenziale rifiutata `craft-bridge-ident.py` moriva con un traceback e non dava verdetto; ora un errore di rete non solleva e il verdetto arriva lo stesso.
* **Correzione**: `craft-bridge-config.py` riallinea anche i file installati, non solo le entry, quando il sorgente cambia.
* **Misura**: 11 app su 12 guidabili e verificate dal vivo; 13/13 entry della config eseguite col comando reale; suite di guasti 10/10, due giri di fila identici.
* **Installazione**: 13 server MCP in `~/.agents/mcp.json`, con il canale di controllo sulle porte attese.
* **Aggiunta**: modalita' `--ci` della suite (salta i casi d'ambiente motivandoli) e workflow di integrazione continua in `.github/workflows/checks.yml`, con badge nel README.
* **Correzione**: il primo giro della CI ha trovato un terzo difetto del workflow: `uvx` non esiste sui runner GitHub. Ora lo porta `astral-sh/setup-uv` e la versione del validatore e' fissata (`okfgen==0.1.3`).
* **Correzione**: due difetti trovati eseguendo gli step del workflow in locale: in PowerShell `"$slug: ..."` viene letto come variabile con drive (`InvalidVariableReferenceWithDrive`, serve `"${slug}: ..."`) e il conteggio delle proprieta' di un oggetto JSON richiede `Measure-Object`, non `.Count`.
