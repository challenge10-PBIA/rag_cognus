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
- Since spec 009 (2026-11-18): Bash text with `$…TOKEN/SECRET/PASSWORD/API_KEY` is blocked, and
  any Bash/Write/Edit content with a Grafana token literal (`glsa_`/`glc_` + 16+ chars). Tests
  that need a fake token build it by concatenation (`"gl" + "sa_" + ...`), see test_hermes_guard.py.
- Bash text mentioning `rag-cognus evaluate` (even inside a heredoc that edits a doc/spec) is
  blocked as "acessa Databricks/LLM real"; also any `${...TOKEN}` in a python heredoc. Use Edit.
- The harness pytest runs with `-x`: with a known expected failure, run
  `pytest -q --deselect <that test>` to prove the rest is green.
- Guard tests run the real script, so blocked events land in `.hermes-runs/events.jsonl`.

**Why:** bypassing a user-configured guard is not allowed even when the task permits the file.
**How to apply:** for .env.example changes, expect a block; propose fixing the guard
(exact match for `.env`) as a separate, explicitly requested change.
