# AGENTS.md — come lavorare in questo repo

Istruzioni per un agente che modifica questo progetto. Le regole valgono sempre, anche
quando sembrano rallentare il lavoro: nascono da difetti veri trovati misurando.

## Cos'è questo progetto

Il ponte fra le Crafting Apps e i client MCP: shim stdio, canale di controllo, diagnosi
e prove. Idea centrale: **niente affermazioni senza la misura** che le sostiene. Ogni
strumento dichiara cosa ha provato, e quando non lo sa lo dice.

## Dove sta cosa

| Percorso | Contenuto |
|---|---|
| `tools/` | gli strumenti Python (14 file). Si eseguono da qui, funzionano da qualunque cartella |
| `install/` | `install-craft-mcp.ps1`, registrazione multi-client dell'MCP generativo |
| `reports/` | artefatti generati; è il default di output degli strumenti, non la cartella da cui li invochi |
| `docs/` | documentazione in **OKF v0.2** (bundle: `docs/index.md`) |
| `README.md`, `ROADMAP.md` | panoramica e prossimi passi |
| `LICENSE` | licenza MIT del progetto: non si modifica, e un file nuovo che entra nel repo ne eredita i termini |

## Regole che non si violano

1. **La config vera dei connettori non è una cavia.** `~/.agents/mcp.json` la scrive
   solo `craft-bridge-config.py --apply` (con backup). I test la riguardano su una
   copia con `--config`.
2. **Le copie installate non si toccano a mano.** `%LOCALAPPDATA%\Programs\craft-bridge`
   si aggiorna con `--apply`. Se modifichi `craft-bridge-mcp.py` o
   `craft-bridge-ident.py` nel repo, esegui `--apply`, altrimenti `doctor` segnala — a
   ragione — la deriva fra sorgente e installato.
3. **Il valore del token non si stampa mai**, non entra in chat, nei log, nei report o
   nel repo. Si legge solo l'esito dell'`auth`.
4. **Nessun processo ucciso se non l'hai avviato tu.** Se una porta è occupata, salta
   il caso (SKIP), non terminare processi altrui.
5. **Le app si avviano solo su porte libere**, dentro `try/finally`, e i temporanei si
   cancellano alla fine.

## Prima di dire "fatto"

```bash
python -m py_compile tools/*.py              # sintassi di tutti gli strumenti
python tools/craft-bridge-doctor.py          # un verdetto sull'assieme (exit 0 = niente da fare)
python tools/craft-bridge-tests.py --static  # ~10 s, i casi che non avviano app
python tools/craft-bridge-feed.py            # l'installato contro il pubblicato (se c'e' il launcher)
python tools/craft-bridge-tests.py           # ~44 s, compresi i casi con app vere
```

In CI gira `python tools/craft-bridge-tests.py --static --ci`: `--ci` salta i casi che
richiedono il ponte **spiegando perché**, e non va mai usata per far passare una macchina
vera (lì i salti non ci sono, e un guasto vero resta un FAIL). Gli step del workflow si
possono eseguire in locale estraendoli da `.github/workflows/checks.yml` ed eseguendoli con
`powershell -NoProfile -ExecutionPolicy Bypass -File step.ps1`.

Se hai toccato shim, ident o doctor, la suite completa è obbligatoria: è lei che
dichiara se il comportamento è cambiato, e confronta da sola con l'esecuzione
precedente (`reports/craft-bridge-tests.md`, sezione *Confronto*).

## Convenzioni

- **Lingua**: prosa, commenti e messaggi in italiano; apostrofi ASCII (`l'app`), non
  tipografici. I nomi di codice restano in inglese.
- **Un solo verdetto per strumento**: esiti distinti per significati distinti
  (`0` ok, `1` problema, `2` errore d'uso, `3` config illeggibile) e ognuno dichiarato
  nel docstring e nel messaggio finale.
- **Una sola fonte per i dati condivisi**: la tabella delle app sta nello shim
  (`--dump-apps`) e la leggono tutti; le entry attese le produce
  `craft-bridge-config.py` e le consuma anche `doctor`. Non duplicare tabelle.
- **Quando scopri un limite, scrivilo.** Le sezioni "Limiti" sono parte del risultato,
  non un'ammissione di colpa.

## Documentazione

La documentazione è un bundle OKF v0.2: un concetto per file `.md` sotto `docs/`, con
frontmatter YAML (solo `type` è obbligatorio; qui si usano anche `title`, `description`,
`resource`, `tags`, `generated`, `status`, `sources`) e **relazioni espresse come link
markdown**, con il tipo di relazione nel testo (`**usa** [...]`, `**provato da** [...]`).

Se cambi il comportamento di qualcosa, aggiorna il nodo corrispondente **e** aggiungi
una riga in [docs/log.md](docs/log.md) con la data (`YYYY-MM-DD`). `index.md` e `log.md`
sono file riservati: non sono concetti, il loro formato è diverso.

Validare e vedere il bundle:

```bash
uvx okfgen validate docs --strict                        # conformità OKF v0.2
uvx okfgen visualize docs -o reports/okf-graph.html      # grafo dei nodi e delle relazioni
```

## Insidie già pagate

- La fine di un messaggio sul canale di controllo si riconosce **parsando**, non
  cercando un a capo: le app lasciano un `\n` isolato dopo la risposta precedente.
- Un errore di rete non deve sollevare: si restituisce quello che si è letto (una
  `sendall` su connessione chiusa dall'app faceva morire `ident` senza verdetto e
  avrebbe potuto far perdere il server MCP).
- Un peer che accetta e tace **non è** un peer vivo: senza handshake il modo bridged
  diventa un headless travestito.
- Un pacchetto pubblicato **non** è un eseguibile: lo `sha256` del feed è dell'archivio (MSI, zip portabile, AppImage), e la CLI sta dentro. Per confrontarla si legge il membro in memoria, e il nome del membro dipende dal sistema (`<slug>-cli.exe` su Windows); un MSI o un .dmg non si aprono con la libreria standard, quindi per quelle app i byte restano non confrontati — e va detto, non aggirato.
- Una prova che non c'è non è una prova passata: se il file da confrontare manca, il verdetto è una nota con il comando per procurarselo, non un "ok".
- `reports/` è versionato apposta: i report sono la memoria delle esecuzioni passate.
