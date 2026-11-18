# 004 — Avaliação online do RAG no MLflow local e resposta estruturada

- **Status:** em implementação (IA: AC-1…AC-14 e AC-D3 feitos; demais AC-D com DevOps)
- **Módulos:** `src/rag_cognus/chain.py`, `src/rag_cognus/judges.py`,
  `src/rag_cognus/metrics.py`, `src/rag_cognus/evaluation.py`, `src/rag_cognus/api/app.py`,
  `src/rag_cognus/api/schemas.py`, `src/rag_cognus/api/store.py`; DevOps: `config.py`,
  `cli.py`, `.env.example`
- **Testes:** `tests/test_chain.py`, `tests/test_response_metrics.py`,
  `tests/test_evaluation.py`, `tests/test_api.py`, `tests/test_config.py`

## Problema
Os juízes (`judges.py`) e as métricas (`metrics.py`) só rodam em lote (`rag-cognus evaluate`).
`POST /v1/ask` devolve texto e citações, sem nota de qualidade, e não declara
`response_model` (o front recebe um tipo genérico). O Qwen 9B local já leva 24–170 s por
resposta; esperar também o juiz na mesma requisição é inviável. A resposta é um parágrafo
único, difícil de ler no app.

## Comportamento esperado
- `POST /v1/ask` responde assim que a resposta do RAG fica pronta, com `ask_id` e
  `evaluation_status="pending"`. Os juízes rodam em segundo plano no Ollama local
  (`OLLAMA_JUDGE_MODEL`, padrão = modelo de chat).
- `GET /v1/ask/{ask_id}/evaluation` devolve `pending` → `done` (notas + justificativas) ou
  `error` (mensagem curta).
- Cada ask avaliado vira um run no MLflow **local** (experimento próprio), com params,
  métricas e o trace da resposta. MLflow fora do ar não quebra a API.
- A resposta ganha forma estruturada `{resumo, pontos[], recomendacao, fontes[]}`, mantendo
  `response`, `abstained`, `cited_chunk_ids` e `citations` como hoje.

## Métricas online (mesmos nomes do lote)
| Métrica | Origem | Faixa |
|---|---|---|
| 5 critérios de `judges.METRICS` (inclui `groundedness`, `professionalism`) | juiz | 1–5 |
| `quality_score` | `as_dict` (média das cinco) | 1–5 |
| `niche_metadata_precision_proxy` | `score_case` (só com `niche`; senão `null`) | 0–1 |
| `citation_integrity` | `score_case` | 0/1 |
| `latency_seconds` | tempo do `pipeline.predict` medido no `/v1/ask` | s |

Sem `expected_facts` online: `accuracy` compara com os trechos (regra já existente no
prompt do juiz).

## Critérios de aceite — engenheiro de IA
- **AC-1:** `POST /v1/ask` declara `response_model=AskOut` e devolve, além dos campos atuais
  (`response`, `abstained`, `cited_chunk_ids`, `citations`, `trace_id`), `ask_id` (str),
  `evaluation_status` e `structured`. A resposta HTTP é enviada sem chamar o juiz: com um
  juiz fake que bloqueia num `threading.Event`, o `POST` retorna e o status é `pending`.
- **AC-2:** A avaliação é agendada num executor injetável em `Services`
  (`evaluation_runner()`), com **um** worker (Ollama local atende uma requisição por vez).
  Nos testes, um runner síncrono permite checar `done` logo após o `POST`.
- **AC-3:** `GET /v1/ask/{ask_id}/evaluation` devolve `{ask_id, status, metrics, judges,
  judge_model, mlflow_logged, error, created_at, finished_at}`; `judges` é uma lista
  `{name, label, score, reason}` na ordem de `judges.METRICS`; `metrics` contém as chaves
  da tabela acima. `ask_id` desconhecido → 404 "Avaliação não encontrada.".
- **AC-4:** O estado da avaliação é persistido no SQLite do `Store` (tabela nova,
  criada se não existir): reiniciar o `Services` mantém `done`/`error`. Avaliação que
  estava `pending` quando o processo morreu é devolvida como `error` "Avaliação
  interrompida.".
- **AC-5:** Juiz que levanta exceção, devolve JSON inválido ou o Ollama fora do ar →
  `status="error"` e `error` em português, sem traceback; o `POST` já respondido não muda.
- **AC-6:** Abstenção também é avaliada (mesma regra do prompt do juiz); `citation_integrity`
  = 1 para abstenção sem citações.
- **AC-7:** Com avaliação concluída, um run é criado no experimento
  `settings.online_experiment` com `run_name="ask-{ask_id}"`, tags
  `{rag_cognus_online: "true", ask_id, abstained}`, params `chat_model`, `judge_model`,
  `backend`, `top_k`, `niche`, `gold_view` e as métricas da tabela; cada nota do juiz é
  registrada como assessment `LLM_JUDGE` no `trace_id` da resposta (quando houver). Testes
  usam um logger fake injetável (`Services.evaluation_logger()`), sem MLflow real.
- **AC-8:** Se o logger levantar exceção (MLflow fora do ar, URI recusada), então
  `status="done"`, notas preenchidas e `mlflow_logged=false`; com sucesso,
  `mlflow_logged=true`. A URI de tracking passa por `ensure_local_tracking`
  (`databricks://` continua proibido).
- **AC-9:** `chain.Answer` passa a ter `resumo` (str), `pontos` (lista de 0–5 str),
  `recomendacao` (str | null) e `fontes` (lista `{chunk_id, trecho}`), além de `answerable`
  e `cited_chunk_ids`. `structured` na API = `{resumo, pontos, recomendacao, fontes:
  [{chunk_id, titulo, nicho, url, trecho}]}`.
- **AC-10:** `titulo`, `nicho` e `url` vêm dos metadados do chunk recuperado, nunca do LLM.
  `nicho` = nicho pedido se estiver em `nichos_json` do chunk; senão o primeiro da lista;
  senão `null`.
- **AC-11:** `trecho` precisa ser substring literal (espaços normalizados) do texto do
  chunk citado; se não for, é trocado pelos primeiros 240 caracteres do chunk cortados em
  fim de palavra. `fontes` com `chunk_id` fora dos recuperados mantém o erro atual
  ("Modelo citou um ID ausente…").
- **AC-12:** `response` (texto atual) = `resumo` + pontos como lista "- …" +
  "Recomendação: …" quando houver, em português. Abstenção → `structured` =
  `{resumo: ABSTENTION, pontos: [], recomendacao: null, fontes: []}` e `response` =
  `ABSTENTION` (igual a hoje).
- **AC-13:** `rag-cognus ask` e `evaluate` continuam funcionando com o novo `Answer`; o
  lote passa a ler `response` montado em AC-12 (sem mudar nomes de métricas).
- **AC-14:** `RAG_ONLINE_EVAL=false` desliga a avaliação: `POST` devolve
  `evaluation_status="disabled"` e o `GET` responde `status="disabled"` sem chamar juiz
  nem MLflow.

## Critérios de aceite — Parte DevOps (engenheiro-devops)
- **AC-D1:** `Settings` ganha `online_experiment` (`MLFLOW_ONLINE_EXPERIMENT`, padrão
  `rag-cognus-online`) e `online_eval` (`RAG_ONLINE_EVAL`, padrão `true`); `from_env` lê
  ambos; `tracking_uri` segue validado por `ensure_local_tracking`.
- **AC-D2:** `.env.example` documenta, com comentários em português, `MLFLOW_TRACKING_URI`
  (`http://127.0.0.1:5001`), `MLFLOW_EXPERIMENT_NAME`, `MLFLOW_ONLINE_EXPERIMENT`,
  `RAG_ONLINE_EVAL`, `OLLAMA_JUDGE_MODEL` (aviso de viés de autoavaliação) e
  `SPEECH_PLEONASM_LLM` (spec 003). Nenhum valor secreto.
- **AC-D3:** `GET /v1/health` ganha `mlflow: bool | None = None`: `true` se
  `GET {tracking_uri}/health` responde 2xx em ≤ 2 s; `null` para URIs `sqlite:`/`file:`.
  Teste com `httpx` monkeypatched.
- **AC-D4:** `rag-cognus mlflow-check` imprime a URI, se o servidor responde e se os
  experimentos de lote e online existem (criando o online se faltar); sai com código 0 se
  ok e 1 com mensagem "rode `rag-cognus mlflow-local`" se não.
- **AC-D5:** `serve_api` não desliga o tracing para sempre quando o MLflow está fora do ar
  na subida: o logger online tenta de novo a cada avaliação (resultado da checagem de
  saúde em cache por 30 s) e marca `mlflow_logged=false` enquanto falhar.
- **AC-D6:** README ganha uma seção curta "Avaliação online" (como subir o MLflow local,
  onde ver o experimento online, custo extra de latência do juiz).

## Fora de escopo
- Avaliação online dos endpoints `/v1/agents/*`; fila distribuída; reavaliar asks antigos;
  feedback humano (já existe em `/v1/feedback`).

## Impacto esperado nas métricas
- O prompt do gerador muda (saída estruturada e mais tokens): `groundedness`,
  `answer_relevance` e `professionalism` podem variar e a latência deve subir (~+20 a 40%
  de tokens gerados; `num_predict` 600 → 900). Antes de aprovar, rodar
  `rag-cognus evaluate --generate --judge` antes/depois no mesmo snapshot Gold e comparar.
- Juiz igual ao gerador (padrão) superestima notas; recomendar `OLLAMA_JUDGE_MODEL`
  diferente. Trocar de modelo entre resposta e juiz recarrega o Ollama (mais latência).

## Plano (preenchido depois da aprovação)
| Passo | Arquivo | Subagente | Verificação |
|---|---|---|---|
| 1 | `config.py`, `.env.example`, `cli.py`, `/v1/health` | engenheiro-devops | AC-D1…D6 |
| 2 | `tests/test_chain.py` → `chain.py` | engenheiro-ia | AC-9…AC-13 |
| 3 | `tests/test_api.py` → `api/*`, `evaluation.py` | engenheiro-ia | AC-1…AC-8, AC-14 |
