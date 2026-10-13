# Registro aggiornamenti

## 2026-10-13
* **Aggiunta**: `craft-bridge-feed.py` legge il feed del launcher di ArtCraft (repo di provenienza, ultima release, pacchetti con il loro sha256) e lo confronta con la build installata: la versione di un eseguibile dice cosa dichiara di essere, non se e' la release pubblicata. `--downloads` confronta i byte dei pacchetti gia' scaricati con lo sha256 pubblicato, l'unico caso che accusa; un launcher assente resta una lacuna dichiarata.
* **Aggiunta**: il `doctor` ha l'ottavo controllo, `pubblicato`: un'app indietro e' una `nota` con l'azione "aggiorna dal launcher" (il ponte funziona lo stesso), un feed assente non cambia il verdetto, e la lettura delle versioni degli eseguibili e' condivisa fra i controlli (resta sotto il secondo).
* **Misura**: 11 app su 11 allineate alla release pubblicata; 2 voci del feed fuori dal ponte (`pdfcraft` 0.7.1, `artcraft-launcher` 0.3.2); cartella dei download vuota, quindi nessun byte da confrontare.
* **Aggiunta**: tre casi nella suite (confronto puro con feed finto, feed assente = nota, feed assente/illeggibile = uscita 3), ora 13 casi totali e 9 nella modalita' `--static`.
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
* **Licenza**: il progetto passa a MIT (`LICENSE`, copyright 2026 matrixNeo76); la sezione "Licenza" del README la cita invece di rimandare a una decisione aperta, e `AGENTS.md` la elenca fra i file di radice.
* **Correzione**: il README citava ancora i conteggi di prima del nodo `operations/ci.md` (28 concetti, 28 nodi): ora sono quelli misurati, 29 concetti e 29 nodi con 114 relazioni.
* **Correzione**: due difetti trovati eseguendo gli step del workflow in locale: in PowerShell `"$slug: ..."` viene letto come variabile con drive (`InvalidVariableReferenceWithDrive`, serve `"${slug}: ..."`) e il conteggio delle proprieta' di un oggetto JSON richiede `Measure-Object`, non `.Count`.
