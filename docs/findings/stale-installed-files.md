---
type: Finding
title: "Installed files not aligned with the source"
description: "The config copied shim and ident only if an entry changed: with the entries in place, the installed copy stayed old while the source moved on."
resource: ../../tools/craft-bridge-config.py
tags: [defect, installation, drift]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-config.py
  title: the fixed code
- resource: ../../docs/architecture/installation-layout.md
  title: the two places
- resource: ../../tools/craft-bridge-tests.py
  title: the suite that exercises the tools
---

# Symptom

With 11 entries already in place, `craft-bridge-config.py` said «da aggiornare (0)» and the
installed copy of the shim stayed the old one: different hashes, measured.

# Cause

Copying the files was tied to the **event** "an entry changed", not to the state of the
files. Two different things that looked like the same one.

# Fix

The installer compares the **bytes** of the files and realigns them when needed, entries
changed or not; and it installs `craft-bridge-ident.py` next to the shim as well, since it
is needed for the question about the build. Idempotent: on the second run it writes
nothing.

# Who notices

`craft-bridge-doctor.py`: the `shim installato` line compares the fingerprints and says
`FIX` with the `--apply` action. The [fault suite](../tools/craft-bridge-tests.md) covers
the case by injecting one extra byte into the installed copy and demanding that the
indicated action repairs it.

# Relations

- **rule in** [Installed, source and global MCP](../architecture/installation-layout.md)
- **detected by** [craft-bridge-doctor](../tools/craft-bridge-doctor.md)
- **linked to** [refused credential](auth-refused-crash.md) - it first surfaced there
