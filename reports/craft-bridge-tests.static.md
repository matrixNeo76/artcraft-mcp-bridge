# Report della suite di guasti

**Generato:** 14/10/2026 10:23 · **host:** wkai01 · **Python:** 3.12.10
**Modi:** solo statici · **durata:** 80.8s
**Strumenti:** `mcp` `f52a99d7261f` · `ident` `8df181789548` · `doctor` `41414d417fbf` · `config` `236ff781b8ee` · `feed` `c65b3ac8ee1a` · `tests` `054e4b36098a` · `ui` `ed3cab22827d` · `connect` `b8fccd17a9d0` · `report` `e2d5cad43626`

## Esito

**23 passati, 0 falliti, 1 saltati** → tutto in ordine

| Caso | Tipo | Stato | Secondi | Dettaglio |
|---|---|---|---|---|
| stato pulito | static | ok | 6.3 | doctor: nessuna azione |
| shim installato stantio | static | ok | 12.6 | accusato e riparato dall'azione indicata |
| entry di config sbagliata | static | ok | 6.4 | doctor e installer concordano: 1 entry da aggiornare |
| percorso inesistente | static | ok | 6.1 | FIX percorsi: cadcraft.command |
| eseguibile mancante | unit | ok | 0.2 | lightcraft app, lightcraft cli |
| posizione dell'app dal sistema | unit | ok | 0.0 | registro prima, tabella poi, e l'assenza si dichiara; l'avvio prende l'eseguibile registrato |
| app registrate dal sistema | static | ok | 0.0 | 12/12 percorsi dal registro App Paths, hive utente e macchina, tabella confermata, avvio sull'eseguibile registrato |
| confronto col feed del launcher | unit | ok | 0.0 | 9 righe: dietro, pari, assente, estraneo e i tre casi di byte |
| byte pubblicati contro installati | unit | ok | 0.1 | uguali ok, diversi FIX, archivio manomesso FIX, assente nota, cli_zip preferito |
| feed assente non e' un guasto | unit | ok | 0.2 | doctor: nota con la ragione, non un FIX |
| feed illeggibile o estraneo | static | ok | 4.1 | assente 3, illeggibile 3, estraneo 0 (nessun guasto inventato) |
| cancello sulle regressioni | unit | ok | 0.0 | sei peggioramenti accusati, quattro casi innocenti, due confronti rifiutati e i quattro codici d'uscita |
| porta chiusa | live | ok | 6.8 | ident unreachable, shim headless (porta 7979) |
| argomenti della chiamata | unit | ok | 0.0 | numeri, stringhe (virgolettate), liste, null e booleani come li vuole la CLI |
| sessione del traduttore | unit | ok | 3.4 | 15 tool, parametri tipizzati, immagine, isError su guasto, -32602 sull'ignoto, modo bridged dichiarato, finestra sparita a meta' sessione diagnosticata |
| senza finestra il traduttore ripiega | unit | ok | 0.6 | nessuna finestra: il server headless del fornitore passa attraverso, dichiarato |
| finestra PdfCraft dal vivo | static | saltato | 0.8 | finestra chiusa (nessuno in ascolto sulla porta 4497 (file stantio?)): l'entry va headless |
| flag di aggancio, verificato | unit | ok | 0.3 | confermato, non confermato, flag diverso, assenza confermata e help illeggibile: sei verdetti, come li vuole l'help della CLI |
| doctor: flag non confermato | unit | ok | 10.6 | tabella non confermata -> FIX con l'azione; confermata dal canale -> ok; CLI assente -> nota |
| flag di aggancio dal vivo | static | ok | 6.5 | 12/12 CLI documentano il flag della tabella, e la diagnosi lo ripete |
| client MCP multipli | static | ok | 1.5 | JSON, VS Code, TOML e YAML: scritti, idempotenti, restore pulito |
| report di stato | static | ok | 0.6 | json 13 entry dalla config indicata (shim e traduttore), html 21343 byte |
| report --serve | static | ok | 1.4 | servito su 127.0.0.1:5981: pagina 200 e JSON con lo schema |
| client MCP nella diagnosi | static | ok | 12.4 | accusa cursor 0/13 (1) e tace con le 13 (0) |

## Confronto con l'esecuzione precedente

Rispetto al report del 14/10/2026 10:04:

- `craft-bridge-tests.py`: 96aed04d9920 -> 054e4b36098a
- `craft-bridge-report.py`: 0957d425a9f8 -> e2d5cad43626

durata: 80.8s (precedente 80.7s, +0.1s)


## Regressioni (cancello)

Nessuna regressione: la baseline regge.
