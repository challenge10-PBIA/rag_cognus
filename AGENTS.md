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
| `llm.py` | Fábrica única do ChatOllama (num_ctx/keep_alive do `.env`) | `tests/test_config.py` |
| `agents/` | Agentes de evidências e de comunicação, pipeline e juízes (spec 001) | `tests/test_agents.py` |
| `agents_ui.py` | Aba 🧠 Agentes do Streamlit | `tests/test_chat_app.py` |
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
- Não toque em `.env`, `uv.lock`, `mlruns/` sem pedido explícito; `data/` só o
  engenheiro de dados.
- Não faça `git push`, `git reset --hard` nem commits sem pedido.

## Time multiagente
Um **líder técnico** conversa com o usuário, escreve o plano e delega; três engenheiros
executam no seu domínio e devolvem relatório no formato combinado.

| Papel | Domínio |
|---|---|
| Líder técnico | Pedido → spec → plano → delegação → harness final → relatório ao usuário |
| Engenheiro de dados | `gold.py`, Databricks em `config.py`, `data/`, `notebooks/`, schema dos documentos |
| Engenheiro de IA | `retrieval.py`, `chain.py`, `judges.py`, `metrics.py`, `evaluation.py`, `speech.py`, lógica do `chat_app.py` |
| Engenheiro DevOps | `.github/`, `pyproject.toml`, `uv.lock`, `cli.py`, MLflow/Streamlit local, `hermes/`, `.claude/` |

- **Claude Code:** `.claude/agents/` (o líder é o agente principal da sessão).
- **Hermes:** skill `rag-orchestrator` com `delegate_task`.

Cada engenheiro recebe: objetivo, arquivos exatos, AC da spec, restrições e o comando de
verificação. Paralelo só quando os arquivos não se sobrepõem.
