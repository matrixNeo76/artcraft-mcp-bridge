---
type: Finding
title: "Refused credential: crash and no verdict"
description: "With a wrong token the app closes the connection and the next write raises ConnectionAbortedError: ident died with a traceback and never printed the verdict."
resource: ../../tools/craft-bridge-ident.py
tags: [defect, credential, network]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../tools/craft-bridge-ident.py
  title: the fixed code
- resource: ../../tools/craft-bridge-mcp.py
  title: the shim, with the same pattern
- resource: ../../tools/craft-bridge-tests.py
  title: the suite that exercises the tools
---

# Symptom

A token different from the app's: `craft-bridge-ident.py` exited 1 with a traceback and an
**empty stdout** - no verdict, no JSON. The case came out of the fault suite, not from a
manual test.

# Cause

The app, having refused the credential, **closes the connection**. The `sendall` that
followed raised `ConnectionAbortedError`, which was not handled.

# Fix

A network error no longer propagates: what was read is returned and the verdict is given
anyway. The **same pattern** was in the shim, where it would have been worse - an MCP
server lost at startup - and it was fixed there too.

# Process consequence

After the fix the **installed** files were still behind the source: the suite reported it by
itself as `FAIL stato pulito`, quoting the doctor line that explained it. See
[installed files not aligned](stale-installed-files.md).

# Relations

- **covered by** [craft-bridge-tests](../tools/craft-bridge-tests.md) - the *refused credential* case
- **concerns** [Control channel](../architecture/control-channel.md) - the close on a failed `auth`
- **rule in** [Safety rules](../operations/safety-rules.md) - the token value is never printed
