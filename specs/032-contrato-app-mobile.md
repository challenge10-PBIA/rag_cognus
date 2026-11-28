# 032 — Contrato da API para o app mobile

- **Status:** implementado
- **Módulos:** `src/rag_cognus/api/schemas.py`, `src/rag_cognus/api/app.py`, `src/rag_cognus/speech.py`
- **Testes:** `tests/test_api.py`, `tests/test_speech.py`

## Problema
O app mobile (`mobile_cognus`, Expo Go) gera os tipos a partir do `openapi.json` e encontrou
lacunas: as rotas `/v1/agents/*` não declaram resposta; não há nível de evidência para o
selo "EVIDÊNCIA FORTE/MODERADA"; o pilar só tem `label` livre, e o app precisaria comparar
strings em português para escolher a cor; e no Expo Go o Android não grava WAV PCM, só
M4A/AAC (ou 3GP/WebM), que hoje a API recusa com 422.

## Comportamento esperado
O OpenAPI descreve as respostas dos agentes, as respostas trazem um nível de evidência
fechado, cada pilar traz um status para a cor, e a API aceita áudio comprimido além de WAV.

## Critérios de aceite
- **AC-1:** `POST /v1/agents/evidence`, `/communication` e `/pipeline` declaram no OpenAPI os
  modelos `EvidenceOut`, `CommunicationOut` e `PipelineOut`, com os campos que já devolvem.
- **AC-2:** `EvidenceOut.evidence_level` ∈ `forte|moderada|fraca`, vindo da confiança da
  síntese (`alta→forte`, `media→moderada`, `baixa→fraca`).
- **AC-3:** `AskOut.evidence_level` ∈ `forte|moderada|fraca`, por regra determinística:
  abstenção ou nenhuma citação → `fraca`; 1 trecho citado → `fraca`; 2 → `moderada`; 3 ou
  mais → `forte`. O número nunca vem do LLM.
- **AC-4:** cada pilar de `SessionResult` traz `status` ∈ `bom|atencao|critico`, derivado do
  `label` (`ideal`, `equilibradas`, `limpo`, `alto` → `bom`; `frequente`, `baixo` →
  `critico`; demais → `atencao`). Sessões antigas ganham o status ao serem lidas.
- **AC-5:** `POST /v1/sessions` e `POST /v1/speech/transcribe` aceitam M4A/AAC (e outros
  formatos que o PyAV decodifica, como WebM e 3GP): o áudio vira WAV PCM 16-bit mono 16 kHz
  antes da análise, e `GET /v1/sessions/{id}/audio` devolve esse WAV.
- **AC-6:** WAV continua passando sem conversão; bytes que não são áudio dão 422 com
  mensagem em português.
- **AC-7:** o teto padrão de tokens do RAG (`RAG_NUM_PREDICT`) passa de 900 para 1800:
  respostas completas medidas no Qwen3.5 9B usam ~800–1200 tokens e 900 cortava o JSON antes
  de `answerable` (ex.: "Como organizar uma apresentação clara?"). O modelo para sozinho
  (`done_reason=stop`), então respostas curtas não ficam mais lentas.
  `OLLAMA_GENERATOR_NUM_PREDICT` continua tendo precedência.
- **AC-8:** se o JSON do modelo ainda vier cortado (sem `answerable`), `/v1/ask` responde 422
  com "A resposta do modelo veio incompleta: tente de novo." em vez do erro cru do Pydantic.

## Fora de escopo
- Métricas ao vivo durante a gravação (WebSocket/polling).
- Autenticação.

## Plano
| Passo | Arquivo | Verificação |
|---|---|---|
| 1 | `tests/test_api.py`, `tests/test_speech.py` | testes falham por AC-1…AC-6 |
| 2 | `api/schemas.py`, `api/app.py`, `speech.py` | `python hermes/harness/check.py` |
