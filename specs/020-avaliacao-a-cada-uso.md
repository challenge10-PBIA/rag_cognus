# 020 — Avaliação online a cada uso

- **Status:** rascunho (aguarda ok do usuário)
- **Módulos:** `src/rag_cognus/api/app.py`, `src/rag_cognus/api/store.py`,
  `src/rag_cognus/api/metrics.py`, `src/rag_cognus/evaluation.py`,
  `src/rag_cognus/agents/agents_judges.py`, `src/rag_cognus/chat_app.py`,
  `src/rag_cognus/agents_ui.py`, `src/rag_cognus/cli.py`
- **Testes:** `tests/test_api.py`, `tests/test_api_metrics.py`, `tests/test_evaluation.py`,
  `tests/test_agents.py`, `tests/test_chat_app.py`

## Problema
Hoje só o `POST /v1/ask` dispara a avaliação online (spec 004). Os outros usos que geram
texto com LLM ficam sem nota: a gravação de sessão (`POST /v1/sessions`, que adapta a fala
com o agente de comunicação), as rotas `/v1/agents/*`, o chat Streamlit e a CLI. No MLflow
eles aparecem só como traces sem assessments. Exemplo de 2026-11-18: a sessão gravada às
16:16 gerou o trace `tr-ae128b63…` (flow=communication), sem run em `rag-cognus-online` e
sem linha em `evaluations`. Além disso, um `/v1/ask` cuja geração é rejeitada (citação de
ID ausente → 422) não deixa nenhum registro.

## Inventário (2026-11-18)
| Caminho | Arquivo:linha | Avalia hoje? |
|---|---|---|
| `POST /v1/ask` | `api/app.py:706` | sim, online em 2º plano (spec 004) |
| `POST /v1/ask` com 422 (citação inválida) | `api/app.py:716`, `chain.py:136` | não, sem registro |
| `POST /v1/sessions` → `CommunicationAgent` | `api/app.py:353` | não |
| `POST /v1/agents/evidence` | `api/app.py:764` | não |
| `POST /v1/agents/communication` | `api/app.py:769` | não |
| `POST /v1/agents/pipeline` | `api/app.py:774` | não |
| `POST /v1/mascot/explain` (`MascotCoach`) | `api/app.py:831` | não; não há juiz |
| Chat Streamlit (RAG) | `chat_app.py:518` | só com a opção "notas", síncrono, sem run |
| Aba Agentes do Streamlit | `agents_ui.py:108`, `agents_ui.py:208` | só com a opção, síncrono, sem run |
| CLI `ask` / `synthesize` / `adapt` | `cli.py:305`, `cli.py:32`, `cli.py:43-46` | só com `--judge`, sem run |
| Checagem de pleonasmo / feedback guiado | `api/app.py:110`, `api/app.py:307` | não (passo interno, não é resposta) |
| CLI `evaluate` (lote) | `cli.py:325` | sim, em lote (não muda) |

## Comportamento esperado
Toda resposta de LLM entregue a quem usa dispara uma avaliação em segundo plano. A resposta
não espera pela avaliação. Cada avaliação vira uma linha em `evaluations`, um run em
`rag-cognus-online` com a tag `flow` e as notas como assessments no trace da resposta.

## Critérios de aceite
- **AC-1:** Fluxos e juízes fixos: `rag` → juiz do RAG (`judges.make_judge`), `evidence` →
  `make_evidence_judge`, `communication` → `make_communication_judge`, `pipeline` → os dois
  juízes de agentes num só run (métricas com prefixo `evidence_`/`communication_`), `session`
  → juiz de comunicação sobre a adaptação da fala.
- **AC-2:** `POST /v1/agents/evidence|communication|pipeline` e `POST /v1/sessions` (quando
  há texto adaptado) criam uma linha em `evaluations` com `flow` e enfileiram a avaliação.
  A resposta ganha `evaluation_id` e `evaluation_status`, sem esperar o juiz.
- **AC-3:** `evaluations` ganha a coluna `flow` (migração aditiva, linhas antigas = `rag`).
  `GET /v1/evaluations/{id}` devolve qualquer fluxo; `GET /v1/ask/{ask_id}/evaluation`
  continua igual.
- **AC-4:** Avaliação concluída → run `<flow>-<id>` em `rag-cognus-online` com tags `flow`,
  `evaluation_id` e `trace_id`, params do modelo e do juiz e as métricas do fluxo. As notas
  também viram assessments `LLM_JUDGE` no trace (`trace_id`) da resposta.
- **AC-5:** O juiz falha (exceção, JSON inválido, Ollama fora do ar) → `status="error"` com
  mensagem curta em português; a resposta já entregue não muda; o worker segue vivo e atende
  a próxima tarefa.
- **AC-6:** MLflow fora do ar → `status="done"` com `mlflow_logged=false` (igual à spec 004
  AC-8).
- **AC-7:** `RAG_ONLINE_EVAL=false` desliga tudo: nenhuma chamada ao juiz, linhas com
  `status="disabled"`, sem run, nos fluxos da API, do Streamlit e da CLI.
- **AC-8:** Fila única por processo, com 1 worker (Ollama local atende um por vez) e no
  máximo `RAG_ONLINE_EVAL_MAX_PENDING` tarefas à espera (padrão 4). Fila cheia → a nova
  linha fica `status="skipped"`, `error="Fila de avaliação cheia."`. Nada bloqueia a resposta.
- **AC-9:** Geração rejeitada no `/v1/ask` (citação de ID ausente ou falta de fontes, hoje
  422) grava uma linha `flow=rag`, `status="rejected"` com o motivo, sem chamar o juiz. O
  422 continua.
- **AC-10:** Prometheus (spec 016): `rag_cognus_online_eval_total{flow,outcome}` com `flow`
  ∈ {rag, evidence, communication, pipeline, session} e `outcome` ∈ {ok, error, skipped,
  rejected}; `rag_cognus_judge_score{flow,metric}` só com as métricas fixas de cada juiz; e o
  gauge novo `rag_cognus_online_eval_pending`. Valor fora do conjunto não cria série.
- **AC-11:** O chat e a aba Agentes do Streamlit usam a mesma fila e o mesmo registro (Store
  em `.cache/app/cognus.db`). A resposta aparece antes das notas, que surgem quando
  `status="done"`. A opção "notas" passa a só mostrar ou esconder as notas.
- **AC-12:** CLI `ask`/`synthesize`/`adapt` imprimem a resposta e depois avaliam no mesmo
  processo antes de sair (sem thread que morra com o processo). `--no-eval` pula. `--judge`
  continua mostrando as notas no JSON.
- **AC-13:** `OLLAMA_JUDGE_MODEL` continua valendo para todos os juízes, e o run registra o
  `judge_model` usado.
- **AC-14:** `rag-cognus evaluate` (lote) não muda: mesmo experimento, mesmas métricas.

## Fora de escopo
- `POST /v1/mascot/explain`: não há juiz para o coach. Fica para uma spec própria (juiz de
  fidelidade aos `facts`).
- Pleonasmo e feedback guiado: são passos internos, não respostas entregues.
- Prioridade ou preempção no Ollama; amostragem (avaliar só uma fração).

## Impacto
- Cada uso passa a ocupar o Ollama mais ~30–40 s com o juiz (o `a5ac5587eb57` levou 36 s).
  Com `OLLAMA_NUM_PARALLEL=1`, a pergunta seguinte pode esperar um juiz em andamento.
  Mitigação: um `OLLAMA_JUDGE_MODEL` menor, que também reduz o viés de autoavaliação.
- Os dashboards da spec 017 que somam `rag_cognus_online_eval_total` por `outcome`
  continuam valendo; os painéis por métrica precisam de `sum by (metric)`.

## Plano (preenchido depois da aprovação)
| Passo | Arquivo | Subagente | Verificação |
|---|---|---|---|
| 1 | `tests/test_api.py`, `tests/test_api_metrics.py` | engenheiro-ia | AC-1…AC-10 vermelhos |
| 2 | `api/*`, `evaluation.py`, `agents_judges.py` | engenheiro-ia | `check.py --changed` |
| 3 | `chat_app.py`, `agents_ui.py`, `cli.py` | engenheiro-ia / devops (cli) | AC-11, AC-12 |
| 4 | Grafana (spec 017) | engenheiro-devops | painéis com `flow` |
