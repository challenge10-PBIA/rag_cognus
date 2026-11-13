---
name: rag-harness
description: Como verificar mudanças no rag_cognus (lint, formato, testes) e interpretar a saída do harness. Use antes de declarar uma tarefa concluída ou quando o harness falhar.
---

# Harness de verificação

| Situação | Comando |
|---|---|
| Durante a edição | `python hermes/harness/check.py --changed` |
| Antes de concluir | `python hermes/harness/check.py` |
| Um teste específico | `python hermes/harness/check.py --no-lint tests/test_x.py -k nome` |

Saída: uma linha `[PASS]/[FAIL] etapa` por etapa; em falha, as últimas 40 linhas.
Última linha: `HARNESS OK` ou `HARNESS FALHOU`.

## Quando falhar
1. `ruff-format` → rode `.venv/bin/python -m ruff format src tests hermes` e repita.
2. `ruff-check` → corrija o arquivo:linha indicado (o hook pós-edição já aplica `--fix`).
3. `pytest` → leia o **primeiro** traceback; abra só o arquivo:linha citado; corrija.
4. Mesmo erro 3 vezes seguidas → pare, explique o erro ao usuário e peça direção.

## Regras
- Nunca diga "pronto" sem `HARNESS OK` desta sessão.
- Nunca desabilite teste, adicione `skip` ou afrouxe assert para ficar verde.
- O resultado fica em `.hermes-runs/last_harness.json` e aparece no painel.
