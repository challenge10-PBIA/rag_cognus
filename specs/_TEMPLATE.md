# NNN — Título curto

- **Status:** rascunho | aprovado | implementado
- **Módulos:** `src/rag_cognus/...`
- **Testes:** `tests/test_....py`

## Problema
O que está errado ou faltando, em 2–4 frases. Inclua exemplo de entrada/saída se houver.

## Comportamento esperado
O que muda para quem usa (CLI, chat, métricas). Sem detalhes de implementação.

## Critérios de aceite
- **AC-1:** Dado …, quando …, então ….
- **AC-2:** …

## Fora de escopo
- …

## Plano (preenchido depois da aprovação)
| Passo | Arquivo | Subagente | Verificação |
|---|---|---|---|
| 1 | `tests/test_x.py` | test-writer | teste falha por AC-1 |
| 2 | `src/rag_cognus/x.py` | implementer | `python hermes/harness/check.py --changed` |
