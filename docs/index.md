---
okf_version: "0.2"
---

# Craft Bridge - indice del bundle

Bundle OKF v0.2 della documentazione del ponte tra le Crafting Apps e i client MCP.
Radice del bundle: questa cartella (`docs/`). Il codice eseguibile e i report
generati stanno fuori dal bundle, in `tools/`, `install/`, `reports/`.

# Progetto
* [Panoramica](overview.md) - cos'e' il ponte, quale problema risolve, stato attuale
* [Manuale tecnico](reference/craft-bridge.md) - il testo lungo e completo, con tutte le misure
* [Analisi dell'ecosistema](reference/analisi.md) - inventario dei 13 server MCP e dell'ambiente
* [Spec](reference/spec.md) - requisiti e criteri di accettazione
* [Piano](reference/piano.md) - fasi e milestone

# Architettura
* [Canale di controllo](architecture/control-channel.md) - protocollo JSON-lines, porte, credenziali
* [Modi dello shim](architecture/shim-modes.md) - bridged o headless, e come si decide
* [Identita' e build](architecture/identity.md) - chi risponde sulla porta e quale versione ci gira
* [Installato, sorgente e MCP globale](architecture/installation-layout.md) - perche' spostare il repo non rompe i connettori
* [Report e baseline](architecture/reports.md) - dove finiscono i report e come si confrontano due esecuzioni

# Strumenti
* [craft-bridge-mcp](tools/craft-bridge-mcp.md) - lo shim stdio che sceglie il modo
* [craft-bridge-ident](tools/craft-bridge-ident.md) - chi risponde sulla porta e quale build
* [craft-bridge-doctor](tools/craft-bridge-doctor.md) - un verdetto solo su tutto l'assieme
* [craft-bridge-feed](tools/craft-bridge-feed.md) - cosa il fornitore pubblica, contro cosa e' installato
* [craft-bridge-config](tools/craft-bridge-config.md) - installer idempotente di copie ed entry
* [craft-bridge-launch](tools/craft-bridge-launch.md) - avvia una o piu' app col canale attivo
* [craft-bridge-verify](tools/craft-bridge-verify.md) - interroga ogni entry col suo comando reale
* [craft-bridge-sweep](tools/craft-bridge-sweep.md) - misura headless contro bridged, app per app
* [craft-bridge-tests](tools/craft-bridge-tests.md) - la suite che inietta guasti
* [Strumenti esplorativi](tools/exploration.md) - recon, probe, pilot
* [report-mcp-tools](tools/report-mcp-tools.md) - inventario reale dei tool dei server
* [artcraft-mcp-proxy](tools/artcraft-mcp-proxy.md) - shim di conformita' per l'MCP generativo

# Operazioni
* [Installare e riparare](operations/install-and-repair.md) - runbook
* [Diagnosi e verifica](operations/diagnosis.md) - runbook
* [Regole di sicurezza](operations/safety-rules.md) - cosa non si tocca mai
* [Integrazione continua](operations/ci.md) - cosa controlla ogni push, e cosa significa `--ci`

# Difetti trovati e corretti
* [Ripiego silenzioso sul peer muto](findings/silent-fallback.md)
* [App sbagliata e build diversa sulla porta](findings/wrong-app-and-build.md)
* [Credenziale rifiutata: crash e nessun verdetto](findings/auth-refused-crash.md)
* [File installati non allineati al sorgente](findings/stale-installed-files.md)
