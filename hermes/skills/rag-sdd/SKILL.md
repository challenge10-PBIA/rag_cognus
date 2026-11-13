---
name: rag-sdd
description: Spec-driven development no rag_cognus. Use antes de implementar feature ou mudança de comportamento; cria specs/NNN-slug.md com critérios de aceite testáveis.
---

# SDD — especificar antes de codar

1. Liste `specs/` e escolha o próximo número (`001`, `002`…).
2. Copie `specs/_TEMPLATE.md` → `specs/NNN-slug.md` (slug curto, kebab-case).
3. Preencha:
   - **Problema**: o que falta/erra hoje, com um exemplo concreto.
   - **Comportamento esperado**: visível para quem usa (CLI, chat, métricas no MLflow).
   - **Critérios de aceite**: `AC-n: Dado … quando … então …`. Cada AC precisa virar
     um teste automatizado sem rede. Se não dá para testar, reescreva o AC.
   - **Fora de escopo**: o que não será feito.
4. Mostre a spec ao usuário e espere aprovação antes de escrever código.
5. Depois de aprovada, preencha a tabela **Plano** (passo → arquivo → papel → verificação)
   e marque `Status: aprovado`. Ao final, `Status: implementado`.

Boas práticas:
- 2 a 6 AC. Mais que isso: divida em duas specs.
- Cite módulos e funções reais (`src/rag_cognus/chain.py::build_prompt`), não invente.
- Não decida detalhes de implementação na spec, só comportamento.
