# Report della suite di guasti

**Generato:** 13/10/2026 19:53 · **host:** wkai01 · **Python:** 3.12.10
**Modi:** completo · **durata:** 72.3s
**Strumenti:** `mcp` `e63385cf6422` · `ident` `8df181789548` · `doctor` `095fb4828ac5` · `config` `1fe109470c98` · `feed` `c65b3ac8ee1a` · `tests` `e2187709e4f8` · `ui` `bed1af7f410d`

## Esito

**23 passati, 0 falliti, 0 saltati** → tutto in ordine

| Caso | Tipo | Stato | Secondi | Dettaglio |
|---|---|---|---|---|
| stato pulito | static | ok | 2.4 | doctor: nessuna azione |
| shim installato stantio | static | ok | 5.1 | accusato e riparato dall'azione indicata |
| entry di config sbagliata | static | ok | 2.7 | doctor e installer concordano: 1 entry da aggiornare |
| percorso inesistente | static | ok | 2.3 | FIX percorsi: cadcraft.command |
| eseguibile mancante | unit | ok | 0.2 | lightcraft app, lightcraft cli |
| posizione dell'app dal sistema | unit | ok | 0.0 | registro prima, tabella poi, e l'assenza si dichiara; l'avvio prende l'eseguibile registrato |
| app registrate dal sistema | static | ok | 0.0 | 11/11 percorsi dal registro App Paths, hive utente e macchina, tabella confermata, avvio sull'eseguibile registrato |
| confronto col feed del launcher | unit | ok | 0.0 | 9 righe: dietro, pari, assente, estraneo e i tre casi di byte |
| byte pubblicati contro installati | unit | ok | 0.0 | uguali ok, diversi FIX, archivio manomesso FIX, assente nota, cli_zip preferito |
| feed assente non e' un guasto | unit | ok | 0.2 | doctor: nota con la ragione, non un FIX |
| feed illeggibile o estraneo | static | ok | 2.7 | assente 3, illeggibile 3, estraneo 0 (nessun guasto inventato) |
| porta chiusa | live | ok | 5.2 | ident unreachable, shim headless (porta 7979) |
| app giusta sulla porta | e2e | ok | 10.2 | gridcraft 7975: ident/doctor/launcher tutti d'accordo |
| build diversa | e2e | ok | 11.4 | doctor, ident e launcher: tutti e tre exit 1 con 0.5.0 != 0.6.1 |
| altra app sulla porta | e2e | ok | 8.6 | GridCraft su 7972: doctor e ident lo riconoscono |
| credenziale rifiutata | e2e | ok | 7.1 | token diverso: accusato da doctor e ident (valore mai stampato) |
| argomenti della chiamata | unit | ok | 0.0 | numeri, stringhe (virgolettate), liste, null e booleani come li vuole la CLI |
| sessione del traduttore | unit | ok | 3.5 | 15 tool, parametri tipizzati, immagine, isError su guasto, -32602 sull'ignoto, modo bridged dichiarato, finestra sparita a meta' sessione diagnosticata |
| senza finestra il traduttore ripiega | unit | ok | 0.6 | nessuna finestra: il server headless del fornitore passa attraverso, dichiarato |
| finestra PdfCraft dal vivo | static | ok | 0.6 | porta 48129 (pid 42336), 15 metodi come li dichiara l'app |
| flag di aggancio, verificato | unit | ok | 0.4 | confermato, non confermato, flag diverso, assenza confermata e help illeggibile: sei verdetti, come li vuole l'help della CLI |
| doctor: flag non confermato | unit | ok | 5.7 | tabella non confermata -> FIX con l'azione; confermata dal canale -> ok; CLI assente -> nota |
| flag di aggancio dal vivo | static | ok | 2.6 | 11/11 CLI documentano il flag della tabella, e la diagnosi lo ripete |

## Confronto con l'esecuzione precedente

Rispetto al report del 13/10/2026 19:46:

- `craft-bridge-tests.py`: 65ed0b8a16fe -> e2187709e4f8

durata: 72.3s (precedente 70.5s, +1.8s)
