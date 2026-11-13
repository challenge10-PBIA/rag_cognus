# AGENTS.md — rag_cognus

Contexto para agentes de código (Hermes Agent, Claude Code, Codex). Seja curto e factual.

## Projeto
RAG em Python 3.11+: lê a Gold `cognus.gold.vw_rag_conhecimento` (Databricks, só leitura),
recupera com BM25/embeddings, responde com Qwen3.5 9B no Ollama e registra avaliações no
MLflow **local** (`http://127.0.0.1:5001`; URIs `databricks://` são proibidas).

| Módulo (`src/rag_cognus/`) | Papel | Teste |
|---|---|---|
| `config.py` | Settings via `.env` | `tests/conftest.py` |
| `gold.py` | Sync/leitura da Gold | `tests/test_gold.py` |
| `retrieval.py` | BM25 / embeddings, top-k | `tests/test_retrieval.py` |
| `chain.py` | Prompt + LLM + citações | `tests/test_chain.py` |
| `judges.py`, `metrics.py` | Juiz LLM e métricas | `tests/test_response_metrics.py` |
| `evaluation.py` | Avaliação em lote → MLflow | `tests/test_evaluation.py` |
| `chat_app.py` | UI Streamlit | `tests/test_chat_app.py` |
| `speech.py` | Áudio → texto (faster-whisper) | `tests/test_speech.py` |
| `cli.py` | Comando `rag-cognus` | — |

## Comandos
- Harness completo (lint + format + testes): `python hermes/harness/check.py`
- Só testes afetados pelo diff: `python hermes/harness/check.py --changed`
- Um teste: `.venv/bin/python -m pytest -q tests/test_chain.py -k nome`
- Nunca rode `sync-gold`, `evaluate` ou chamadas reais ao Databricks/Ollama em testes.

## Fluxo obrigatório (SDD → TDD → Harness)
1. **Spec**: mudança de comportamento começa em `specs/NNN-slug.md` (modelo em
   `specs/_TEMPLATE.md`). Critérios de aceite numerados (AC-1, AC-2…).
2. **Teste vermelho**: um teste por AC em `tests/`, rodar e ver falhar pelo motivo certo.
3. **Implementação mínima** até ficar verde. Sem refatorar junto.
4. **Harness**: `python hermes/harness/check.py` precisa passar antes de dizer "pronto".
5. Relate o que foi verificado com a saída real; se algo falhou, diga.

## Regras
- Edite o mínimo; leia o arquivo antes de alterar; use `patch` em vez de reescrever.
- Testes não acessam rede: use fakes/monkeypatch (veja `tests/conftest.py`).
- Linha ≤ 100 colunas, `ruff format`. Textos de UI e mensagens em português.
- Não toque em `.env`, `uv.lock`, `mlruns/`, `data/` sem pedido explícito.
- Não faça `git push`, `git reset --hard` nem commits sem pedido.

## Multiagentes
Para tarefas com mais de um módulo, carregue a skill `rag-orchestrator` e delegue com
`delegate_task`. Cada subagente recebe: objetivo, arquivos exatos, AC da spec e o comando
de verificação. Subagentes devolvem resumo curto + caminhos alterados + saída do harness.
