---
name: guard-quirks
description: hermes/hooks/guard.py blocks .env.example edits (prefix match) and any Bash command text containing databricks:// or "cat .env"
metadata:
  type: project
---

The guard hook (hermes/hooks/guard.py) checks Bash command text and protected paths:
- Any Bash command containing `databricks://` or `cat .env` (also `cat .env.example`) is blocked,
  even in heredocs writing tests. Use Write/Edit tools for such content, Read for .env.example.
- PROTECTED uses `path.startswith(".env")`, so `.env.example` cannot be edited by agents
  (seen 2026-11-16, spec 004 AC-D2). Do not bypass; report and hand the text to the leader/user.

**Why:** bypassing a user-configured guard is not allowed even when the task permits the file.
**How to apply:** for .env.example changes, expect a block; propose fixing the guard
(exact match for `.env`) as a separate, explicitly requested change.
