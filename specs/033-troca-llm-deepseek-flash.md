# 033 — Troca do LLM local para `eriktonon/deepseek-v4.1-flash-1017:latest`

- **Status:** implementado (2026-11-27)
- **Módulos:** `src/rag_cognus/config.py`, `src/rag_cognus/llm.py`, `.env.example`, `Modelfile`,
  `hermes/config.yaml`
- **Testes:** `tests/test_config.py`
- **Relacionadas:** 010 (opções por papel), 032 (citações no app mobile)

## Problema
O modelo local passou de `qwen3.5:9b` para `eriktonon/deepseek-v4.1-flash-1017:latest` (fine-tune
de 9B sobre a mesma base Qwen3.5, Q4_K_M; `qwen3.5:9b` e `qwen3.5:4b` não estão mais no Ollama).
Com o novo modelo o `/v1/ask` falhava em 4 de 4 perguntas reais com "Resposta sem fontes": o
JSON schema enviado ao Ollama (`format`) deixava `fontes` e `cited_chunk_ids` opcionais (têm
default no Pydantic) e o modelo os omitia. O Hermes apontava para a tag `:9b`, que não existe.

## Comportamento esperado
O app usa o novo modelo por padrão, também nas etapas leves (sem `qwen3.5:4b`). Toda saída
estruturada obriga o modelo a preencher todos os campos do schema, inclusive os que têm default
no Pydantic; a validação no Python continua a mesma.

## Critérios de aceite
- **AC-1:** Sem `OLLAMA_CHAT_MODEL`, o modelo padrão é `eriktonon/deepseek-v4.1-flash-1017:latest`;
  `.env.example` usa esse modelo e deixa `OLLAMA_FAST_MODEL` vazio.
- **AC-2:** O `format` de `make_ollama` lista em `required` todas as propriedades do schema e
  dos modelos aninhados (`$defs`), sem alterar o schema do Pydantic.
- **AC-3:** `hermes/config.yaml` aponta para a tag `:latest` instalada.

## Verificação manual (Ollama real, fora dos testes)
- Antes: 4/4 perguntas sem citação. Depois: 4/4 com 1–2 `chunk_id` válidos (38–62 s cada no M4).
- Agente de comunicação: JSON válido em ~20 s. Juiz: JSON válido em ~14 s.

## Fora de escopo
- Encurtar os `chunk_id` (hash de 64 caracteres) para reduzir latência.
- Juiz independente (`OLLAMA_JUDGE_MODEL`): continua o mesmo modelo do chat.
