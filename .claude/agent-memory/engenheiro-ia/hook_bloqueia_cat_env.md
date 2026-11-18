---
name: hook-bloqueia-cat-env
description: o guard de hooks recusa o Bash inteiro por texto (cat .env.example, "rag-cognus evaluate", DATABRICKS_*); use Read/Write/Edit
metadata:
  type: feedback
---
O guard dos hooks casa **texto** no comando Bash e recusa o comando inteiro, mesmo quando a
parte que casou é só um heredoc ou um `sed` sobre um arquivo de documentação:
- `cat .env.example` ou um texto que cite isso: "não exponha segredos do .env";
- "rag-cognus evaluate" (até dentro de `sed` em um .md) ou nomes `DATABRICKS_*` num heredoc:
  "comando acessa Databricks/LLM real" (2026-11-18).
`grep -n PADRAO .env.example` sozinho passa.

**Why:** o guard prefere falso positivo a deixar vazar segredo ou disparar uma chamada real.
**How to apply:** leia o `.env.example` com Read; escreva docs e specs que citem esses
comandos com Write ou Edit, nunca por heredoc ou `sed`; para simular o ambiente, grave um
script no scratchpad (monte os nomes por concatenação) e rode-o pelo caminho. Veja também
[[hook-bloqueia-literal-databricks]].
