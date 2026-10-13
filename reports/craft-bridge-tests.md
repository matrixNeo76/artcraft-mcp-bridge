# Report della suite di guasti

**Generato:** 13/10/2026 16:46 · **host:** wkai01 · **Python:** 3.12.10
**Modi:** completo · **durata:** 44.7s
**Strumenti:** `mcp` `3f4bf8aa1ad4` · `ident` `8df181789548` · `doctor` `e16e1ab9f82a` · `config` `7776f22be252` · `tests` `1571ea4262fb`

## Esito

**10 passati, 0 falliti, 0 saltati** → tutto in ordine

| Caso | Tipo | Stato | Secondi | Dettaglio |
|---|---|---|---|---|
| stato pulito | static | ok | 1.3 | doctor: nessuna azione |
| shim installato stantio | static | ok | 1.9 | accusato e riparato dall'azione indicata |
| entry di config sbagliata | static | ok | 1.1 | doctor e installer concordano: 1 entry da aggiornare |
| percorso inesistente | static | ok | 0.8 | FIX percorsi: cadcraft.command |
| eseguibile mancante | unit | ok | 0.2 | lightcraft app, lightcraft cli |
| porta chiusa | live | ok | 5.1 | ident unreachable, shim headless (porta 7979) |
| app giusta sulla porta | e2e | ok | 9.1 | gridcraft 7975: ident/doctor/launcher tutti d'accordo |
| build diversa | e2e | ok | 10.4 | doctor, ident e launcher: tutti e tre exit 1 con 0.5.0 != 0.6.1 |
| altra app sulla porta | e2e | ok | 7.7 | GridCraft su 7972: doctor e ident lo riconoscono |
| credenziale rifiutata | e2e | ok | 6.0 | token diverso: accusato da doctor e ident (valore mai stampato) |

## Confronto con l'esecuzione precedente

Niente e' cambiato rispetto al report del 13/10/2026 16:45.

durata: 44.7s (precedente 45.0s, -0.3s)
