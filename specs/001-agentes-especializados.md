# 001 — Agentes de evidências e de adaptação ao público

- **Status:** implementado
- **Módulos:** `src/rag_cognus/config.py`, `src/rag_cognus/llm.py`, `src/rag_cognus/agents/`,
  `src/rag_cognus/agents_ui.py`, `src/rag_cognus/chat_app.py`, `src/rag_cognus/cli.py`
- **Testes:** `tests/test_config.py`, `tests/test_agents.py`, `tests/test_chat_app.py`

## Problema
O RAG responde uma pergunta por vez, com uma única busca. O produto (treino de cognição e de
apresentação em público) precisa de: (1) consolidar o que a base diz sobre um tema amplo,
com consensos, conflitos e lacunas; (2) transformar conteúdo — ou a fala do próprio usuário —
para um público e um tempo de fala. Além disso, `num_ctx` fixo e diferente entre chamadas faz
o Ollama recarregar o modelo, deixando tudo lento.

## Comportamento esperado
- **Agente de evidências:** recebe um tema, quebra em até 4 subperguntas (modelo leve), busca
  na Gold por subpergunta e devolve uma síntese com afirmações citadas, conflitos, lacunas e
  confiança. Nunca aceita citação de trecho não recuperado.
- **Agente de comunicação:** recebe um texto (digitado, gravado ou vindo do agente de
  evidências) e um perfil (público, contexto, minutos, tom) e devolve a versão adaptada, o que
  mudou, dicas de ensaio e métricas objetivas (palavras, tempo estimado, legibilidade).
- **Pipeline:** tema → evidências → texto adaptado ao público.
- Os dois aparecem no Streamlit (aba **🧠 Agentes**) e na CLI (`synthesize`, `adapt`); cada
  execução vira um trace `AGENT` no MLflow com a tag `agent`, e as notas do juiz viram feedback.
- Configuração no `.env`: `OLLAMA_NUM_CTX`, `OLLAMA_KEEP_ALIVE`, `OLLAMA_FAST_MODEL`.

## Critérios de aceite
- **AC-1:** `Settings.from_env` lê `OLLAMA_NUM_CTX` (padrão 16384), `OLLAMA_KEEP_ALIVE`
  (padrão `30m`) e `OLLAMA_FAST_MODEL` (vazio = modelo do chat); `num_ctx < 2048` é recusado.
- **AC-2:** Tema curto e simples não chama o modelo de decomposição; usa o próprio tema.
- **AC-3:** Tema composto vira 1–4 subperguntas sem duplicatas; saída inválida do modelo
  volta para o tema original.
- **AC-4:** A busca por subpergunta não repete `chunk_id` e respeita o limite total de trechos.
- **AC-5:** Sem nenhum trecho recuperado, a síntese não chama o LLM, tem confiança `baixa` e
  lista as subperguntas como lacunas.
- **AC-6:** Afirmações que citam IDs fora dos trechos recuperados têm esses IDs removidos; sem
  ID válido, a afirmação é descartada e contada em `discarded_claims`.
- **AC-7:** Subpergunta sem trecho recuperado aparece em `gaps`.
- **AC-8:** O agente de comunicação recusa texto vazio e devolve métricas determinísticas:
  palavras, frases, média de palavras por frase, minutos estimados (150 palavras/min),
  desvio do tempo-alvo e legibilidade (Flesch adaptado ao português).
- **AC-9:** O pipeline entrega ao agente de comunicação o resumo e as afirmações da síntese e
  as afirmações como `source_claims` (para o juiz de fidelidade).
- **AC-10:** Os juízes dos agentes devolvem 3 notas 1–5 com motivo e a média
  (`evidence_score` / `communication_score`).
- **AC-11:** Cada execução gera um trace persistido no MLflow com span raiz `AGENT` e tag
  `agent=evidence|communication|pipeline`.
- **AC-12:** O app mostra a aba **🧠 Agentes** e executa síntese e adaptação com modelos falsos.

## Fora de escopo
- Avaliação em lote dos agentes (`evaluate-agents` + datasets) — próxima spec.
- Memória de longo prazo do usuário e histórico de ensaios.
- Fine-tuning; LangGraph (o grafo é Python puro com spans manuais).

## Plano
| Passo | Arquivo | Verificação |
|---|---|---|
| 1 | `tests/test_config.py`, `tests/test_agents.py` | testes falham por AC-1…AC-11 |
| 2 | `config.py`, `llm.py`, `chain.py`, `judges.py` | AC-1 verde |
| 3 | `agents/schemas.py`, `evidence.py`, `communication.py`, `pipeline.py`, `agents_judges.py` | AC-2…AC-11 verdes |
| 4 | `agents_ui.py`, `chat_app.py`, `cli.py`, `tests/test_chat_app.py` | AC-12 + `python hermes/harness/check.py` |
