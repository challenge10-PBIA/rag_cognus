---
name: hermes-ollama-perf
description: Como medir o desempenho do Hermes+Ollama no Mac (prompt-size, server.log) e armadilhas do /v1, lazy MCP e cache híbrido
metadata:
  type: reference
---

Verificado em 2026-11-18 (Ollama 0.32 com llama-server, Hermes local, spec 015):
- `ragdev prompt-size [--json]` mede system prompt + schemas offline. Para testar uma config
  sem tocar o perfil: `HERMES_HOME=<scratch com config.yaml + symlink skills>
  ~/.hermes/hermes-agent/.hermes/bin/hermes prompt-size`.
- `/v1` do Ollama IGNORA `options.num_ctx`: o Hermes roda com `OLLAMA_CONTEXT_LENGTH` do
  servidor. Ver `grep "server config" ~/.ollama/logs/server.log` e `starting llama-server -c N`.
- MCP `lazy: true` ainda põe as ferramentas no prompt (cache de schema); só `enabled: false` tira.
- `compression.threshold` tem piso 0.75 abaixo de 512K.
- qwen3.5:9b é híbrido: KV 32 KB/token f16; cache de prefixo só por checkpoint no fim do
  prompt. Bench com texto lido do repo muda se você editar os arquivos: use snapshot fixo.
- Prefill no M4 ~105–150 tok/s: gargalo real; cada bench frio leva 2–3 min (rode em background).

**How to apply:** comece diagnósticos de lentidão por esses comandos. Veja [[hermes-mlflow-internals]].
