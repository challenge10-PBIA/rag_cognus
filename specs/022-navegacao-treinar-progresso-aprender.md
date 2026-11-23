# 022 — Navegação por tarefa: Início · Treinar · Progresso · Aprender · Perfil

- **Status:** aprovada (2026-11-23)
- **Módulos:** front irmão `frontend_UI/` (Next 16): `src/components/nav.tsx`,
  `src/app/**/page.tsx`, `next.config.ts`, `src/components/cognus/cognus-view.tsx`,
  `src/components/cognus/phonetics-guide.tsx`, `src/components/session/session-flow.tsx`,
  `src/components/profile/profile-view.tsx`, `src/components/metrics/metrics-view.tsx`,
  `src/components/onboarding/onboarding.tsx`, `src/components/mascot/mascot-dock.tsx`,
  `src/lib/api/client.ts`; backend `src/rag_cognus/coach.py`
- **Testes:** `tests/test_coach.py`; front sem runner de testes (spec 008 AC-12): verificação
  por `npm run typecheck && npm run lint && npm run build`
- **Relacionadas:** 008 (mascote), 013 (coach, dicas por rota), 014 (onboarding/tour),
  015-catalogo-fonetico-gold e 017-articulacao-3d-perfis-catalogo (catálogo + 3D). Há duas
  specs 017 (`017-articulacao-3d-perfis-catalogo.md` e `017-mlflow-grafana.md`); não são
  renumeradas, e esta spec só depende da primeira. Sequenciar com a 023 (ver Dependências).

## Problema
Os exercícios fonéticos com o 3D, que são o diferencial do produto, estão escondidos como 4ª aba
("Fonética & Exercícios") de "Pergunte ao Cognus" (`cognus-view.tsx`, `TABS`), uma tela que
mistura perguntar, sintetizar tema, adaptar ao público e fonética. A Home tem ~6 entradas para
`/gravar` (`home-view.tsx:85,129,139,175,215`), o Histórico de sessões e Meus Hábitos ficam no
Perfil (`profile-view.tsx`, `History` e `Habits`), longe das métricas. O "voltar" da sessão de
exercício é fixo em `/cognus` (`session-flow.tsx:260,353`). Quando a Gold fonética não está
disponível, `GET /v1/phonetics/exercises` responde 503 e `PhoneticsGuide` mostra o `ErrorBox`
genérico com a mensagem técnica da API.

## Comportamento esperado
A navegação passa a seguir a tarefa de quem usa, com cinco destinos: **Início**, **Treinar**
(ação central, substitui "Gravar"), **Progresso**, **Aprender** e **Perfil**. Treinar é um hub
com três trilhas (Sessão de fala, Articulação, Preparar fala). Progresso reúne métricas,
histórico e hábitos. Aprender fica só com Perguntar e Sintetizar tema. Links antigos continuam
funcionando por redirect. O mascote coach (spec 013) e o tour do onboarding (spec 014) acompanham
as novas rotas. Catálogo fonético indisponível vira um estado amigável, não um erro técnico.

### Mapa de rotas
| Rota nova | Conteúdo | Origem hoje |
|---|---|---|
| `/` | Início (sem mudança de conteúdo nesta spec) | `/` |
| `/treinar` | Hub com as 3 trilhas | — (novo) |
| `/treinar/sessao` | Fluxo de sessão (`SessionFlow`), modos e query `modo`/`desafio`/`exercicio` | `/gravar` |
| `/treinar/articulacao` | Catálogo fonético + drawer 3D (`PhoneticsGuide`) | aba `phonetics` de `/cognus` |
| `/treinar/preparar` | Adaptar ao público (`Adapt`) | aba `adapt` de `/cognus` |
| `/progresso` | Métricas (`MetricsView`) + Histórico + Meus Hábitos | `/metricas` + parte de `/perfil` |
| `/aprender` | Perguntar + Sintetizar tema | abas `ask`/`evidence` de `/cognus` |
| `/perfil` | Perfil sem Histórico e sem Hábitos | `/perfil` |
| `/sessoes/[id]` | Sem mudança | `/sessoes/[id]` |

## Critérios de aceite
- **AC-1:** `components/nav.tsx` mostra, na navegação lateral (desktop, `lg:`) e na inferior
  (mobile), exatamente cinco destinos, nesta ordem: Início (`/`), Treinar (`/treinar`),
  Progresso (`/progresso`), Aprender (`/aprender`), Perfil (`/perfil`). Treinar é o destaque
  central: na inferior, o botão circular `bg-primary` no meio (posição 3 de 5); na lateral, o
  botão de topo no lugar do atual "Gravar". O item ativo usa `aria-current="page"` e
  `/treinar/*` ativa Treinar. Não sobra nenhum link para `/gravar`, `/metricas` ou `/cognus`
  na navegação.
- **AC-2:** `/treinar` é um hub com três cartões-link, todos com título e uma frase em
  português: **Sessão de fala** (lista os modos `daily_pitch`, `reuniao_1_1`,
  `apresentacao_tecnica`, `espontanea` com os rótulos de `GET /v1/meta`, cada um levando a
  `/treinar/sessao?modo=<id>`), **Articulação** (leva a `/treinar/articulacao`) e **Preparar
  fala** (leva a `/treinar/preparar`).
- **AC-3:** As rotas `/treinar/sessao`, `/treinar/articulacao`, `/treinar/preparar`,
  `/progresso` e `/aprender` existem em `src/app/` e renderizam o conteúdo do mapa de rotas.
  `/treinar/sessao` aceita as mesmas query strings de hoje (`modo`, `desafio`, `exercicio`).
  `/treinar/preparar`, depois de adaptar o texto, mostra o botão **"Gravar com este texto"**,
  que abre `/treinar/sessao` com o texto adaptado visível como roteiro na tela da sessão; se
  o navegador não deixar guardar o texto, a sessão abre sem roteiro, sem erro.
- **AC-4:** `next.config.ts` declara `redirects()` permanentes (308): `/gravar` →
  `/treinar/sessao`, `/metricas` → `/progresso`, `/cognus` → `/aprender`. A query string é
  preservada (ex.: `/gravar?modo=espontanea&exercicio=x` → `/treinar/sessao?modo=espontanea&
  exercicio=x`). As pastas `src/app/gravar`, `src/app/metricas` e `src/app/cognus` deixam de
  existir, e nenhum `href`/`router.push`/prefixo em `src/` aponta para as rotas antigas
  (verificável: `grep -rnE "/(gravar|metricas|cognus)\b" src` não encontra rota, só
  eventuais nomes de pasta de componente como `components/cognus/`).
- **AC-5:** `/aprender` mostra apenas as abas **Perguntar** e **Sintetizar tema**; as abas
  `adapt` e `phonetics` saem de `TABS` em `cognus-view.tsx`. O título da página é "Aprender".
- **AC-6:** `History` ("Histórico de sessões") e `Habits` ("Meus Hábitos") saem de
  `profile-view.tsx` e aparecem em `/progresso`, abaixo das métricas, com o mesmo
  comportamento (carregando, erro com "Tentar de novo", vazio). O estado vazio do histórico
  leva a `/treinar`.
- **AC-7:** Na sessão, o botão "Voltar" (`TopBar back`) leva a `/treinar/articulacao` quando a
  sessão veio de um exercício (`exercicio` na query) e a `/treinar` nos demais casos; o
  "Voltar" de "Concluir Sessão" leva a `/treinar/sessao` mantendo `modo`/`exercicio`.
  A navegação inferior, o mascote (`mascot-dock.tsx`, `HIDDEN_PREFIXES`) e o onboarding
  continuam ocultos durante a sessão, agora pelo prefixo `/treinar/sessao`.
- **AC-8:** O tour do onboarding (`TOUR` em `onboarding.tsx`) tem um passo por destino da
  navegação (`treinar`, `inicio`, `progresso`, `aprender`, `perfil`), com textos em português
  que descrevem os novos destinos. Todo `id` de `TOUR` tem um `data-tour` correspondente em
  `nav.tsx` nas duas navegações, e não sobra `data-tour` nem passo para `gravar`, `metricas`
  ou `cognus`.
- **AC-9:** `coach.tips` (backend, `src/rag_cognus/coach.py`, hoje ramificado em `/metricas`,
  `/cognus`, `/perfil`) reconhece as rotas novas: `/progresso` devolve as mesmas dicas de
  `/metricas` (`metrics-empty` / `metrics-weakest-<pilar>`), `/aprender` devolve
  `cognus-how`, `/treinar` devolve `train-hub`, `/treinar/articulacao` devolve
  `train-articulation` e `/treinar/preparar` devolve `train-prepare` (textos em português, no
  máximo 2 dicas). `/metricas` e `/cognus` continuam como alias e devolvem os mesmos ids que
  `/progresso` e `/aprender`. Rota desconhecida segue sem dicas. Testes em
  `tests/test_coach.py` (parametrizar `test_static_route_tips` e um teste de alias).
- **AC-10:** Em `/treinar/articulacao`, quando `GET /v1/phonetics/exercises` falha com 503 (ou
  a rede falha), a página mostra um estado amigável em português — título "Os exercícios de
  articulação ainda não estão disponíveis" e uma frase sem jargão — com o botão "Tentar de
  novo" (refaz a consulta). Nenhuma mensagem técnica (texto do `detail`, "Erro 503", nome de
  tabela ou de exceção) aparece. Para isso o erro da API passa a carregar o status HTTP
  (`ApiError.status` em `src/lib/api/client.ts`). Outros erros continuam no `ErrorBox`.
- **AC-11:** Verificação: no front, `npm run typecheck && npm run lint && npm run build`
  passam; no backend, `python hermes/harness/check.py` passa.

## Fora de escopo
- **F2:** limpeza da Home (reduzir as ~6 entradas para `/gravar` a uma), mover "Serviços
  locais" do Perfil, esconder o painel do juiz (`EvaluationPanel`) atrás de uma flag,
  consentimento de áudio único.
- **F3:** card "Próximo passo" adaptativo na Home; fonte única de exercícios
  (`data/exercicios.json` × catálogo fonético da Gold).
- Tema escuro (spec 023).
- Mudança de API além do `coach.tips`: os endpoints `/v1/*` não mudam.

## Dependências e sequência
- A spec 023 (tema escuro) pode correr em paralelo, **exceto** o AC-2 da 023 (seletor de tema
  no Perfil), que também mexe em `profile-view.tsx`. Fazer o AC-6 desta spec antes e só
  depois o seletor de tema.
- `nav.tsx` é tocado pelas duas (aqui a estrutura; na 023, `text-white` → `text-on-primary`).
  Implementar a 022 primeiro em `nav.tsx` e aplicar a troca de token da 023 em cima.

## Impacto
- Nenhum impacto em métricas do RAG nem nos juízes: o AC-9 só muda dicas por rota do coach.
- Links salvos/compartilhados para rotas antigas seguem funcionando pelos redirects 308.

## Plano (preenchido depois da aprovação)
| Passo | Arquivo | Subagente | Verificação |
|---|---|---|---|
| 1 | `tests/test_coach.py` | engenheiro-ia | AC-9 vermelho |
| 2 | `src/rag_cognus/coach.py` | engenheiro-ia | `python hermes/harness/check.py --changed` |
| 3 | `frontend_UI` rotas, `next.config.ts`, `nav.tsx` | engenheiro-frontend | AC-1…AC-4, `npm run build` |
| 4 | `cognus-view.tsx`, `profile-view.tsx`, `/progresso` | engenheiro-frontend | AC-5, AC-6 |
| 5 | `session-flow.tsx`, `mascot-dock.tsx`, `onboarding.tsx` | engenheiro-frontend | AC-7, AC-8 |
| 6 | `client.ts`, `phonetics-guide.tsx` | engenheiro-frontend | AC-10 |
| 7 | — | líder técnico | AC-11 (front + harness) |
