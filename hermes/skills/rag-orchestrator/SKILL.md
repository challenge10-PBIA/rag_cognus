---
name: rag-orchestrator
description: Use para qualquer tarefa no rag_cognus que toque mais de um arquivo ou peça feature/bugfix. Coordena subagentes (explorer, spec-writer, test-writer, implementer, reviewer) via delegate_task no fluxo SDD → TDD → harness.
---

# Orquestrador multiagente (rag_cognus)

Você é o líder. Planeje, delegue, integre e verifique. Não faça você mesmo o trabalho
pesado de leitura: delegue e mantenha seu contexto limpo (o modelo local tem contexto curto).

## Fases

| Fase | Papel | Paralelo? | Saída esperada |
|---|---|---|---|
| 1. Entender | `explorer` | sim, 1 por módulo | ≤10 linhas: funções relevantes com `arquivo:linha` |
| 2. Especificar | `spec-writer` | não | `specs/NNN-slug.md` com AC numerados |
| 3. Aprovar | você + usuário | — | pergunte ao usuário se a spec está ok |
| 4. Teste vermelho | `test-writer` | sim, 1 por arquivo de teste | testes falhando + saída do pytest |
| 5. Implementar | `implementer` | sim só se arquivos diferentes | código + `check.py --changed` verde |
| 6. Revisar | `reviewer` | não | lista de problemas ou "aprovado" |
| 7. Harness final | você | — | `python hermes/harness/check.py` verde |

Pule fases 2–3 só para mudanças triviais (typo, renomear, ajuste de texto).

## Como delegar
Sempre preencha `goal` curto e `context` completo — o subagente NÃO vê sua conversa.
Use `role="leaf"` para os papéis abaixo. Nunca coloque dois subagentes paralelos editando
o mesmo arquivo.

```
delegate_task(tasks=[
  {"goal": "[explorer] mapear como chain.py monta citações",
   "context": "<PAPEL explorer abaixo>\nArquivos: src/rag_cognus/chain.py, tests/test_chain.py\nPergunta: ...",
   "role": "leaf"},
  {"goal": "[explorer] mapear métricas de citação",
   "context": "<PAPEL explorer>\nArquivos: src/rag_cognus/metrics.py ...",
   "role": "leaf"}
])
```

Comece o `goal` com o papel entre colchetes: o painel (`hermes/monitor/app.py`) agrupa por ele.

## Papéis (cole no `context`)

**explorer** — Somente leitura. Use read_file/search_files. Não edite nada. Responda em ≤10
linhas com `arquivo:linha` e o que cada trecho faz. Sem sugestões de código.

**spec-writer** — Copie `specs/_TEMPLATE.md` para `specs/NNN-slug.md` (NNN = próximo número).
Preencha Problema, Comportamento, AC testáveis (Dado/Quando/Então) e Fora de escopo. Não
escreva código. Devolva o caminho e os AC.

**test-writer** — Carregue a skill `rag-tdd`. Para cada AC recebido, escreva um teste em
`tests/` que falhe pelo motivo certo. Sem rede: use monkeypatch/fakes. Rode
`.venv/bin/python -m pytest -q <arquivo> -x` e devolva a saída mostrando a falha. Não
toque em `src/`.

**implementer** — Carregue a skill `rag-tdd`. Leia o teste vermelho, faça a menor mudança em
`src/` que o deixe verde, use `patch`. Rode `python hermes/harness/check.py --changed`.
Devolva: arquivos alterados + última linha do harness. Não altere testes, exceto se o teste
estiver comprovadamente errado — nesse caso pare e explique.

**reviewer** — Somente leitura + `git diff`. Verifique: cada AC tem teste; sem rede em teste;
sem segredos; linhas ≤100; mensagens em português; nada fora do escopo da spec. Devolva
lista numerada `arquivo:linha — problema` ou "aprovado".

## Integração
- Depois de cada lote, leia só os resumos. Se um subagente falhou, re-delegue com o erro
  exato no `context` (no máximo 2 tentativas; depois pergunte ao usuário).
- Feche com o harness completo e um relatório: spec, testes adicionados, arquivos
  alterados, saída final do harness.
