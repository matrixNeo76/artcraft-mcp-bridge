# Report della suite di guasti

**Generato:** 13/10/2026 17:24 · **host:** wkai01 · **Python:** 3.12.10
**Modi:** completo · **durata:** 44.8s
**Strumenti:** `mcp` `3f4bf8aa1ad4` · `ident` `8df181789548` · `doctor` `a84f864bc053` · `config` `7776f22be252` · `feed` `e134b02049ac` · `tests` `f660a0079e28`

## Esito

**13 passati, 0 falliti, 0 saltati** → tutto in ordine

| Caso | Tipo | Stato | Secondi | Dettaglio |
|---|---|---|---|---|
| stato pulito | static | ok | 0.9 | doctor: nessuna azione |
| shim installato stantio | static | ok | 2.1 | accusato e riparato dall'azione indicata |
| entry di config sbagliata | static | ok | 1.2 | doctor e installer concordano: 1 entry da aggiornare |
| percorso inesistente | static | ok | 0.8 | FIX percorsi: cadcraft.command |
| eseguibile mancante | unit | ok | 0.2 | lightcraft app, lightcraft cli |
| confronto col feed del launcher | unit | ok | 0.0 | 9 righe: dietro, pari, assente, estraneo e i tre casi di byte |
| feed assente non e' un guasto | unit | ok | 0.2 | doctor: nota con la ragione, non un FIX |
| feed illeggibile o estraneo | static | ok | 1.7 | assente 3, illeggibile 3, estraneo 0 (nessun guasto inventato) |
| porta chiusa | live | ok | 5.1 | ident unreachable, shim headless (porta 7979) |
| app giusta sulla porta | e2e | ok | 8.8 | gridcraft 7975: ident/doctor/launcher tutti d'accordo |
| build diversa | e2e | ok | 9.9 | doctor, ident e launcher: tutti e tre exit 1 con 0.5.0 != 0.6.1 |
| altra app sulla porta | e2e | ok | 7.3 | GridCraft su 7972: doctor e ident lo riconoscono |
| credenziale rifiutata | e2e | ok | 5.6 | token diverso: accusato da doctor e ident (valore mai stampato) |

## Confronto con l'esecuzione precedente

Rispetto al report del 13/10/2026 16:46:

- `confronto col feed del launcher`: nuovo (PASS)
- `feed assente non e' un guasto`: nuovo (PASS)
- `feed illeggibile o estraneo`: nuovo (PASS)
- `craft-bridge-doctor.py`: e16e1ab9f82a -> a84f864bc053
- `craft-bridge-feed.py`: nuovo strumento (e134b02049ac)
- `craft-bridge-tests.py`: 1571ea4262fb -> f660a0079e28

durata: 44.8s (precedente 44.7s, +0.1s)
