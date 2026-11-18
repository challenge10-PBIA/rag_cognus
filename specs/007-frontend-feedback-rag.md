# 007 — Front: transcrição, avatar, feedback interativo e avaliação do RAG

- **Status:** rascunho
- **Repositório:** `/Users/aluno1/Development/frontend_UI` (Next.js 16, React 19,
  Tailwind 4, openapi-fetch, TanStack Query)
- **Módulos:** `src/components/diagnosis/diagnosis-view.tsx`,
  `src/components/cognus/cognus-view.tsx`, `src/components/profile/profile-view.tsx`,
  `src/lib/api/queries.ts`, `src/lib/api/client.ts`, `src/lib/api/schema.d.ts` (gerado);
  componentes novos em `src/components/diagnosis/` e `src/components/ui.tsx`
- **Verificação:** `npm run api:types && npm run typecheck && npm run lint && npm run build`
- **Depende de:** specs 003, 004 e 006 implementadas na API (`rag-cognus api`)

## Problema
A tela de diagnóstico mostra a transcrição inteira sempre aberta, só marca vícios fixos e
as recomendações são cartões estáticos. A aba "Perguntar" exibe um parágrafo e não mostra a
qualidade da resposta. Não há avatar do usuário.

## Comportamento esperado
- Transcrição recolhível, com vícios e pleonasmos destacados e sugestão em tooltip.
- Avatar cartunizado no topo do feedback, que acompanha o mouse com inclinação suave.
- Recomendações expansíveis com sub-recomendações, fontes da Gold e cards de exercício que
  podem ser marcados como feitos.
- Resposta do RAG estruturada e painel de avaliação que se atualiza sozinho.
- Regras do `AGENTS.md` do front valem: números só da API, textos em português, páginas
  Server Components finas, hooks de URL em Client Components dentro de `<Suspense>`.

## Critérios de aceite — transcrição
- **AC-1:** A transcrição fica num bloco recolhível: recolhida mostra ~3 linhas
  (`line-clamp-3`) com gradiente de fade e botão "Ver transcrição completa"; expandida
  mostra tudo e "Recolher". O botão tem `aria-expanded` e `aria-controls`.
- **AC-2:** Palavras de `transcript[]` com `kind` (spec 003) são destacadas por tipo:
  `vicio_fixo` e `vicio_detectado` em lavanda, `pleonasmo` em `warn`; o contador do
  cabeçalho mostra vícios e pleonasmos separados. Sem `kind` (sessão antiga), cai no
  comportamento atual por `filler`.
- **AC-3:** Ao focar ou passar o mouse num termo destacado, um tooltip acessível
  (`role="tooltip"`, abre com teclado, fecha com Esc) mostra tipo, `suggestion` e
  `excerpt` da ocorrência correspondente em `occurrences[]` (casada por `start`).
- **AC-4:** Clique (ou Enter) num termo leva o player a `start`; se o player ainda não
  foi aberto, abre e posiciona. Sem áudio disponível (404), o termo não é clicável e o
  tooltip continua.

## Critérios de aceite — avatar
- **AC-5:** Em Perfil, o usuário envia uma foto (PNG/JPEG/WebP ≤ 5 MB) para
  `POST /v1/profile/avatar`, vê a prévia cartunizada e pode removê-la (`DELETE`); erros
  da API aparecem com `ErrorBox`.
- **AC-6:** No feedback, o avatar (`profile.avatar_url`; sem avatar → iniciais do nome)
  aparece num cartão no estilo atual (`Card`, borda `ink`, `shadow-offset`) e inclina
  conforme o mouse: rotação ≤ 8° em X/Y, com interpolação suave via
  `requestAnimationFrame`, voltando a 0° quando o mouse sai.
- **AC-7:** Com `prefers-reduced-motion: reduce` ou em toque (sem `hover`), o avatar fica
  estático. A imagem tem `alt` "Seu avatar".

## Critérios de aceite — feedback interativo
- **AC-8:** Cada item de `guided_feedback` é um acordeão (título, pilar, prioridade em
  `Pill`); aberto, mostra sub-recomendações com o trecho entre aspas e a fonte (título e
  link quando houver `url`). `sources_available=false` mostra "Base de conhecimento
  indisponível". Sessão sem `guided_feedback` mostra as `recommendations` atuais.
- **AC-9:** Cada exercício aparece em card com título, nível, duração (`duracao_min` min),
  passos numerados e link "Fonte: {titulo} ({autor}, {ano})" que abre em nova aba com
  `rel="noopener noreferrer"`.
- **AC-10:** "Marcar como feito" chama `POST /v1/habits` com `{text, session_id,
  exercise_id}` (hook `useAddHabit` estendido); o card mostra "Feito" quando há hábito
  com aquele `exercise_id` e `session_id` em `GET /v1/habits`.

## Critérios de aceite — tela do RAG
- **AC-11:** "Perguntar" usa os tipos gerados de `AskOut` (sem cast manual
  `as AskResult`) e mostra `structured`: resumo, pontos em lista, recomendação destacada e
  fontes `{titulo, nicho, trecho}` com link. Abstenção mostra só o resumo.
- **AC-12:** Painel "Avaliação da resposta" faz polling de
  `GET /v1/ask/{ask_id}/evaluation` com `refetchInterval` (3 s, recuo até 10 s) enquanto
  `status="pending"` e para em `done`, `error` ou `disabled`, ou após 5 minutos.
- **AC-13:** Em `done`, mostra `quality_score` e cada juiz (rótulo, nota 1–5 em barra,
  justificativa curta), `latency_seconds` formatado e o aviso "Notas geradas por modelo
  local: exploratórias". `mlflow_logged=false` mostra "Não registrado no MLflow".
  Em `error`, a mensagem da API; nenhum número é calculado no front.

## Critérios de aceite — verificação
- **AC-14:** `npm run api:types` regenera `src/lib/api/schema.d.ts` a partir da API em
  execução (`NEXT_PUBLIC_API_URL=http://127.0.0.1:8001`) e `npm run typecheck`,
  `npm run lint` e `npm run build` passam sem erros.

## Fora de escopo
- Player de áudio com forma de onda; edição do avatar no front; notificações push; testes
  E2E automatizados.

## Plano (preenchido depois da aprovação)
| Passo | Arquivo | Subagente | Verificação |
|---|---|---|---|
| 1 | `schema.d.ts`, `queries.ts`, `client.ts` | front | AC-14 (typecheck) |
| 2 | `diagnosis/*` | front | AC-1…AC-4, AC-6…AC-10 |
| 3 | `profile-view.tsx` | front | AC-5 |
| 4 | `cognus-view.tsx` | front | AC-11…AC-13 + lint/build |
