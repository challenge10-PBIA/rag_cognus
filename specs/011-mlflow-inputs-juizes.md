# 011 — Contrato do trace para os juízes do MLflow (lote, agentes e UI)

- **Status:** implementada (IA, 2026-11-18); pendências no fim
- **Módulos:** IA: `src/rag_cognus/chain.py`, `src/rag_cognus/retrieval.py`,
  `src/rag_cognus/evaluation.py`, `src/rag_cognus/agents/evidence.py`,
  `src/rag_cognus/agents/communication.py`, `src/rag_cognus/agents/pipeline.py`;
  DevOps (spec 012): `src/rag_cognus/cli.py`, `.env.example`
- **Testes:** `tests/test_chain.py`, `tests/test_retrieval.py`, `tests/test_evaluation.py`,
  `tests/test_agents.py`
- **Versões confirmadas:** mlflow 3.18.0, langchain-ollama 1.1.0, ollama-python 0.6.3,
  servidor Ollama 0.32.0 (`litellm` e `openai` não instalados)

## Problema
Os juízes do MLflow 3.18 (built-in, `make_judge` e os criados na UI) leem o trace assim
(código instalado em `.venv`):
- `{{ inputs }}` e `{{ outputs }}` vêm de `root_span.inputs` e `root_span.outputs`
  (`genai/utils/trace_utils.py:103-133`). Os built-in convertem com `parse_inputs_to_str`
  e `parse_outputs_to_str` (`trace_utils.py:686-731`): um dict sem `messages` vira
  `str(dict)` (repr do Python, com aspas simples e `None`). Um dict de saída sem
  `choices`, `messages` ou `output` vira o JSON **inteiro**.
- O contexto vem só dos spans `RETRIEVER` de topo. Cada documento precisa de
  `page_content`, `content` ou `text`. Do resto, só `metadata.doc_uri` é aproveitado
  (`trace_utils.py:799-920`). Sem esse span, `RetrievalGroundedness` falha com "No retrieval
  context found" (`scorers/builtin_scorers.py:795-799`).
- `{{ expectations }}` vem das assessments `expectation` de origem HUMAN. Se faltarem, o
  juiz levanta "Must specify 'expectations'"
  (`judges/instructions_judge/__init__.py:339-350`).

Causas no nosso código:
1. **Saídas gigantes no span raiz.** `RagPipeline.predict` devolve `retrieved_context` com o
   texto completo dos chunks, além de `structured`, `citations` e outros campos
   (`chain.py:169-190`). O agente de evidências devolve `evidence` com o texto de cada
   trecho (`evidence.py:172-178`), e o pipeline aninha os dois resultados
   (`pipeline.py:34`). O juiz recebe dezenas de KB de JSON com o contexto duplicado. Pelo
   endpoint OpenAI-compatível o Ollama não recebe `num_ctx` e usa o contexto padrão do
   servidor. O prompt é cortado pelo **começo**, que é onde fica a pergunta (hipótese
   forte para "inputs não detectados"; confirmar na spec 012).
2. **A resposta não é reconhecida.** O texto final está em `response`
   (`chain.py:170`), `synthesis.summary` (`evidence.py:176`) ou `adapted.adapted_text`
   (`communication.py:114`). Nenhum desses é um formato que o MLflow extrai, então a
   prévia e os juízes built-in veem JSON cru.
3. **Inputs poluídos no lote.** O `predict` decorado (`evaluation.py:111-112`) põe `case_id`
   e `niche=None` no span raiz (`evaluation.py:134`). O `request` dos built-in vira
   `"{'query': ..., 'case_id': 'gold-01', 'niche': None}"`.
4. **Documentos sem identificação.** `retrieve_gold` emite `Document(id, page_content,
   metadata)` (`retrieval.py:121-128`), mas a Gold não tem `doc_uri` (as chaves vistas em
   `.cache/gold.jsonl` são `source_url`, `doc_id`, `chunk_id`…). O contexto do juiz fica só
   com o texto, sem como ligar cada trecho ao `chunk_id` citado. `gather_evidence` emite
   dicts com `text` e sem `metadata` (`evidence.py:103-121`), e seus inputs são uma lista de
   subperguntas.
5. **Comunicação sem contexto.** O trace do `communication_agent`
   (`communication.py:103-118`) não tem span `RETRIEVER`. A fonte de fidelidade
   (`original_text`, `source_claims`) só aparece misturada nos inputs e outputs.
6. **Expectativas.** Só o lote registra expectativas (harness `_get_new_expectations`).
   `_expectations` remove apenas `None` (`evaluation.py:40-42`), e o dataset tem
   `expected_facts: []`, `relevant_chunk_ids: []` e `label_status: "draft"`
   (`data/evaluation/questions.jsonl`). Vão para o juiz listas vazias e um rótulo de
   curadoria como se fossem gabarito. Os traces online e de agentes não têm expectativas.
7. **Spans LLM sem o prompt.** `generate_grounded_answer`, `decompose_topic`,
   `synthesize_evidence` e `adapt_text` (`chain.py:114`, `evidence.py:87,123`,
   `communication.py:87`) registram argumentos Python (lista de documentos, hits), sem
   modelo, papel ou opções (spec 010). O `langchain` não está instalado, então o
   autolog do LangChain que o `mlflow.genai.evaluate` liga nunca entra em ação.

## Comportamento esperado: contrato do trace
| Fluxo | Span raiz (tipo) | `inputs` | `outputs` | Spans `RETRIEVER` de topo | Tags |
|---|---|---|---|---|---|
| RAG (`/v1/ask`, chat, lote) | `rag_cognus` (CHAIN) | `{query, niche}` | `{response, abstained, cited_chunk_ids, fontes}` | 1 (`retrieve_gold`) | `flow=rag`, `chat_model`, `judge_model`; no lote, também `case_id` |
| Só recuperação (lote) | `retrieve_gold` (RETRIEVER) | `{query, niche}` | documentos | 1 | `flow=retrieval`, `case_id` |
| Evidências | `evidence_agent` (AGENT) | `{topic, niche}` | `{response, claims, gaps, confidence, cited_chunk_ids}` | 1 (`gather_evidence`) | `flow=evidence`, `agent=evidence` |
| Comunicação | `communication_agent` (AGENT) | `{text, profile, source_claims}` | `{response, changes, rehearsal_tips, metrics}` | 0 | `flow=communication`, `audience` |
| Pipeline | `evidence_to_audience` (AGENT) | `{topic, profile, niche}` | `{response, evidence_summary, cited_chunk_ids}` | 1 | `flow=pipeline`, `audience` |

Regras:
- `response` é sempre o texto final em português, ou a abstenção. `request_preview` recebe
  a pergunta, o tema ou o texto, e `response_preview` recebe `response`
  (`mlflow.update_current_trace`).
- Documento em span `RETRIEVER`: `{"page_content": str, "metadata": {"doc_uri": str,
  "chunk_id": str, ...}, "id": chunk_id}`. Usar `doc_uri = source_url` e, se não houver,
  `gold://<doc_id>`. A metadata é copiada, nunca alterada no índice.
- **O retorno das funções não muda.** A API, o chat e os scorers do lote continuam
  recebendo o dict completo de hoje. Só o que vai para o span raiz é enxuto (span manual
  com `set_inputs`/`set_outputs`, ou equivalente).
- Spans LLM ganham os atributos `model`, `role` e `options` (spec 010).
- Lote: o `case_id` vai para a coluna `tags` do dataset, e o harness grava a tag no trace.
  As expectativas registradas são só as não vazias. `label_status` vira tag, não
  expectativa.
- Juízes da UI com `{{ expectations }}` só valem no experimento do lote. Os de grounding
  (`RetrievalGroundedness` e afins) só valem com `flow ∈ {rag, evidence, pipeline}`. Os
  filtros da UI usam a tag `flow`.

### Interface com o DevOps (spec 012)
Confirmado no MLflow 3.18 instalado, sem rede:
- `openai:/qwen3.5:9b` → `GatewayAdapter` → `OpenAIProvider`. Lê `OPENAI_API_KEY`
  (obrigatória, qualquer valor) e `OPENAI_API_BASE`. Com
  `OPENAI_API_BASE=http://127.0.0.1:11434/v1` o endpoint é
  `http://127.0.0.1:11434/v1/chat/completions`. **É o URI do contrato**, porque respeita o
  `OLLAMA_BASE_URL`.
- Alternativa sem variável: `ollama:/qwen3.5:9b` → `OllamaProvider`, fixo em
  `http://localhost:11434/v1` e não configurável.
- Modelo padrão dos juízes da UI: `MLFLOW_GENAI_JUDGE_DEFAULT_MODEL`
  (`judges/utils/__init__.py:35-41`). Sem essa variável, o padrão é `openai:/gpt-4.1-mini`.

A IA entrega em `evaluation.py` duas funções puras, que o DevOps consome em
`cli.py mlflow-local`:
- `ui_judge_model_uri(settings) -> "openai:/" + settings.judge`
- `ui_judge_env(settings) -> {"OPENAI_API_BASE": f"{ollama_url}/v1",
  "OPENAI_API_KEY": "ollama", "MLFLOW_GENAI_JUDGE_DEFAULT_MODEL": ui_judge_model_uri(...)}`

Fica para a spec 012 (DevOps): passar esse ambiente ao `mlflow server` sem sobrescrever o
que já estiver definido; subir o Ollama com `OLLAMA_CONTEXT_LENGTH` igual a
`OLLAMA_NUM_CTX` e `OLLAMA_NUM_PARALLEL=1`; verificar como desligar o raciocínio do
qwen3.5 pelo `/v1`.

## Critérios de aceite
Todos sem rede: pipeline, agentes e LLM são fakes, o tracking usa `isolated_tracking`
(sqlite em tmp) e o trace é lido com `mlflow.get_trace(mlflow.get_last_active_trace_id())`.
- **AC-1:** Dado `RagPipeline` com chat fake, quando `predict("pergunta", "clareza_linguagem")`
  roda, então o span raiz tem `inputs == {"query": "pergunta", "niche":
  "clareza_linguagem"}` e `outputs` com exatamente as chaves `response`, `abstained`,
  `cited_chunk_ids` e `fontes`. O valor devolvido continua com `retrieved_context` e todas
  as chaves de hoje.
- **AC-2:** No mesmo trace, `trace.info.request_preview == "pergunta"` e
  `response_preview` é o `response` devolvido. Numa abstenção, é `ABSTENTION`.
- **AC-3:** Para o trace do AC-1, `extract_retrieval_context_from_trace(trace)` devolve um
  span com um item por documento recuperado, `content` não vazio e `doc_uri` igual ao
  `source_url`. Num documento sem `source_url`, `doc_uri == "gold://<doc_id>"`. A
  `metadata` dos documentos do `GoldRetriever` não é alterada.
- **AC-4:** Dado `evaluate(...)` com pipeline fake, quando o run termina, então em cada
  trace o span raiz tem `inputs` sem `case_id`, o trace tem a tag `case_id`, e o
  `per_case.json` continua com `case_id`, `query` e `response`. No modo só recuperação,
  `extract_retrieval_context_from_trace` também devolve contexto.
- **AC-5:** Dado um caso com `expected_facts: []`, `relevant_chunk_ids: []`,
  `should_abstain: null` e `label_status: "draft"`, quando avaliado, então
  `extract_expectations_from_trace` devolve só as expectativas não vazias, sem
  `label_status`, e o trace tem a tag `label_status=draft`.
- **AC-6:** Dado `EvidenceAgent` com fakes, quando `run(tema)` roda, então o span raiz
  tem `inputs == {"topic", "niche"}` e `outputs` com `response` (resumo mais afirmações)
  e `cited_chunk_ids`. `gather_evidence` emite documentos no formato do contrato, com
  `metadata.chunk_id`, `metadata.doc_uri` e `metadata.subquestion`.
  `extract_retrieval_context_from_trace` não volta vazio. O dict devolvido não muda.
- **AC-7:** Dado `CommunicationAgent` com chat fake, quando `run(texto, perfil, [claims])`
  roda, então o span raiz tem `inputs` com `text`, `profile` (dict) e `source_claims`,
  `outputs.response == adapted_text`, a tag `flow=communication`, e não há span
  `RETRIEVER`.
- **AC-8:** Dado `EvidenceToAudience` com fakes, quando `run` roda, então o span raiz tem
  `inputs` com `topic`, `profile` e `niche`, `outputs.response` é o texto adaptado, há
  exatamente um span `RETRIEVER` de topo e a tag `flow` vale `pipeline` (não é
  sobrescrita pelos agentes filhos).
- **AC-9:** Para os traces dos AC-1, 6, 7 e 8, `resolve_inputs_from_trace(None, trace)` e
  `resolve_outputs_from_trace(None, trace)` devolvem dicts não vazios.
  `extract_request_from_trace(trace)` contém o texto da pergunta, do tema ou do texto, e
  `extract_response_from_trace(trace)` contém o `response`. Todos os traces têm as tags
  `flow`, `chat_model` e `judge_model`.
- **AC-10:** Nos traces do AC-1 e do AC-6, os spans LLM têm os atributos `model`, `role` e
  `options` (dict), com os valores de `ollama_options` da spec 010.
- **AC-11:** Dado `Settings(ollama_url="http://127.0.0.1:11434")`, então
  `ui_judge_model_uri(settings) == "openai:/qwen3.5:9b"`, ou `"openai:/<judge_model>"`
  quando `OLLAMA_JUDGE_MODEL` está preenchido. Com `ui_judge_env(settings)` aplicado por
  monkeypatch, `mlflow.genai.judges.utils.get_default_model()` devolve esse URI,
  `get_adapter(uri, "x")` é `GatewayAdapter`, e
  `_get_provider_instance("openai", model).get_endpoint_url("llm/v1/chat") ==
  "http://127.0.0.1:11434/v1/chat/completions"`. Nada faz chamada HTTP.
- **AC-12:** Dado um pipeline fake que levanta exceção, quando `evaluate` roda, então o
  caso devolve `{"error": ...}` aos scorers (como hoje), o trace do caso fica com o estado
  ERROR e tem a tag `error=true`.

## Impacto nas métricas
- Nossas métricas de lote e online: **nenhum**. Os scorers continuam recebendo o dict
  completo devolvido pelo `predict`, e `per_case.json` não muda (AC-4).
- Juízes da UI e built-in sobre os traces: as notas mudam porque passam a ver pergunta,
  resposta e contexto corretos. Elas não são comparáveis com as notas anteriores a esta
  spec.
- Expectativas vazias deixam de ir para o `Correctness` e afins, então menos falsos
  negativos.

## Fora de escopo
- Subir o servidor, o ambiente do `mlflow server` e o contexto do Ollama (spec 012, DevOps).
- Criar juízes na UI e registrar scorers (`mlflow.genai.scorers`) automaticamente.
- Autolog do LangChain: exige o pacote `langchain`, que não é dependência do projeto.
- Mudar o dataset em `data/` (o filtro de vazios acontece no código).

## Plano (preenchido depois da aprovação)
| Passo | Arquivo | Subagente | Verificação |
|---|---|---|---|
| 1 | `tests/test_chain.py`, `tests/test_retrieval.py` | engenheiro-ia | AC-1, AC-2, AC-3 vermelhos |
| 2 | `retrieval.py` (`doc_uri`), `chain.py` (span raiz enxuto, prévias, tags) | engenheiro-ia | AC-1, AC-2, AC-3, AC-9, AC-10 |
| 3 | `tests/test_evaluation.py`, `evaluation.py` | engenheiro-ia | AC-4, AC-5, AC-11, AC-12 |
| 4 | `tests/test_agents.py`, `agents/*.py` | engenheiro-ia | AC-6, AC-7, AC-8, AC-10 |
| 5 | `cli.py`, `.env.example` (spec 012) | engenheiro-devops | consome `ui_judge_env` |
| 6 | — | líder | `python hermes/harness/check.py` |

## Pendências (após a implementação da IA)
- AC-9: `extract_response_from_trace` devolve o dict de saída como JSON com escape ASCII
  (`ó` vira `ó`, em `parse_outputs_to_str`). O `response` está lá, mas escapado, e os
  testes decodificam o JSON para comparar. Por decisão do líder, ficou o dict enxuto. Se as
  notas dos juízes built-in em português piorarem, a alternativa é o span raiz devolver só
  a string `response`.
- O `retrieved_context` devolvido passa a ter `metadata.doc_uri`, que é a única mudança
  visível no retorno.
- `relevant_chunk_ids` e `should_abstain` só viram expectativa com
  `label_status == "human_verified"`. As métricas do lote não mudam, porque `score_case` já
  ignorava esses campos em rascunho.
- A verificação manual na UI do MLflow, com Ollama e `mlflow server` no ar, depende da
  spec 012 (DevOps).
