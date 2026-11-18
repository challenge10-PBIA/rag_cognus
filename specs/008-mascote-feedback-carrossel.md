# 008 — Mascote personalizável e feedback em carrossel narrado

- **Status:** aprovada — backend (AC-1…AC-8) implementado; AC-9 e front pendentes
- **Substitui:** spec 006 AC-12…AC-16 (avatar cartunizado) e spec 007 AC-5…AC-7 (avatar no
  front). As demais ACs de 006 e 007 continuam valendo.
- **Módulos (backend, `rag_cognus`):** novo `src/rag_cognus/mascot.py`,
  `src/rag_cognus/api/app.py`, `src/rag_cognus/api/schemas.py`, `src/rag_cognus/api/store.py`,
  `src/rag_cognus/feedback.py`; removidos `src/rag_cognus/avatar.py`, `tests/test_avatar.py`;
  `pyproject.toml` (extra `api`)
- **Módulos (front, `/Users/aluno1/Development/frontend_UI`):** novos
  `src/components/mascot/{mascot.tsx,mascot-math.ts,mascot-math.test.mjs}`, novo
  `src/components/diagnosis/feedback-carousel.tsx`, `guided-feedback.tsx`,
  `diagnosis-view.tsx`, `profile/profile-view.tsx`, `header-status.tsx`,
  `src/lib/api/{client.ts,queries.ts,schema.d.ts}`; removido `src/components/avatar.tsx`
- **Testes:** `tests/test_mascot.py` (novo), `tests/test_api.py`, `tests/test_feedback.py`;
  front: `node --test src/components/mascot/mascot-math.test.mjs` + typecheck/lint/build
- **Depende de:** specs 006 (AC-1…AC-11) e 007 (AC-8…AC-10) implementadas

## Problema
O avatar é uma foto cartunizada por filtro (Pillow): exige enviar foto pessoal, fica
estático e não conversa com o feedback. As recomendações da sessão aparecem todas de uma vez
em acordeão, o que dilui a mensagem principal. O usuário quer um mascote cartoon próprio,
personalizável, que represente a pessoa no app e "narre" o feedback, uma recomendação por vez.

## Comportamento esperado
- O perfil guarda um **mascote** (escolhas de uma paleta fechada), sem foto. O upload de
  avatar deixa de existir na API e no front.
- O mascote é um personagem SVG flat (cabeça, orelhas, gorro de tricô com etiqueta ou cabelo,
  olhos com brilho, sobrancelhas, nariz, bochechas coradas, boca, camisa polo), animado por
  `requestAnimationFrame` com parallax por camadas, olhar ocioso, piscar e respiração.
- Na tela de diagnóstico, o feedback guiado vira um **carrossel narrado**: um card por
  recomendação; o mascote fala a recomendação atual num balão e muda de expressão conforme a
  nota do pilar.
- Só o personagem é extraído da referência visual "MascotPortfolioHero"; título, flor,
  serviços e sala em perspectiva do hero **não** entram.

## Contrato do mascote (API)
`mascot = {skin, headwear, headwear_color, shirt}` — todos obrigatórios no objeto, ids de
uma paleta fechada definida em `src/rag_cognus/mascot.py` (fonte única; o front lê do
endpoint de opções, não duplica hex).

- `skin` (6): `pele_1` Clara `#F6D5BF`; `pele_2` Clara média `#EBBE97`;
  `pele_3` Média `#D39A63`; `pele_4` Morena `#B07647`; `pele_5` Morena escura `#87553A`;
  `pele_6` Escura `#5A3825`.
- `headwear` (4, sem hex): `gorro` Gorro de tricô; `cabelo_curto` Cabelo curto;
  `cabelo_cacheado` Cabelo cacheado; `nenhum` Sem cabelo.
- `headwear_color` (10): `petroleo` `#0F4C5C`; `lavanda` `#7C78D6`; `menta` `#4FB38A`;
  `coral` `#E7735A`; `mostarda` `#E0A82E`; `grafite` `#2E3338`; `castanho` `#6B4226`;
  `preto` `#1B1B1B`; `loiro` `#D8B25A`; `ruivo` `#B5532B`.
- `shirt` (6): `petroleo` `#0F4C5C`; `branca` `#F7F5FA`; `lavanda` `#7C78D6`;
  `menta` `#4FB38A`; `coral` `#E7735A`; `mostarda` `#E0A82E`.

Padrão: `{skin: "pele_3", headwear: "gorro", headwear_color: "petroleo", shirt: "menta"}`.
`headwear = "nenhum"` ignora `headwear_color` no desenho, mas o valor continua validado.

## Decisão: remover o avatar por foto
Remover `POST/GET/DELETE /v1/profile/avatar`, `avatar.py`, `tests/test_avatar.py`, os testes
de avatar em `tests/test_api.py`, `AvatarOut`, `Profile.avatar_url` e os métodos de avatar do
`Store`. Motivos: o usuário pediu substituir (não coexistir); manter dois "rostos" do usuário
gera UI ambígua; some o tratamento de foto pessoal (privacidade) e a superfície de upload de
imagem (decompression bomb, formatos); `Pillow` só é importado por `avatar.py` e pelos testes
de avatar (verificado com `grep "PIL"` em `src/` e `tests/`), então sai do extra `api`.
Um `<data_dir>/avatar.png` já existente não é lido nem apagado pela API (sem migração
destrutiva); o README orienta apagar à mão.

## Critérios de aceite — backend (engenheiro-ia)
- **AC-1:** `mascot.py` expõe `MASCOT_OPTIONS: dict[str, list[dict]]` (campo → lista de
  `{id, label, hex|None}`, na ordem da tabela), `DEFAULT_MASCOT: dict` e
  `normalize(raw: object) -> dict`, que devolve um mascote completo: campo ausente, de tipo
  errado ou com id fora da paleta vira o padrão daquele campo; chaves extras são descartadas.
  `skin` tem ≥ 5 opções; ids são únicos por campo.
- **AC-2:** `ProfileIn` ganha `mascot: MascotIn | None = None`; `MascotIn` usa `Literal` com
  os ids de `MASCOT_OPTIONS` e `extra="forbid"`. `PUT /v1/profile` com id fora da paleta,
  campo faltando ou chave desconhecida em `mascot` → 422; nada é gravado.
- **AC-3:** `PUT /v1/profile` sem `mascot` (ou `null`) mantém o mascote salvo; com `mascot`
  substitui o objeto inteiro. A resposta é o `Profile` atualizado.
- **AC-4:** `Profile` passa a ser `{name, daily_goal_minutes, mascot: Mascot}`, com `mascot`
  sempre preenchido (padrão quando nunca salvo ou quando o JSON gravado é inválido, via
  `normalize`). `avatar_url` não existe mais no schema nem no OpenAPI.
- **AC-5:** Migração idempotente: `Store` adiciona `profile.mascot_json TEXT` se faltar
  (`PRAGMA table_info`), preservando `name` e `daily_goal_minutes`; abrir o mesmo banco duas
  vezes não falha nem duplica a coluna (teste com banco criado pelo schema antigo).
- **AC-6:** `GET /v1/profile/mascot/options` → `{options: MASCOT_OPTIONS, default:
  DEFAULT_MASCOT}` (schema `MascotOptions`), sem acesso a rede ou disco além do SQLite.
- **AC-7:** `POST`, `GET` e `DELETE /v1/profile/avatar` respondem 404 (rota inexistente);
  `avatar.py`, `tests/test_avatar.py` e `AvatarOut` não existem; grep em src/ vazio
  (testes podem citar a rota removida).
- **AC-8:** `GuidedRecommendation` ganha `pillar_score: int | None = None` (score do pilar
  alvo; `diction` para dicção) e `maintain: bool = False` (true na recomendação "Manter" da
  spec 006 AC-2). `build_guided` preenche os dois; sessões antigas sem os campos continuam
  válidas em `GET /v1/sessions/{id}`.
- **AC-9 (engenheiro-devops):** `Pillow` sai do extra `api` do `pyproject.toml` (com o
  comentário associado); `grep -rn "PIL" src tests` vazio; `python hermes/harness/check.py`
  passa. `uv.lock` só é regenerado com pedido explícito.

## Critérios de aceite — mascote (front)
- **AC-10:** `src/components/mascot/mascot-math.ts` não importa React, DOM nem Next e só usa
  sintaxe TypeScript apagável (sem `enum`/`namespace`), contendo funções puras:
  `aim(pointer, center, max) -> {x, y}` (vetor limitado a `max`), `approach(cur, target,
  ease, eps) -> number` (interpolação que encaixa no alvo abaixo de `eps`), `pose(aimVec,
  depths) -> Record<Layer, {x, y}>` (deslocamento por camada proporcional à profundidade),
  `blink(elapsedMs, double) -> number` (abertura da pálpebra 0–1), `nextBlink(rand) ->
  {delayMs, double}` (atraso 2–6 s, duplo em ~20 %; `rand` injetado) e
  `moodFor({score, maintain}) -> Mood`.
- **AC-11:** `moodFor`: `maintain` ou `score ≥ 80` → `"feliz"`; `60 ≤ score < 80` →
  `"neutro"`; `score < 60` → `"pensativo"`; `score` nulo → `"neutro"`. Limiares ficam em
  constantes exportadas.
- **AC-12:** O front não tem runner de testes (sem script `test`, sem vitest/jest). Sem nova
  dependência: `mascot-math.test.mjs` usa `node:test` + `node:assert` e importa
  `./mascot-math.ts` (type stripping nativo do Node ≥ 22.6; local tem v24) e cobre AC-10/AC-11
  (limites de `aim`, convergência de `approach`, `blink` em 0 e no meio, `nextBlink` com
  `rand` fixo, cada faixa de `moodFor`). Script `"test:mascot"` em `package.json`. Se o
  `node --test` não rodar no CI do front, a verificação cai para typecheck/lint/build e isso
  é dito no relatório.
- **AC-13:** `<Mascot mascot mood speaking? size? interactive? onActivate?>` desenha o
  personagem em SVG `viewBox="0 0 600 720"` com camadas `<g>` nomeadas `body`, `head`, `ears`,
  `headwear`, `face`, `nose`, `eyes`, `brows`; cores vêm do hex de `MASCOT_OPTIONS` recebido
  da API (nenhum hex de pele/roupa fixo no componente); `headwear` desenha gorro com etiqueta,
  cabelo curto, cacheado ou nada.
- **AC-14:** Animação num único laço `requestAnimationFrame` que escreve `transform` direto
  nos `<g>` por ref (nenhum `setState` por quadro): parallax pelo mouse usando `aim`/`pose`;
  após 3,5 s sem movimento do mouse, olhar ocioso passeia; piscar segundo `nextBlink`/`blink`;
  respiração (escala vertical sutil do corpo, ≤ 2 %); com o ponteiro a menos de ~120 px do
  rosto os olhos arregalam.
- **AC-15:** Expressões por `mood`: `feliz` (sorriso aberto, olhos curvos), `neutro`
  (sorriso leve), `pensativo` (sobrancelhas inclinadas, boca pequena de lado, olhar para
  cima). Clique/Enter/Espaço no mascote interativo mostra `feliz` por ~1,2 s e chama
  `onActivate`.
- **AC-16:** `IntersectionObserver` pausa o laço com o mascote fora da tela e retoma ao
  voltar; desmontar cancela o quadro, remove listeners e desconecta o observer.
  `prefers-reduced-motion: reduce` → pose estática (sem laço, sem parallax, sem piscar);
  expressão e balão continuam. Em toque (`hover: none`) não há seguir-mouse.
- **AC-17:** O código do personagem não traz nada do hero de portfólio (título, flor,
  serviços, sala). Origem do desenho registrada em comentário no topo de `mascot.tsx`
  (ver Riscos).

## Critérios de aceite — personalização e presença no app (front)
- **AC-18:** Em Perfil, o bloco "Seu mascote" substitui o editor de avatar: um
  `role="radiogroup"` por campo (`Tom de pele`, `Cabelo ou gorro`, `Cor do cabelo/gorro`,
  `Camisa`), opções como amostras com `aria-label` do `label` da API e seleção visível além
  da cor (anel + ícone); prévia ao vivo com `<Mascot>`; "Salvar mascote" envia `PUT
  /v1/profile` com nome, meta e `mascot`; "Restaurar padrão" aplica `default`. Erros da API
  em `ErrorBox`; sucesso em `role="status"` "Mascote atualizado."
- **AC-19:** O link "Perfil" do cabeçalho (`header-status.tsx`) mostra o mascote do usuário
  em miniatura estática (sem laço de animação), mantendo `aria-label="Perfil"`.
- **AC-20:** Some todo o fluxo de foto: `avatar.tsx`, `TiltAvatar`, `AvatarImage`,
  `avatarSrc`, `uploadAvatar`, `deleteAvatar`, `useUploadAvatar`, `useDeleteAvatar`,
  `useAvatarVersion`; `grep -ri avatar src` vazio após `npm run api:types`.

## Critérios de aceite — carrossel narrado (front)
- **AC-21:** Com `guided_feedback` não vazio, a coluna de recomendações mostra o mascote e um
  carrossel com um card por recomendação, na ordem de prioridade atual (alta → baixa); só o
  card atual é visível e interativo (demais com `inert` e `aria-hidden`). O mascote do cartão
  de índice (`UserAvatar`) é removido: há um único mascote na tela.
- **AC-22:** O card reaproveita a renderização de `guided-feedback.tsx` extraída em
  componentes exportados (corpo da recomendação, `SubItem` com trecho e fonte da Gold,
  aviso "Base de conhecimento indisponível", `ExerciseCard` com "Marcar como feito" da spec
  007 AC-9/AC-10); o acordeão deixa de ser usado na tela de diagnóstico.
- **AC-23:** O balão do mascote mostra `title` e `text` da recomendação atual; a expressão é
  `moodFor({score: pillar_score ?? result.pillars[pillar]?.score ?? (pillar === "diction" ?
  result.diction : null), maintain})` — o front só lê números da API.
- **AC-24:** Navegação: botões "Anterior"/"Próxima" (desabilitados nas pontas); swipe
  horizontal (pointer events, limiar 48 px, ignorado se o gesto for mais vertical); ←/→
  quando o foco está dentro do carrossel (sem atalho global, para não brigar com o player);
  clique no mascote avança e, no último card, volta ao primeiro.
- **AC-25:** Indicador de posição: uma bolinha-botão por card, `aria-label="Ir para a
  recomendação N de M"`, atual com `aria-current="true"`; texto "N de M" visível.
- **AC-26:** Transição de card: desliza com leve giro (`rotateY` ≤ 12°) em ≤ 350 ms via CSS;
  com `prefers-reduced-motion` a troca é instantânea. O índice atual não reinicia quando o
  hábito é marcado (refetch de `GET /v1/habits`).
- **AC-27:** Fallback: sessão sem `guided_feedback` (antiga) usa o mesmo carrossel com as
  `recommendations` atuais (título, texto, fontes), sem exercícios; humor `feliz` para
  `strength`, `pensativo` para `next_step`, `neutro` para `tip`. Lista vazia → só o mascote
  `neutro` com "Sem recomendações para esta sessão."
- **AC-28:** Uma única recomendação: sem setas nem bolinhas; clique no mascote só dispara a
  expressão feliz.

## Critérios de aceite — acessibilidade e responsivo (front)
- **AC-29:** O mascote interativo é um `<button>` com `aria-label` em português
  ("Mascote: ouvir a próxima recomendação"; no Perfil, "Prévia do seu mascote" sem ação) e o
  SVG interno `aria-hidden`.
- **AC-30:** O balão tem `aria-live="polite"` e anuncia só a troca de recomendação (não a
  animação). O carrossel é `<section aria-roledescription="carrossel" aria-label=
  "Recomendações da sessão">`; cada card `role="group" aria-roledescription="slide"
  aria-label="N de M: {title}"`.
- **AC-31:** Todos os controles (mascote, setas, bolinhas, amostras do Perfil) têm foco
  visível (`focus-visible:outline-2 outline-primary`) e alvo de toque ≥ 44 × 44 px.
- **AC-32:** Em larguras < `lg` o mascote fica acima do card, centralizado, ≤ 160 px de
  largura, e o card ocupa a largura toda; sem rolagem horizontal da página a 360 px; swipe
  funciona em toque. Em `lg+` o conjunto ocupa a coluna lateral atual.

## Critérios de aceite — verificação
- **AC-33:** Backend: `.venv/bin/python -m pytest -q tests/test_mascot.py tests/test_api.py
  tests/test_feedback.py` e `python hermes/harness/check.py` passam; nenhum teste usa rede.
- **AC-34:** Front: `npm run api:types && npm run typecheck && npm run lint && npm run build`
  sem erros, mais `npm run test:mascot` (AC-12). Nenhuma dependência nova em `package.json`.

## Fora de escopo
- Mascote gerado por IA ou a partir de foto; upload de imagem; acessórios além da paleta;
  narração por voz (TTS); mascote na aba "Perguntar"; testes E2E; apagar `avatar.png` antigo.

## Impacto esperado
- Métricas do RAG: nenhum (prompt, recuperação e juízes não mudam). `build_guided` só ganha
  dois campos derivados de dados que já calcula.
- API: quebra intencional de `/v1/profile/avatar` e de `Profile.avatar_url`; o front é
  atualizado na mesma entrega (AC-20) e os tipos regenerados (AC-34).

## Riscos e dúvidas
- **Licença do código de referência:** a origem/licença do "MascotPortfolioHero" colado não
  foi informada. Confirmar com o usuário antes de copiar trechos literais (paths SVG,
  funções); sem confirmação, reimplementar o personagem inspirado nele, com desenho e código
  próprios (AC-17 registra a origem).
- **Teste do front com `node --test`:** depende de type stripping do Node; se o CI do front
  usar Node < 22.6, AC-12 cai para typecheck/lint/build.
- **Dono do front:** o time não tem engenheiro de front; o líder define quem executa
  AC-10…AC-32 (como na spec 007).
- **Desempenho:** laço rAF por mascote; o cabeçalho usa versão estática (AC-19) para não
  haver dois laços na tela.

## Plano (preenchido depois da aprovação)
| Passo | Arquivo | Subagente | Verificação |
|---|---|---|---|
| 1 | `tests/test_mascot.py` → `mascot.py` | engenheiro-ia | AC-1 |
| 2 | `tests/test_api.py` → `api/*` (mascote, remoção do avatar) | engenheiro-ia | AC-2…AC-7 |
| 3 | `tests/test_feedback.py` → `feedback.py`, `schemas.py` | engenheiro-ia | AC-8 |
| 4 | `pyproject.toml` (Pillow) | engenheiro-devops | AC-9, `check.py` |
| 5 | `mascot-math.ts` + `.test.mjs` | front (líder define) | AC-10…AC-12 |
| 6 | `mascot.tsx`, `profile-view.tsx`, `header-status.tsx`, `lib/api/*` | front | AC-13…AC-20 |
| 7 | `feedback-carousel.tsx`, `guided-feedback.tsx`, `diagnosis-view.tsx` | front | AC-21…AC-32 |
| 8 | ambos os repositórios | líder | AC-33, AC-34 |
