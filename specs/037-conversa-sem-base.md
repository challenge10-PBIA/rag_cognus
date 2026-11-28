# 037 — Conversa casual sem a base de conhecimento

- **Status:** implementado (2026-11-27)
- **Módulos:** novo `src/rag_cognus/small_talk.py`; `src/rag_cognus/chain.py` (`RagPipeline`);
  `src/rag_cognus/api/app.py` (`/v1/ask`); `src/rag_cognus/api/schemas.py` (`AskOut.kind`)
- **Testes:** novo `tests/test_small_talk.py`, `tests/test_api.py`
- **Relacionadas:** 004 (avaliação online), 032 (contrato mobile)

## Problema
Toda mensagem do chat e do assistente de voz vai para o RAG. Frases do dia a dia ("opa eae
fera", "tá me ouvindo?", "valeu!") viram busca na base: o modelo tenta citar trechos que não têm
relação, demora 30–60 s, cai em "sem evidência suficiente" e ainda dispara o juiz online.

## Comportamento esperado
Saudação, agradecimento, despedida, teste de áudio ("tá me ouvindo?") e perguntas sobre o
próprio assistente ("quem é você?") recebem uma resposta curta e amigável do modelo, sem
recuperação, sem citações e sem juiz. Se a mensagem traz qualquer pedido de conteúdo ("bom dia,
como melhorar minha voz?"), segue para o RAG como hoje.

A detecção é por regra (sem chamada extra ao LLM): mensagem curta em que **todas** as palavras
pertencem a um vocabulário fechado de conversa. Na dúvida, vai para o RAG.

## Critérios de aceite
- **AC-1:** `is_small_talk` reconhece saudações, gírias e testes de áudio (ex.: "opa eae fera",
  "tá me ouvindo?", "bom dia!", "valeu mano", "quem é você?") e recusa pedidos de conteúdo
  (ex.: "como melhorar minha voz?", "bom dia, como parar de falar né?", "o que é dicção?").
- **AC-2:** Conversa casual não chama o retriever nem o LLM do RAG; o resultado tem a mesma forma
  do RAG, com `kind="conversa"`, `abstained=false`, sem citações nem fontes e `structured.resumo`
  igual à resposta.
- **AC-3:** A resposta vem do modelo (papel rápido, prompt curto e amigável, em português); se o
  modelo falhar, usa uma resposta fixa amigável, sem erro para o usuário.
- **AC-4:** `/v1/ask` devolve `kind` (`rag` | `conversa`); na conversa, `evaluation_status` é
  `disabled` e o juiz online não roda.
- **AC-5:** O trace no MLflow tem `flow=conversa`.

## Fora de escopo
- Classificação por LLM ou embeddings (fica para quando a regra errar na prática).
- Memória de conversa entre mensagens.
