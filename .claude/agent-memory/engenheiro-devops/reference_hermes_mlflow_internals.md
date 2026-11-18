---
name: hermes-mlflow-internals
description: Onde confirmar chaves do Hermes instalado e como o MLflow 3.18 resolve o LLM dos juízes (UI exige gateway:/)
metadata:
  type: reference
---

Verificado em 2026-11-18 (Hermes v0.23.1, MLflow 3.18.0):
- Hermes: fonte em `~/.hermes/hermes-agent` (`cli-config.yaml.example`,
  `website/docs/reference/mcp-config-reference.md`, `optional-mcps/<nome>/manifest.yaml`).
  `find /` para achar o example trava >2 min: vá direto nesse caminho.
- `delegate_task` só aceita goal/context/role; filhos herdam toolsets/MCP do pai.
- MLflow: juízes criados na UI gravam `gateway:/<endpoint>` (AI Gateway do servidor, provedor
  Ollama existe). Em código: `openai:/m` precisa OPENAI_API_KEY+OPENAI_API_BASE no processo do
  servidor (jobs herdam os.environ); `ollama:/m` funciona sem env (base localhost:11434).

**How to apply:** comece a investigação por esses caminhos; reconfirme se as versões mudaram.
Specs ligadas: 009, 011, 012. Veja [[guard-quirks]].
