# 036 — Tracing MLflow completo do cenário pitch

- **Status:** implementado
- **Módulos:** `src/rag_cognus/config.py`, `src/rag_cognus/evaluation.py`,
  `src/rag_cognus/api/app.py`, `src/rag_cognus/scenarios/pitch.py`,
  `src/rag_cognus/agents/communication.py`, `.env.example`
- **Testes:** `tests/test_evaluation.py`, `tests/test_api.py`, `tests/test_config.py`

## Problema
Os traces do cenário pitch (spec 035) chegam ao MLflow local só com os spans manuais: as
chamadas LangChain/ChatOllama não aparecem (sem `mlflow.langchain.autolog()`), não há
tokens, o experimento só é escolhido pelo nome (o experimento `rag-cognus-pitch` já existe
com ID 2), o pitch e a rodada de objeção não ficam ligados numa conversa e as prévias da
lista de traces mostram só o começo da transcrição.

## Comportamento esperado
Na aba Traces do MLflow local, cada avaliação de cenário aparece no experimento configurado
(por ID ou nome), com a árvore LangChain completa e tokens; pitch e objeção ficam na mesma
sessão; a lista mostra "produto · comprador · fala" e "veredito · n/5 · objeção".

## Critérios de aceite
- **AC-1:** Dado `MLFLOW_EXPERIMENT_ID` preenchido, quando `configure_tracking` roda, então
  usa `mlflow.set_experiment(experiment_id=...)` e ignora o nome; vazio mantém o nome
  (`MLFLOW_EXPERIMENT_NAME`). Documentado em `.env.example`.
- **AC-2:** `configure_tracking` liga `mlflow.langchain.autolog()`; as chamadas LangChain
  feitas dentro de um span manual viram filhos desse trace (um trace só, sem trace novo).
- **AC-3:** O trace de `run_scenario_evaluation` grava `session_id` = id da sessão do pitch;
  na rodada de objeção, o `objecao_de` (sessão do pitch original). O trace do
  CommunicationAgent da sessão usa o mesmo id da conversa, sem mudar o contrato da resposta.
- **AC-4:** O trace do cenário tem metadata imutável vinda da config: `chat_model`,
  `judge_model`, `retriever` e `tracking` (URI local). Nada de segredo.
- **AC-5:** `request_preview` = produto · comprador · início da fala (objeção: objeção ·
  início da fala); `response_preview` = `veredito · n/5 · objeção` (objeção:
  `respondida|não respondida · motivo`). Ambos curtos (≤ 200 caracteres).

## Fora de escopo
- Custo em moeda: modelo local no Ollama não tem preço; não se inventa custo.
- Autolog quando o MLflow está fora do ar na subida da API (`cli.py` só fixa a URI).
- Variável de "ambiente" (dev/prod): não existe na config; não é criada.

## Plano (preenchido depois da aprovação)
| Passo | Arquivo | Subagente | Verificação |
|---|---|---|---|
| 1 | `tests/test_evaluation.py`, `tests/test_api.py`, `tests/test_config.py` | engenheiro-ia | testes falham por AC-1..AC-5 |
| 2 | `config.py`, `evaluation.py`, `api/app.py`, `scenarios/pitch.py`, `agents/communication.py` | engenheiro-ia | `python hermes/harness/check.py` |
| 3 | MLflow local (experimento 2) | engenheiro-ia | trace real de pitch + objeção lido com `mlflow.get_trace` |
