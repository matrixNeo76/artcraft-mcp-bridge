---
type: Policy
title: "Project safety rules"
description: "The rules that always hold: what is not modified, which files are sacred, how to test without touching the real configuration."
resource: ../../README.md
tags: [policy, safety, rules]
generated: { by: process:freebuff-buffy, at: 2026-10-13T14:26:01Z }
status: stable
sources:
- resource: ../../docs/reference/craft-bridge.md
  title: complete technical manual
- resource: ../../tools/craft-bridge-tests.py
  title: the suite that exercises the tools
---

# Files that are never edited by hand

* `~/.agents/mcp.json` (the connector config): only `craft-bridge-config.py --apply`
  writes it, and it backs it up first.
* `%LOCALAPPDATA%\Programs\craft-bridge\*`: these are copies; they are updated with
  `--apply`, not by hand.
* `~/.craft-bridge/photocraft.token`: the app writes it. The value is never printed, never
  goes into chat and never enters the repo.

# Rules of the tests

* The **real** configuration is never used as a guinea pig: the tests exercise it on a
  temporary copy with `--config`.
* The only real file the suite touches is the installed copy of the shim, inside a
  `try/finally` that puts it back; if needed, `--apply` realigns it.
* Apps are started **only on free ports**; an occupied port makes the case skip, it does
  not authorise killing someone else's processes.
* Temporary files, logs and test tokens are deleted at the end.

# Downloading published packages

`craft-bridge-feed.py --download <slug>` downloads one package from the launcher feed in
order to compare its bytes. The rules hold even when it would be convenient to skip them:

* only on explicit request and one app at a time: packages run from 14 to 120 MB, and
  downloading them all "just in case" is a way of getting none of them done;
* `https` only, and only towards the GitHub hosts listed in the code: the feed is a local
  file that anyone can rewrite, so before opening a connection we check who we are talking
  to;
* the published `sha256` digest is verified **before** the file is used, and it stays
  `<name>.parte` until it matches: if it does not match it is **deleted**, and a failed
  download never becomes a verdict on the bytes;
* nothing is extracted to disk: the file inside the archive is read in memory, so a second
  copy of the app does not appear anywhere;
* the cache is `~/.craft-bridge/releases` and can be deleted at will: it is not the
  launcher's folder, which is the launcher's own.

# Source against installed

Changing the shim, `ident` or the window translator in the repo does **not** change what
Freebuff runs: `python tools/craft-bridge-config.py --apply` is required. The diagnosis
reports the difference - see
[Installed, source and global MCP](../architecture/installation-layout.md).

# Relations

- **enforced by** [craft-bridge-tests](../tools/craft-bridge-tests.md)
- **checked by** [craft-bridge-doctor](../tools/craft-bridge-doctor.md)
- **they apply to** [craft-bridge-feed](../tools/craft-bridge-feed.md) too - on-demand downloads
