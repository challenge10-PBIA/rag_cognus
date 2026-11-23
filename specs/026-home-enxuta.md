# 026 — Home enxuta: um próximo passo claro

- **Status:** aprovada (2026-11-23)
- **Módulos:** front irmão `frontend_UI/` (Next 16): `src/components/home/home-view.tsx`;
  leitura de `src/lib/api/client.ts` (tipo de `GET /v1/home`); backend
  `src/rag_cognus/coach.py` (só conferência dos textos das dicas de `/`)
- **Testes:** `tests/test_coach.py` (dicas de `/` sem elementos removidos, já verde); front sem
  runner de componentes (spec 008 AC-12): `npm run typecheck && npm run lint && npm run build`
  + `test:mascot`, `test:articulation`, `test:session`, `test:audience`
- **Relacionadas:** 013 (dicas do mascote por rota), 022 (rotas `/treinar/*`, Início),
  023 (tokens e contraste AA), 025 (sessão imersiva)

## Problema
A Home mostra muita coisa ao mesmo tempo: Modos de Prática, Prática Espontânea, Atalho de
Articulação, cartão de pontos com ícone, cartão de feedback, "Novo Treino" e os desafios do
dia, todos com peso visual parecido. Quem abre o app não sabe o que fazer primeiro, e no
celular a ação principal fica abaixo da dobra.

## Comportamento esperado
A Home vira uma coluna única com uma pergunta respondida no topo: **qual é o meu próximo
passo?** O primeiro desafio pendente aparece em destaque com um botão "Começar agora"; logo
abaixo, uma faixa compacta resume como a pessoa está; depois, os demais desafios do dia em
lista simples; por fim, uma linha "Explorar" com os atalhos que sobram. Os dados vêm todos de
`GET /v1/home`, sem mudança de API.

## Critérios de aceite
- **AC-1 (cabeçalho):** O topo da Home tem o título "Início", a saudação com o nome do perfil
  e uma linha de status com a sequência de dias (`streak_days`) e "Meta de hoje" com uma barra
  de progresso preenchida por `daily_goal.percent` (limitada a 100%). A barra tem
  `role="progressbar"` com `aria-valuenow`, `aria-valuemin="0"` e `aria-valuemax="100"`.
- **AC-2 (Seu próximo passo):** Um cartão "Seu próximo passo" mostra o **primeiro** item de
  `challenges` com `done === false`, na ordem em que o backend o envia (título, minutos e
  descrição), e um botão primário **"Começar agora"** que abre a sessão desse desafio. Estados:
  - sem sessões (`latest === null` e nenhuma prática registrada): o cartão diz "Grave sua
    primeira sessão" e "Começar agora" abre a prática espontânea;
  - todos os desafios com `done === true`: o cartão diz "Desafios de hoje concluídos" e o botão
    vira **"Prática livre"**, que abre a prática espontânea.
- **AC-3 (Como você está):** Só quando há sessões (`latest !== null`), uma faixa compacta
  "Como você está" mostra o índice da última sessão com a variação (`index_change`, com sinal;
  omitida quando `null`), o nível (`level`), a **primeira frase** de `latest.feedback` e o link
  "Ver diagnóstico" para a análise da última sessão. Sem sessões, a faixa não é renderizada.
- **AC-4 (Depois):** Uma seção "Depois" lista os demais desafios (todos exceto o do AC-2) só
  com título e minutos, sem descrição nem botão próprio; os concluídos aparecem riscados
  (`line-through`) e anunciados como concluídos para leitor de tela. Se não houver outros
  desafios, a seção não aparece.
- **AC-5 (Explorar):** Uma seção "Explorar" mostra **uma linha** com três atalhos: "Sessão de
  fala", "Articulação" e "Preparar fala" (rotas da spec 022). Saem da Home: Modos de Prática,
  Prática Espontânea (como cartão), Atalho de Articulação (como cartão), o cartão de pontos com
  ícone, o cartão de feedback e o botão "Novo Treino". Nenhum desses textos aparece no HTML da
  Home.
- **AC-6 (celular e acessibilidade):** Em viewport 360×640, o botão "Começar agora" (ou
  "Prática livre") está visível sem rolar. A ordem do Tab segue AC-1 → AC-2 → AC-3 → AC-4 →
  AC-5. Todo texto tem contraste AA (≥ 4.5:1) nos temas claro e escuro (tokens da spec 023).
  Com `prefers-reduced-motion: reduce`, a barra da meta e os cartões não animam.
- **AC-7 (verificação):** No `frontend_UI`, `npm run typecheck && npm run lint &&
  npm run build` e os testes `npm run test:mascot`, `test:articulation`, `test:session` e
  `test:audience` passam; no backend, `python hermes/harness/check.py` segue verde e as dicas
  do mascote para `/` (`coach.tips`) não citam elementos removidos no AC-5.

## Fora de escopo
- Próximo passo escolhido pelo backend a partir do diagnóstico (F3): aqui a ordem é a de
  `challenges` que o backend já envia.
- Mudanças em `GET /v1/home`, `progress.py` ou nas outras telas (Treinar, Progresso, Aprender,
  Perfil).

## Riscos
- **Dobra no celular:** cabeçalho alto empurra o "Começar agora" para baixo; manter a linha de
  status numa só linha em 360 px.
- **Dicas desatualizadas:** o mascote (spec 013) não pode apontar para cartões que sumiram;
  conferido em `coach.tips("/")` (textos atuais só falam de prática curta, meta e sequência).

## Impacto
- Nenhum impacto em métricas do RAG, juízes ou API.

## Plano (preenchido depois da aprovação)
| Passo | Arquivo | Subagente | Verificação |
|---|---|---|---|
| 1 | `specs/026-home-enxuta.md`, `coach.py` (conferência das dicas de `/`) | engenheiro-ia | `tests/test_coach.py` |
| 2 | `home-view.tsx` | engenheiro-frontend | AC-1…AC-6, `typecheck`/`lint`/`build` |
| 3 | — | líder técnico | AC-7 |
