---
okf_version: "0.2"
---

# Craft Bridge - bundle index

OKF v0.2 bundle for the documentation of the bridge between the Crafting Apps and MCP
clients. Bundle root: this folder (`docs/`). The executable code and the generated
reports live outside the bundle, in `tools/`, `install/`, `reports/`.

# Project
* [Overview](overview.md) - what the bridge is, the problem it solves, current state
* [Technical manual](reference/craft-bridge.md) - the long, complete text, with every measurement
* [Ecosystem analysis](reference/analysis.md) - inventory of the 13 MCP servers and of the environment
* [Spec](reference/spec.md) - requirements and acceptance criteria
* [Plan](reference/plan.md) - phases and milestones

# Architecture
* [Control channel](architecture/control-channel.md) - JSON-lines protocol, ports, credentials
* [Shim modes](architecture/shim-modes.md) - bridged or headless, and how it is decided
* [Identity and build](architecture/identity.md) - who answers on the port and which version is running
* [Installed, source and global MCP](architecture/installation-layout.md) - why moving the repo does not break the connectors
* [Where the app is](architecture/app-locations.md) - the system resolves the paths, the table confirms them
* [Reports and baseline](architecture/reports.md) - where reports go and how two runs are compared

# Tools
* [craft-bridge-mcp](tools/craft-bridge-mcp.md) - the stdio shim that chooses the mode
* [craft-bridge-ident](tools/craft-bridge-ident.md) - who answers on the port and which build
* [craft-bridge-doctor](tools/craft-bridge-doctor.md) - one single verdict on the whole assembly
* [craft-bridge-feed](tools/craft-bridge-feed.md) - what the vendor publishes, against what is installed
* [craft-bridge-ui](tools/craft-bridge-ui.md) - the PdfCraft window as an MCP server, one method per call
* [craft-bridge-config](tools/craft-bridge-config.md) - idempotent installer of copies and entries
* [craft-bridge-launch](tools/craft-bridge-launch.md) - starts one or more apps with the channel active
* [craft-bridge-verify](tools/craft-bridge-verify.md) - queries every entry with its real command
* [craft-bridge-sweep](tools/craft-bridge-sweep.md) - measures headless against bridged, app by app
* [craft-bridge-tests](tools/craft-bridge-tests.md) - the suite that injects faults
* [Exploratory tools](tools/exploration.md) - recon, probe, pilot
* [report-mcp-tools](tools/report-mcp-tools.md) - real inventory of the servers' tools
* [artcraft-mcp-proxy](tools/artcraft-mcp-proxy.md) - conformance shim for the generative MCP

# Operations
* [Install and repair](operations/install-and-repair.md) - runbook
* [Diagnosis and verification](operations/diagnosis.md) - runbook
* [Safety rules](operations/safety-rules.md) - what is never touched
* [Continuous integration](operations/ci.md) - what every push checks, and what `--ci` means

# Defects found and fixed
* [Silent fallback on a mute peer](findings/silent-fallback.md)
* [Wrong app and different build on the port](findings/wrong-app-and-build.md)
* [Refused credential: crash and no verdict](findings/auth-refused-crash.md)
* [Installed files not aligned with the source](findings/stale-installed-files.md)
