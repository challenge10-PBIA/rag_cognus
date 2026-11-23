---
name: venv-drift
description: .venv (py3.14) diverge do uv.lock e tem pacotes extras; uv sync muda pandas/pyarrow/ruff — instalar pacote novo com uv pip install pinado
metadata:
  type: project
---

O `.venv` (Python 3.14, criado com `python -m venv`) tem todos os extras (dev, ui, audio, api)
mais pacotes fora do pyproject (databricks-connect, jupyter, pyspark). Em 2026-11-23,
`uv sync --all-extras --inexact --dry-run` queria trocar pandas 2.3.3→3.1.1, pyarrow 24→26 e
ruff 0.17.5→0.17.4; sem `--inexact` ainda removeria os pacotes extras.

**Why:** usuário instala por pip; um sync completo mexe em libs que nada pediu.
**How to apply:** para adicionar um pacote, `uv lock` e depois
`uv pip install --python .venv/bin/python "<pkg>==<versão do lock>"`; sempre rode o sync com
`--dry-run` antes e relate. Ver [[guard-quirks]].
