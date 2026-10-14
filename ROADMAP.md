# Roadmap

State as of 13 October 2026: the bridge works and is verified (13/13 apps driveable, 14/14
entries, 24/24 in the fault suite, diagnosis `tutto in ordine`), the whole suite runs on every
push to `main` and a case that gets worse than the saved baseline stops the run. What follows is
what is worth doing next, in order of value for cost.

## Done

- [x] Control channel recognised and documented (protocol, ports, credentials).
- [x] Shim with bridged/headless choice through the handshake and `--require-bridge`.
- [x] App identity (command catalogue) and running build (PID, executable).
- [x] Single diagnosis (`doctor`) with actions, idempotent installer (`config`), launcher.
- [x] Repeatable proofs: `verify` (real entries), `sweep` (headless against bridged), `tests`
      (24 injected faults), `report-mcp-tools` (tool inventory).
- [x] Four real defects fixed at the cause and covered by the suite.
- [x] Documentation in an OKF v0.2 bundle with nodes and relations, in English.

## Next (small, immediately useful)

- [x] **Regression gate**: the suite exits 3 when a case gets worse than the saved baseline
      (PASS → SKIP counts: a proof that is not there is not a passed proof), the report records
      what got worse, and CI fails on it. See [craft-bridge-tests](docs/tools/craft-bridge-tests.md).
- [ ] **Append-only history** of runs (one line per run) to see the trend of outcomes and
      duration, instead of only the comparison with the previous run.
- [ ] **Hook**: run `craft-bridge-tests.py --static` after changes to `tools/` that touch shim,
      ident or doctor.
- [ ] **`doctor --tests`**: run the suite from the diagnosis, so it does not have to be
      remembered.
- [ ] **OKF node attestation**: today the nodes have `generated` but no `verified`. Attestation
      (`verified: { by: human:<id>, at: ... }`) is only put in after a real human review, node by
      node.

## Medium

- [ ] **Portability**: `taskkill` and `DETACHED_PROCESS` are Windows-specific; Linux/macOS need
      signals and `start_new_session`.
- [ ] **Installable package**: `pyproject.toml` with entry points (`craft-bridge doctor`,
      `… tests`) so the tools are used without the `tools/` prefix.
- [x] **CI**: GitHub Actions on Windows running `--static` on every push, and the whole suite -
      the cases with real apps - on the self-hosted runner, on every push to `main`. The procedure
      is in [docs/operations/ci.md](docs/operations/ci.md).
- [ ] **Unit tests of the protocol**: JSON-lines parsing, end of message, timeouts, network error
      handling — today covered only end-to-end.
- [ ] **Integrity beyond the version**: hash of the executable recorded in `builds.json`, to tell
      two builds with the same version apart.

## Long term

- [ ] **Diagnosis MCP server**: expose `doctor`, `ident` and `tests` as MCP tools, so an agent can
      verify the bridge from inside the session.
- [ ] **`craft-bridge watch`**: reconcile the state of the apps with what the clients expect on
      its own (start what is missing, flag what is wrong).
- [ ] **Reports comparable across machines**: an environment section (versions, builds, ports) in
      the reports, to compare runs made on different PCs.
- [ ] **Upstream**: propose to the app vendors the two gaps observed (no documented credential on
      a failed `auth`, no revision in the startup line) and, for PdfCraft, the missing bridge.
- [ ] **Regenerate the OKF bundle from the reports** (outcomes and measurements as nodes), instead
      of updating it by hand.

## Non-goals

- Not to replace the Crafting Apps nor to generate content in their place.
- Not to change the behaviour of the binaries: the bridge drives them, it does not modify them.
- Not to introduce a silent fallback: if the bridge is not there, it is said.
