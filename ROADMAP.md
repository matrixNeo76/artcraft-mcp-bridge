# Roadmap

Stato al 13 ottobre 2026: il ponte funziona ed è verificato (11/12 app guidabili,
13/13 entry, 10/10 nella suite di guasti, diagnosi `tutto in ordine`). Quello che segue
è ciò che vale la pena fare dopo, in ordine di rapporto fra valore e costo.

## Fatto

- [x] Canale di controllo riconosciuto e documentato (protocollo, porte, credenziali).
- [x] Shim con scelta bridged/headless via handshake e `--require-bridge`.
- [x] Identità dell'app (catalogo dei comandi) e build in esecuzione (PID, eseguibile).
- [x] Diagnosi unica (`doctor`) con azioni, installer idempotente (`config`), launcher.
- [x] Prove ripetibili: `verify` (entry reali), `sweep` (headless contro bridged),
      `tests` (10 guasti iniettati), `report-mcp-tools` (inventario tool).
- [x] Quattro difetti veri corretti alla causa e coperti dalla suite.
- [x] Documentazione in bundle OKF v0.2 con nodi e relazioni.

## Prossimo (piccolo, subito utile)

- [ ] **Cancello sulle regressioni**: la suite esce diverso da zero quando un caso
      peggiora rispetto alla baseline, così una regressione blocca invece di essere
      solo letta.
- [ ] **Storico append-only** delle esecuzioni (una riga per run) per vedere la
      tendenza di esiti e durata, invece del solo confronto con l'esecuzione
      precedente.
- [ ] **Hook**: eseguire `craft-bridge-tests.py --static` dopo modifiche a `tools/`
      che toccano shim, ident o doctor.
- [ ] **`doctor --tests`**: far girare la suite dalla diagnosi, per non doversene
      ricordare.
- [ ] **Attestazione dei nodi OKF**: oggi i nodi hanno `generated` ma nessun
      `verified`. L'attestazione (`verified: { by: human:<id>, at: ... }`) va messa
      solo dopo una revisione umana reale, nodo per nodo.

## Medio

- [ ] **Portabilità**: `taskkill` e `DETACHED_PROCESS` sono Windows; per Linux/macOS
      servono segnali e `start_new_session`.
- [ ] **Pacchetto installabile**: `pyproject.toml` con entry point (`craft-bridge
      doctor`, `… tests`) così gli strumenti si usano senza prefisso `tools/`.
- [ ] **CI**: GitHub Actions su Windows che esegue `--static` a ogni push (i casi con
      app vere restano locali, richiedono gli eseguibili installati).
- [ ] **Test unitari del protocollo**: parsing JSON-lines, fine messaggio, timeout,
      gestione degli errori di rete — oggi coperti solo end-to-end.
- [ ] **Integrità oltre la versione**: hash dell'eseguibile registrato in
      `builds.json`, per distinguere due build con la stessa versione.

## Lungo

- [ ] **Server MCP di diagnosi**: esporre `doctor`, `ident` e `tests` come tool MCP,
      così un agente può verificare il ponte da dentro la sessione.
- [ ] **`craft-bridge watch`**: riconciliare da solo lo stato delle app con quello che
      i client si aspettano (avvia ciò che manca, segnala ciò che è sbagliato).
- [ ] **Report confrontabili fra macchine**: sezione ambiente (versioni, build,
      porte) nei report, per confrontare esecuzioni fatte su PC diversi.
- [ ] **Upstream**: proporre ai produttori delle app le due lacune osservate (nessuna
      credenziale documentata su `auth` fallito, assenza di revisione nella riga di
      avvio) e, per PdfCraft, il ponte mancante.
- [ ] **Rigenerare il bundle OKF dai report** (esiti e misure come nodi), invece di
      aggiornarlo a mano.

## Non obiettivi

- Non sostituire le Crafting Apps né generare contenuti al posto loro.
- Non modificare il comportamento dei binari: il ponte li guida, non li modifica.
- Non introdurre un fallback silenzioso: se il ponte non c'è, si dice.
