---
type: Tool
title: "craft-bridge-tests - la suite che inietta guasti"
description: "Dieci casi che rompono qualcosa di proposito e pretendono il verdetto giusto da doctor, ident e launcher; ogni esecuzione lascia un report con il confronto sulla precedente."
resource: ../../tools/craft-bridge-tests.py
tags: [strumento, test, guasti, report]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-tests.py
  title: sorgente
- resource: ../../reports/craft-bridge-tests.md
  title: l'ultimo report
- resource: ../../docs/architecture/reports.md
  title: il formato del report
---

# Cosa fa

Rende ripetibile cio' che era stato provato a mano: per ogni caso **rompe qualcosa**
(shim stantio, entry sbagliata, percorso inesistente, eseguibile mancante, build
0.5.0 sulla porta, altra app sulla porta, credenziale rifiutata, porta chiusa),
chiede il verdetto agli strumenti, pretende l'esito giusto e rimette a posto.

# Interfaccia

```
python tools/craft-bridge-tests.py                 # tutto (~44 s, avvia app vere)
python tools/craft-bridge-tests.py --static        # solo i casi senza app (~10 s)
python tools/craft-bridge-tests.py --only build --json
python tools/craft-bridge-tests.py --report reports/mie.json --compare vecchio.json
python tools/craft-bridge-tests.py --static --ci   # su un runner senza ponte installato
```

# `--ci`

Serve a un runner di CI: se la macchina non ha ne' la config dei connettori ne' le copie
installate, i casi che parlano del ponte vengono **saltati spiegando perche'** invece di
fallire. Un guasto vero resta un FAIL: la modalita' cambia cosa e' un ambiente assente, non
cosa e' un guasto. Su una macchina con il ponte, `--ci` non cambia niente - verificato:
6/6 senza salti. Vedi [Integrazione continua](../operations/ci.md).

# Report e confronto

Ogni esecuzione scrive `reports/craft-bridge-tests.json` (macchina) e
`reports/craft-bridge-tests.md` (leggibile), e confronta da sola con l'esecuzione
precedente: casi cambiati, comparsi, spariti, impronte degli strumenti. La durata e'
contesto. `--no-report` non scrive, `--no-compare` non legge.

# Regole di sicurezza

La config vera non viene mai scritta (i casi la riguardano su una copia con
`--config`); l'unico file vero toccato e' la copia **installata** dello shim, dentro
un `try/finally` che la rimette a posto; le app si avviano solo su porte libere, e se
una porta e' occupata il caso si salta invece di uccidere processi altrui; temporanei,
log e token di prova spariscono alla fine.

# Esiti

| Uscita | Significato |
|---|---|
| 0 | ogni caso passato (le SKIP non sono guasti) |
| 1 | almeno un FAIL |
| 2 | errore d'uso |

# Difetti trovati da questa suite

* [Credenziale rifiutata: crash e nessun verdetto](../findings/auth-refused-crash.md)
* [File installati non allineati al sorgente](../findings/stale-installed-files.md)

# Relazioni

- **verifica** [craft-bridge-doctor](craft-bridge-doctor.md), [craft-bridge-ident](craft-bridge-ident.md), [craft-bridge-launch](craft-bridge-launch.md)
- **produce** [Report e baseline](../architecture/reports.md)
- **nel runbook** [Diagnosi e verifica](../operations/diagnosis.md)
- **eseguita a ogni push da** [Integrazione continua](../operations/ci.md) con `--static --ci`
