# 002 — API do produto: sessões de fala, progresso e agentes

- **Status:** implementado
- **Módulos:** `src/rag_cognus/api/`, `src/rag_cognus/speech.py`, `src/rag_cognus/speech_analysis.py`,
  `src/rag_cognus/progress.py`, `src/rag_cognus/cli.py`
- **Testes:** `tests/test_speech_analysis.py`, `tests/test_progress.py`, `tests/test_api.py`
- **Plano de produto:** [docs/plano-frontend.md](../docs/plano-frontend.md)

## Problema
O front web (repo `frontend_UI`) precisa de uma API HTTP. Hoje só o Streamlit usa o RAG, os
agentes e a voz, chamando Python direto. As telas pedem também o que não existe: análise
acústica da fala, histórico de sessões, índice, streak, conquistas, desafios e hábitos.

## Comportamento esperado
- `rag-cognus api` sobe a API em `http://127.0.0.1:8000` (OpenAPI em `/docs`), CORS só para
  o front local.
- O usuário grava uma sessão (WAV 16-bit) num modo; a API transcreve com timestamps por palavra,
  calcula 4 pilares (ritmo, pausas, vícios, clareza) e o índice geral, gera recomendações (regras
  + fontes da Gold) e, se o Ollama responder, a versão adaptada do agente de comunicação.
- Números (índice, pilares, streak, conquistas) vêm de fórmulas, nunca do LLM.
- Ansiedade não é medida: o usuário informa (1–5) antes/depois; "calma" deriva disso.

## Critérios de aceite
- **AC-1:** Ritmo = palavras (sem vícios) por minuto de fala; nota 100 entre 120–160 ppm,
  −2 por ppm fora da faixa.
- **AC-2:** Pausas = intervalos de 0,4–2 s entre palavras; silêncios > 3 s contam à parte e
  penalizam; nota 100 com 3–8 pausas/min.
- **AC-3:** Vícios: formas alongadas de "é" (éé, ééh, eh), hã/hum/hmm, "tipo" e "né"; `value`
  = % da fala livre; nota = 100 − 5 × taxa (%).
- **AC-4:** Clareza = legibilidade (Flesch PT) e, se houver, nota de clareza do juiz; índice
  geral = média arredondada dos 4 pilares.
- **AC-5:** Dicção = probabilidade média das palavras do Whisper (0–100).
- **AC-6:** Progresso: streak de dias consecutivos (até hoje ou ontem), meta diária em minutos,
  barras por período (semana = 7 dias, mês = 4 semanas, trimestre = 12 semanas), variação do
  índice vs. período anterior, nível e conquistas.
- **AC-7:** Desafios do dia priorizam o pilar mais fraco das últimas sessões **até ontem**
  (a lista não muda durante o dia) e ficam concluídos quando há sessão hoje com aquele
  `challenge_id`.
- **AC-8:** `POST /v1/sessions` salva áudio e resultado; `GET /v1/sessions/{id}` devolve o
  mesmo resultado; falha do LLM não impede a análise (sem `adapted`).
- **AC-9:** `/v1/ask` e `/v1/agents/*` respondem 503 com mensagem clara sem snapshot da Gold.
- **AC-10:** `/v1/home`, `/v1/progress`, `/v1/habits`, `/v1/profile`, `/v1/meta` e
  `/v1/feedback` funcionam sem Ollama.

## Fora de escopo
- Sessão ao vivo por WebSocket (spec futura), entonação por F0 (`parselmouth`), login.

## Plano
| Passo | Arquivo | Verificação |
|---|---|---|
| 1 | `tests/test_speech_analysis.py`, `tests/test_progress.py`, `tests/test_api.py` | vermelhos |
| 2 | `speech.py` (palavras + timestamps), `speech_analysis.py` | AC-1…AC-5 |
| 3 | `api/store.py`, `progress.py` | AC-6, AC-7 |
| 4 | `api/app.py`, `cli.py` | AC-8…AC-10 + harness |
