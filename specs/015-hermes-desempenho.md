# 015 — Desempenho do perfil Hermes `ragdev` no Mac de 24 GB

- **Status:** implementado (DevOps, 2026-11-18); o usuário aplica launchctl e reinstala o perfil
- **Módulos:** `hermes/config.yaml`, `hermes/skills/rag-harness/SKILL.md`,
  `hermes/hooks/inject_context.py`, `hermes/install.sh`, `hermes/README.md`, `README.md`,
  `docs/estudos/hermes-desempenho.md`
- **Testes:** `tests/test_hermes_config.py`

## Problema
No perfil `ragdev` (Qwen3.5 9B no Ollama 0.32, Mac M4 com 24 GB), o agente não conclui nem
"leia AGENTS.md e diga quais módulos existem". O `errors.log` mostra
`Interrupted provider wait counted as stale after 119s with no output`.

Medido em 2026-11-18 (detalhes em `docs/estudos/hermes-desempenho.md`):
- `ragdev prompt-size`: system prompt 23,8 KB + 21 ferramentas com 40,4 KB de schema
  = **~19,7 mil tokens** (`prompt_eval_count` do Ollama para um prompt do mesmo tamanho).
- Prefill no M4 a ~150 tokens/s: a 1ª chamada com cache frio leva **~131 s** só para ler o
  prompt, antes do 1º token. Passa dos ~120 s em que o usuário desiste (stale).
- Com o prefixo em cache, o mesmo prompt responde em ~6 s. Mas as três sessões do Hermes do
  dia começaram recarregando o modelo (`server.log`): o servidor rodava com
  `OLLAMA_KEEP_ALIVE` 5m e `OLLAMA_CONTEXT_LENGTH` 131072 (o `/v1` usado pelo Hermes carregou
  com 131072, não com o `ollama_num_ctx` 64000), e o app usa `num_ctx` 16384: cada troca
  recarrega o modelo e perde o cache.
- `reasoning_effort: medium` liga o raciocínio do Qwen, que gera centenas de tokens a
  ~12 tokens/s antes de cada ação.

## Comportamento esperado
A tarefa simples responde em tempo razoável (1º token bem abaixo de 120 s mesmo com cache
frio; segundos com cache quente), sem stale, e a documentação explica cada ajuste.

## Critérios de aceite
- **AC-1:** `hermes/config.yaml` tem `context_length` e `ollama_num_ctx` iguais e ≤ 32768.
- **AC-2:** `agent.reasoning_effort` é `"none"` (valor aceito pelo hermes-agent instalado;
  qualquer outro nível liga o raciocínio do Qwen no Ollama).
- **AC-3:** `delegation.max_concurrent_children` ≤ 1.
- **AC-4:** `agent.disabled_toolsets` desliga os toolsets que o projeto não usa (pelo menos
  `browser`, `code_execution`, `image_gen`, `tts`, `computer_use`) e mantém `terminal`,
  `file`, `skills`, `todo`, `memory` e `delegation`.
- **AC-5:** `compression.threshold` ≥ 0.75 (o hermes-agent aplica piso de 0.75 abaixo de
  512K, então 0.60 era ignorado) e o MCP `grafana` continua `enabled: false` e `lazy: true`.
- **AC-6:** a skill `rag-harness` e o hook `inject_context` orientam `--changed` durante a
  iteração e o harness completo só no fim.
- **AC-7:** `hermes/README.md` e `README.md` têm a tabela "Ajustes por hardware" com
  `NUM_PARALLEL × num_ctx`, `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`, os
  comandos `launchctl` e como reiniciar o Ollama; `docs/estudos/hermes-desempenho.md` existe
  e está no índice `docs/estudos/README.md`.
- **AC-8:** `install.sh` sugere `OLLAMA_NUM_PARALLEL 1`, `OLLAMA_CONTEXT_LENGTH` igual ao
  perfil, `OLLAMA_FLASH_ATTENTION 1` e `OLLAMA_KV_CACHE_TYPE q8_0`.

## Fora de escopo
- Mudar `.env`/`.env.example` (o alinhamento `OLLAMA_NUM_CTX=32768` do app é recomendação ao
  usuário), `src/`, `uv.lock`, `pyproject.toml`.
- Reiniciar o Ollama, mudar o `launchctl`, rodar `install.sh` no perfil real, parar containers.
- Trocar o modelo (ex.: Qwen 4B) ou podar as skills embutidas do Hermes.

## Plano
| Passo | Arquivo | Subagente | Verificação |
|---|---|---|---|
| 1 | medições (`ragdev prompt-size`, `/api/chat`, `ollama ps`) | engenheiro-devops | números na seção Problema |
| 2 | `tests/test_hermes_config.py` | engenheiro-devops | falha por AC-1..AC-6, AC-8 |
| 3 | `hermes/config.yaml`, skill, hook, `install.sh` | engenheiro-devops | `python hermes/harness/check.py --changed` |
| 4 | READMEs e `docs/estudos/` | engenheiro-devops | `python hermes/harness/check.py` |
