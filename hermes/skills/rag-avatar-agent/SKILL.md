---
name: rag-avatar-agent
description: Papel [avatar] no rag_cognus. Use ao alterar o agente de comunicação via avatar — o mascote coach que dá dicas por tela e explica métricas com fatos do backend (coach.py, /v1/mascot/*). Traz o contrato real, a guarda de números, o trace no MLflow e como testar sem rede.
---

# Agente de comunicação via avatar (mascote coach)

O agente **já está no repo** como o mascote coach (spec `specs/013-mascote-coach-dicas.md`).
O papel dele (tom, regras, fontes) está em `hermes/agents/communication-agent.md`; o código é a
fonte da verdade. Mude o comportamento pela spec 013 (SDD → TDD → harness), nunca só o prompt.

## Objetivo
Falar com a pessoa por meio do mascote: dicas curtas por tela (regras, sem LLM) e explicações
"Me explica…" de tópicos fechados, escritas pelo LLM a partir de **fatos calculados pelo
backend**. O avatar **não cria conteúdo nem número**: só traduz o que recebeu.

## Onde está o código
- Agente e regras: `src/rag_cognus/coach.py` — `TOPICS`, `GLOSSARY`, `tips()`, `topics()`,
  `facts()`, `grounded()` (guarda de números), `rules_text()`, `MascotCoach.explain()`.
- Rotas: `src/rag_cognus/api/app.py` — `GET /v1/mascot/tips`, `GET /v1/mascot/topics`,
  `POST /v1/mascot/explain`, `GET/PUT /v1/mascot/settings`; esquemas em
  `src/rag_cognus/api/schemas.py`; preferência em `app_state` (`src/rag_cognus/api/store.py`).
- Aparência do mascote (spec 008): `src/rag_cognus/mascot.py` (`options()`, `normalize()`).
- Onboarding guiado pelo mascote: `specs/014-onboarding-guiado.md` (`/v1/onboarding`,
  `/v1/privacy`).
- Adaptação de texto ao público (outro agente, não o mascote):
  `src/rag_cognus/agents/communication.py`.
- Testes: `tests/test_coach.py` (regras, guarda, trace) e `tests/test_api.py` (rotas).
- Front (repo `frontend_UI`, fora deste): dock do mascote, painel "Me explica…" e o
  contexto da tela (`ask_id` em Pergunte ao Cognus).

## Contrato
- Entrada do LLM: tópico + definição do glossário + fatos `[{label, value}]`.
- Saída do LLM: `{"text": "até 3 frases", "mood": "feliz" | "neutro" | "pensativo"}`.
- Saída da API: `{topic, text, mood, facts, source: "llm" | "regras", trace_id}`.
- Guarda: número no `text` que não esteja nos fatos/glossário, texto vazio, > 600 caracteres
  ou falha do Ollama → explicação por regras (`source="regras"`), HTTP 200.
- LLM no papel `fast` (spec 010: `make_ollama(..., role="fast")`, opções do `.env`).

## Trace no MLflow (spec 011)
Span raiz `mascot_agent` (AGENT), `inputs={topic, facts}`,
`outputs={response, mood, source}`; span `mascot_explain` (LLM) com `model`, `role=fast`,
`options`. Tags: `flow=mascot`, `agent=mascot`, `topic`, `mascot_source`, `chat_model`,
`judge_model`. A taxa de `mascot_source=regras` é o sinal que o papel `[obs]` acompanha.

## Próximo passo (a criar)
- Relatórios diário/semanal/mensal do mascote: `specs/016-mascote-relatorios.md` (a criar;
  número sugerido) — números por fórmula em Python, narrativa por este agente, mesma guarda.

## Como testar sem rede
- Siga a skill `rag-tdd`. LLM falso: `RunnableLambda` devolvendo `AIMessage` com JSON fixo
  (veja `fake_chat` em `tests/test_coach.py`). Nunca chame Ollama ou MLflow reais.
- Todo texto novo do LLM precisa de teste de que número inventado cai para regras.

## Verificação
- `.venv/bin/python -m pytest -q tests/test_coach.py tests/test_api.py -k mascot`
- `python hermes/harness/check.py` → precisa terminar em `HARNESS OK`.

## Retorno
`STATUS | ARQUIVOS | TESTES | HARNESS (última linha) | CONTRATO/IMPACTO | PENDÊNCIAS`.
Estudo: `docs/estudos/agente-avatar.md`.
