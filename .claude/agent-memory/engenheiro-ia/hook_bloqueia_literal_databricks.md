---
name: hook-bloqueia-literal-databricks
description: O hook guard de hermes/hooks recusa qualquer comando Bash que contenha o literal "databricks://", até dentro de heredoc de teste
metadata:
  type: feedback
---

Não escreva o literal `databricks://` em comandos Bash, nem dentro de heredocs. O guard PreToolUse recusa o comando inteiro.

**Why:** em 2026-11-16 um heredoc que adicionava teste de URI remota recusada foi bloqueado pelo hook ("tracking no Databricks é proibido").

**How to apply:** para testar a rejeição de tracking remoto, use outra URI não local (ex.: `http://mlflow.exemplo.com`) e o `match="MLflow local"` de `ensure_local_tracking`.
