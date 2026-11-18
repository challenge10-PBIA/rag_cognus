@AGENTS.md

## Claude Code: time de agentes

A sessão principal roda como `lider-tecnico` (definido em `.claude/settings.json`).
Ele conversa com o usuário e delega para:

- `engenheiro-dados` — Gold/Databricks, documentos, datasets de avaliação
- `engenheiro-ia` — recuperação, geração, juízes, métricas, voz, lógica do chat
- `engenheiro-devops` — CI, dependências, CLI, MLflow/Streamlit local, harness e configs de agentes

Definições em `.claude/agents/`. Hooks de `hermes/hooks/` bloqueiam comandos destrutivos e
arquivos protegidos e formatam os `.py` editados (os mesmos usados no Hermes).
