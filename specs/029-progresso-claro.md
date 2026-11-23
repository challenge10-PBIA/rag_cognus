# 029 — Progresso claro: estou melhorando e o que faço agora

- **Status:** aprovada (2026-11-23)
- **Módulos:** front irmão `frontend_UI/` (Next 16): `src/components/metrics/metrics-view.tsx`,
  `src/app/progresso/page.tsx`, `src/components/progress/progress-history.tsx`, tipos gerados em
  `src/lib/api/schema.d.ts` (`npm run api:types`); backend (AC-8, depois da spec 027)
  `src/rag_cognus/progress.py` (`summary`), `src/rag_cognus/api/schemas.py` (`Progress`, `Bar`),
  rota `GET /v1/progress` em `src/rag_cognus/api/app.py`
- **Testes:** `tests/test_progress.py`, `tests/test_api.py`; front sem runner de componentes
  (spec 008 AC-12): `npm run typecheck && npm run lint && npm run build` + `test:progress`
  (novo, lógica pura dos gráficos) e os `test:*` existentes
- **Relacionadas:** 022 (rota `/progresso`, Histórico saiu do Perfil), 023 (tokens e contraste
  AA nos dois temas), 026 (padrão "um próximo passo claro"), 027 (voz do avatar: o AC-8 só
  começa depois dela, pois mexe nos mesmos arquivos da API)

## Problema
A tela de Progresso mostra um cartão de índice, um gráfico de barras que mistura minutos com
calma, quatro conquistas, dois direcionamentos, o histórico completo e os hábitos, todos com o
mesmo peso. Ela não responde com clareza às quatro perguntas de quem a abre: **Estou
melhorando? Onde estou bem e onde estou fraco? Sou constante? O que faço agora?** Os pilares
(`pillars`) chegam na API mas não aparecem na tela, e não existe comparação por pilar com o
período anterior.

## Comportamento esperado
A tela vira uma leitura de cima para baixo, uma pergunta por bloco: resumo em uma linha →
evolução do índice → pilares (com o foco destacado) → constância → o que fazer agora →
histórico curto. Conquistas e Hábitos continuam disponíveis, mas recolhidos. Todo número
exibido vem pronto do backend (`GET /v1/progress?period=week|month|quarter`); o front só
formata e desenha. Os campos novos do AC-8 são opcionais no front: enquanto o backend não os
enviar, as partes que dependem deles (valor anterior, variação e minilinha por pilar) não
aparecem, sem erro.

## Dados de origem (estado atual, `progress.summary`)
- **Períodos:** `week` = 7 barras de 1 dia; `month` = 4 barras de 7 dias; `quarter` = 12
  barras de 7 dias. A janela termina hoje e tem `barras × dias` dias; o período anterior é a
  janela de mesmo tamanho imediatamente antes.
- **`bars[]`:** por barra, `label` (dia da semana `SEG…DOM` ou `dd/mm` do 1º dia),
  `minutes` (soma de `duration_seconds`/60, 1 casa), `index` (média dos índices das sessões da
  barra, arredondada; `null` sem sessões), `calm` (média de `(5 − anxiety_after)/4 × 100`,
  arredondada; `null` sem autoavaliação).
- **Pilares:** chaves fixas `pace`, `pauses`, `fillers`, `clarity` (rótulos no front: Ritmo,
  Pausas, Vícios de linguagem, Clareza — `PILLAR_NAMES`). `pillars` é a média de cada pilar nas
  sessões do período, arredondada; `null` se nenhuma sessão tiver o pilar.
- **Variações:** `index_change_pct` e `anxiety_change_pct` são **percentuais relativos**
  (`100 × (agora − antes)/antes`, 1 casa; `null` sem base). `guidance` usa os 2 pilares mais
  fracos das **últimas 5 sessões** (não do período), com padrão fixo sem histórico.

## Critérios de aceite
- **AC-1 (resumo em 1 linha):** Abaixo do seletor de período há uma linha de resumo com
  `sessions` ("N sessões" / "1 sessão"), o índice `index` com `index_change_pct` (com sinal
  `+`/`−` e seta; omitida quando `null`) e a sequência `streak_days` ("N dias seguidos").
  Trocar o período atualiza a linha. Estado vazio (`sessions === 0` no período): a linha diz
  "Nenhuma sessão neste período" e há um botão **"Gravar primeira sessão"** (ou "Gravar uma
  sessão" se `streak_days > 0` ou houver histórico) que abre a prática espontânea; os blocos
  AC-2 a AC-4 mostram estado vazio, nunca zeros inventados.
- **AC-2 (evolução do índice):** Um gráfico de linha com área por barra de `bars[].index`, eixo
  Y de 0 a 100 e rótulos de `bars[].label` no X. Barra com `index === null` vira **lacuna** (a
  linha e a área se interrompem; nenhum ponto é interpolado nem desenhado em 0). Cada ponto tem
  tooltip no hover e é focável por teclado (Tab/setas), mostrando rótulo e índice. O gráfico
  tem uma descrição textual acessível (`<title>`/`<desc>` ou texto `sr-only`) com primeiro e
  último valor e quantas barras têm dado. Ao lado: índice atual `index`"/100" e o nível
  (`level.number` e `level.name`).
- **AC-3 (pilares):** Quatro barras horizontais 0–100, uma por chave de `pillars`, com o
  valor numérico escrito. Quando `pillars_previous[k]` e `pillars_change[k]` (AC-8) existem e não
  são `null`, a barra mostra um marcador do valor anterior e o texto da variação em pontos
  (ex.: "+6 vs. anterior"). O pilar com **menor** `pillars[k]` não nulo recebe o selo
  **"Seu foco"** (empate: ordem `pace`, `pauses`, `fillers`, `clarity`); se todos forem `null`,
  nenhum selo. Quando `bars[].pillars` (AC-8) existe, cada pilar tem uma minilinha com as
  médias por barra, com lacunas para `null`. Pilar `null` aparece como "sem dados", não como 0.
- **AC-4 (constância):** Um gráfico de barras de `bars[].minutes` com uma linha horizontal
  rotulada "Meta diária" (meta de `GET /v1/home` `daily_goal.goal_minutes`; em `month`/
  `quarter`, meta × 7 por barra, rótulo "Meta semanal"), e o texto da sequência
  (`streak_days`) e da média diária (`avg_daily_minutes`). A calma (`bars[].calm`) fica em um
  **gráfico separado**, com título contendo "autoavaliação", e `anxiety_change_pct` só aparece
  quando não `null`. Minutos e calma nunca compartilham o mesmo eixo.
- **AC-5 (o que fazer agora):** O bloco "O que fazer agora" mostra o **primeiro** item de
  `guidance` aberto (foco, título, descrição, minutos, fontes) com o botão **"Praticar agora"**
  (`/treinar/sessao?modo={mode}&desafio={pillar}`). Os demais itens ficam atrás de um
  controle **"Ver mais"** (`aria-expanded`), fechado por padrão. Com `guidance` vazio, o bloco
  não aparece.
- **AC-6 (histórico e recolhidos):** O histórico mostra as **5** sessões mais recentes de
  `GET /v1/sessions` e um controle **"Ver todas"** que expande a lista completa. "Conquistas"
  (com a contagem de desbloqueadas no cabeçalho) e "Hábitos" ficam em seções recolhidas
  (`<details>`/disclosure com `aria-expanded`), fechadas por padrão.
- **AC-7 (gráficos e acessibilidade):** Os gráficos dos AC-2 a AC-4 são **SVG próprio**, sem
  biblioteca nova em `package.json`. Cores vêm dos tokens da spec 023 e funcionam nos temas
  claro e escuro. Nenhuma informação depende só de cor (variação tem sinal e seta; o selo tem
  texto; lacunas são explicitadas no texto acessível). Com `prefers-reduced-motion: reduce`,
  nada anima. Em viewport de 360 px não há rolagem horizontal e os rótulos não se sobrepõem.
  Texto e marcas têm contraste AA (texto ≥ 4.5:1, marcas ≥ 3:1). Forma, cores, marcas e
  interação seguem o método da skill `dataviz`. A lógica pura (escala, segmentação de lacunas,
  escolha do "Seu foco", meta por barra) fica num módulo `.mjs` testado por `test:progress`.
- **AC-8 (backend; a implementar DEPOIS da spec 027, pelo engenheiro-ia, em TDD):**
  `GET /v1/progress` passa a enviar, calculado só em `progress.summary`:
  - `Progress.pillars_previous: dict[str, int | None]` — mesmas chaves de `pillars`, média
    arredondada de cada pilar nas sessões do **período anterior de mesmo tamanho** (a mesma
    janela já usada para `index_change_pct`); `None` sem dados;
  - `Progress.pillars_change: dict[str, int | None]` — `pillars[k] − pillars_previous[k]` em
    pontos, calculada no backend sobre as médias **antes** de arredondar e então arredondada;
    `None` se faltar um dos lados;
  - `Bar.pillars: dict[str, int | None] | None` — média arredondada de cada pilar nas sessões da
    barra; `None` (o campo todo) quando a barra não tem sessões;
  - `Progress.bar_goal_minutes: float | None` — meta por barra para a linha de referência do
    gráfico de constância (AC-4): `daily_goal_minutes` do perfil × dias da barra (1 em `week`,
    7 em `month`/`quarter`); `None` sem meta. O front não calcula a meta (`summary` recebe a
    meta diária; a rota passa a do perfil).
  Testes: em `tests/test_progress.py`, um por campo (período anterior com sessões só em
  `9 dias atrás` para `week`; variação `None` quando um lado falta; barra vazia com
  `pillars is None`; meta × 1 em `week`, × 7 em `month`/`quarter`, `None` sem meta); em
  `tests/test_api.py`, `GET /v1/progress` com os quatro campos no JSON
  e o modelo `Progress` validando. Os campos existentes não mudam de nome, tipo nem valor.
- **AC-9 (verificação):** No `frontend_UI`, `npm run typecheck && npm run lint &&
  npm run build` e `npm run test:progress` (novo) + os `test:*` existentes passam; depois do
  AC-8, `npm run api:types` regenera `schema.d.ts` e o typecheck segue verde. No backend,
  `python hermes/harness/check.py` passa.

## Fora de escopo
- Novas métricas de fala ou novos pilares (ex.: `diction` no resumo do período).
- Metas configuráveis por pilar.
- Exportar relatório (PDF/CSV) do progresso.
- Mudar o critério de `guidance` (continua nas últimas 5 sessões).

## Riscos
- **"Seu foco" × direcionamento:** o selo usa o menor pilar do **período**; o AC-5 usa os
  pilares mais fracos das **últimas 5 sessões**. Em períodos longos podem divergir; o texto do
  selo não deve prometer que é o mesmo do direcionamento.
- **Percentual × pontos:** `index_change_pct` é relativo (%), `pillars_change` é em pontos.
  O front rotula cada um ("%" e "pts") para não misturar.
- **Conflito de arquivos:** AC-8 toca `app.py`/`schemas.py`, em edição pela spec 027;
  só começa depois dela.

## Impacto
- Nenhum impacto em métricas do RAG, juízes ou avaliação. AC-8 só acrescenta campos à
  resposta de `GET /v1/progress` (compatível com clientes atuais).

## Plano (preenchido depois da aprovação)
| Passo | Arquivo | Subagente | Verificação |
|---|---|---|---|
| 1 | `specs/029-progresso-claro.md` | engenheiro-ia | revisão do líder |
| 2 | `metrics-view.tsx`, `progresso/page.tsx`, `progress-history.tsx`, módulo `.mjs` | engenheiro-frontend | AC-1…AC-7, `typecheck`/`lint`/`build`/`test:progress` (campos do AC-8 opcionais) |
| 3 | `tests/test_progress.py`, `tests/test_api.py` → `progress.py`, `schemas.py`, `app.py` | engenheiro-ia (após 027) | AC-8, `python hermes/harness/check.py --changed` |
| 4 | `schema.d.ts` (`npm run api:types`) | engenheiro-frontend | AC-9 |
| 5 | — | líder técnico | AC-9, harness completo |
