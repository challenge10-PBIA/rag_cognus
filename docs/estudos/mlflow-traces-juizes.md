# Traces que os juízes do MLflow conseguem ler (spec 011)

Material de estudo: como os juízes do MLflow 3.18 leem um trace, o que estava errado nos
nossos traces, o que mudou e como verificar. Spec: `specs/011-mlflow-inputs-juizes.md`.

## 1. Como um juiz do MLflow lê um trace
Os juízes built-in, os criados com `make_judge` e os criados na UI usam o mesmo caminho
(`mlflow/genai/utils/trace_utils.py`):
- **Pergunta e resposta** (`{{ inputs }}`, `{{ outputs }}`) vêm dos `inputs` e `outputs` do
  **span raiz**.
  - Um dict de entrada sem `messages` vira `str(dict)`.
  - Um dict de saída sem `choices`, `messages` ou `output` vira **o JSON inteiro**, com
    escape ASCII (`ó` vira `ó`).
- **Contexto** vem só dos spans do tipo `RETRIEVER` "de topo", ou seja, que não estão dentro
  de outro `RETRIEVER`. Cada documento precisa de `page_content`, `content` ou `text`. Da
  metadata, só `doc_uri` é aproveitado. Sem esse span, `RetrievalGroundedness` falha com
  "No retrieval context found".
- **Gabarito** (`{{ expectations }}`) vem das assessments do tipo expectation, que só o lote
  registra.

## 2. O que estava errado
1. O span raiz guardava o dict de retorno inteiro: o texto completo dos chunks, `structured`,
   `citations` etc. O juiz recebia dezenas de KB e o Ollama, pelo endpoint
   OpenAI-compatível, cortava o prompt pelo começo, que é onde está a pergunta.
2. A resposta ficava em chaves que o MLflow não reconhece.
3. No lote, `case_id` e `niche=None` iam para os inputs do span raiz.
4. Os documentos do span `RETRIEVER` não tinham `doc_uri`.
5. Iam para o juiz expectativas vazias (`[]`) e o `label_status`, como se fossem gabarito.
6. Os spans LLM não diziam modelo, papel nem opções.

## 3. Contrato novo
| Fluxo | Span raiz | `inputs` | `outputs` | `RETRIEVER` de topo | Tags |
|---|---|---|---|---|---|
| RAG (API, chat, lote) | `rag_cognus` (CHAIN) | `{query, niche}` | `{response, abstained, cited_chunk_ids, fontes}` | 1 (`retrieve_gold`) | `flow=rag`, `chat_model`, `judge_model`; no lote, também `case_id` e `label_status` |
| Só recuperação (lote) | `retrieve_gold` (RETRIEVER) | `{query, niche}` | documentos | 1 | `flow=retrieval`, `case_id` |
| Evidências | `evidence_agent` (AGENT) | `{topic, niche}` | `{response, claims, gaps, confidence, cited_chunk_ids}` | 1 (`gather_evidence`) | `flow=evidence`, `agent=evidence` |
| Comunicação | `communication_agent` (AGENT) | `{text, profile, source_claims}` | `{response, changes, rehearsal_tips, metrics}` | 0 | `flow=communication`, `audience` |
| Pipeline | `evidence_to_audience` (AGENT) | `{topic, profile, niche}` | `{response, evidence_summary, cited_chunk_ids}` | 1 | `flow=pipeline`, `audience` |

Pontos importantes:
- **O retorno das funções não mudou.** A API, o chat e os scorers do lote recebem o dict
  completo de antes. Só o que vai para o span raiz ficou enxuto (`mlflow.start_span` com
  `set_inputs`/`set_outputs` no lugar do decorador `@mlflow.trace`). A única diferença
  visível no retorno é a chave `doc_uri` dentro da `metadata` de `retrieved_context`.
- `response` é sempre o texto final em português, ou a abstenção.
- As prévias da lista de traces (`request_preview` e `response_preview`) mostram a pergunta
  e a resposta em texto, sem o JSON.
- Documento no span `RETRIEVER`: `{"page_content", "metadata": {"doc_uri", "chunk_id", ...},
  "id"}`. O `doc_uri` é a `source_url` e, sem ela, `gold://<doc_id>`. A metadata é copiada,
  e o índice nunca é alterado.
- Spans LLM têm os atributos `model`, `role` e `options` (veja `docs/estudos/llm-config.md`).
- Se o RAG falha, o trace fica com estado `ERROR` e a tag `error=true`. No lote, isso vale
  também quando um pipeline sem trace levanta exceção.

## 4. Lote (`rag-cognus evaluate`)
- O `predict` do lote não tem mais `@mlflow.trace`, então o span raiz é o do próprio
  `RagPipeline` (ou o `retrieve_gold`). Se o pipeline não gerar trace (um fake, por exemplo),
  o `mlflow.genai.evaluate` cria um span `predict` automaticamente.
- O `case_id` vai na coluna `tags` do dataset, e o MLflow grava a tag no trace.
- Expectativas: só as não vazias. `relevant_chunk_ids` e `should_abstain` só entram quando
  `label_status == "human_verified"`, porque rascunho não é gabarito. O `label_status` vira
  tag. As nossas métricas determinísticas não mudam: os scorers recebem as mesmas
  referências revisadas de antes.
- Params novos do run: `generator_options`, `judge_options` e `judge_is_generator`.

## 5. Juízes da UI apontando para o Ollama
Em `src/rag_cognus/evaluation.py`, duas funções puras para o DevOps usar no
`rag-cognus mlflow-local` (spec 012):
- `ui_judge_model_uri(settings)` devolve `"openai:/" + settings.judge`, por exemplo
  `openai:/qwen3.5:9b`.
- `ui_judge_env(settings)` devolve:
  - `OPENAI_API_BASE`: o `OLLAMA_BASE_URL` terminado em exatamente um `/v1`;
  - `OPENAI_API_KEY=ollama` (o Ollama ignora, mas o provedor exige);
  - `MLFLOW_GENAI_JUDGE_DEFAULT_MODEL`: o URI acima.

Com esse ambiente no `mlflow server`, os juízes da UI chegam a
`http://127.0.0.1:11434/v1/chat/completions` (provedor OpenAI do gateway do MLflow, sem
`litellm`).

## 6. Como verificar no MLflow local
1. Faça uma pergunta pela API ou pelo chat, ou rode `rag-cognus evaluate`.
2. Em **Traces**, as colunas Request e Response mostram a pergunta e a resposta em texto.
3. Abra o trace. O span raiz deve ter exatamente as chaves do contrato e o span
   `retrieve_gold` deve ter documentos com `metadata.doc_uri`.
4. Filtre pela tag `flow` (por exemplo `tags.flow = 'rag'`) antes de aplicar juízes de
   grounding. Juízes com `{{ expectations }}` só fazem sentido no experimento do lote.
5. Em um run do lote, a aba de avaliação deve mostrar só expectativas preenchidas, e cada
   trace deve ter as tags `case_id` e `label_status`.

## 7. Limites conhecidos
- O JSON de saída chega aos juízes built-in com escape ASCII (`ó`). O texto continua
  legível para o modelo, mas fica mais longo. A alternativa seria o span raiz devolver só a
  string `response`, o que perde `abstained` e `cited_chunk_ids`. Por decisão do líder,
  ficou o dict enxuto.
- O corte do prompt pelo começo depende do `OLLAMA_CONTEXT_LENGTH` do servidor (spec 012).
