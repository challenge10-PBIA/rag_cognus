# 018 — Figura feminina do mascote

- **Status:** implementada (backend + tipos + front); falta a revisão visual do usuário (AC-F6)
- **Estende:** spec 008 (contrato do mascote, AC-1…AC-6, AC-13, AC-18). As demais ACs de 008
  continuam valendo.
- **Módulos (backend, `rag_cognus`):** `src/rag_cognus/mascot.py`,
  `src/rag_cognus/api/schemas.py` (`Mascot`, `MascotIn`, `MascotPalette`). `api/app.py` e
  `api/store.py` **não mudam**: o perfil já passa por `mascot.normalize()` (app.py:583) e o
  SQLite guarda o mascote como JSON livre (`profile.mascot_json`), sem migração.
- **Módulos (front, `/Users/aluno1/Development/frontend_UI`):** `openapi.json` e
  `src/lib/api/schema.d.ts` (gerados), `src/components/mascot/mascot.tsx`,
  `src/components/mascot/mascot-math.ts` + `mascot-math.test.mjs`,
  `src/components/profile/profile-view.tsx` (`MASCOT_FIELDS`). `onboarding.tsx`,
  `header-status.tsx`, `mascot-dock.tsx` e `feedback-carousel.tsx` herdam a mudança sem edição
  (recebem o objeto `mascot` inteiro; o onboarding reaproveita `MascotPicker`).
- **Testes:** `tests/test_mascot.py`, `tests/test_api.py`; front:
  `npm run test:mascot` + typecheck/lint/build + inspeção visual.
- **Depende de:** spec 008 (backend e front implementados).

## Problema
O mascote só tem uma figura, de traços masculinos. O usuário pediu "apenas uma opção do
usuário feminino com as mesmas opções, para garantir mais diversidade". Hoje
`mascot = {skin, headwear, headwear_color, shirt}`; não há como escolher a figura.

## Comportamento esperado
- Em Perfil → "Seu mascote" (e no passo "Escolha meu visual" do onboarding, que usa o mesmo
  `MascotPicker`) aparece um grupo novo **"Figura"** com duas opções: "Masculino" e
  "Feminino".
- Todas as outras escolhas (6 tons de pele, 4 cabelos/gorro, 10 cores, 6 camisas) continuam
  iguais e valem para as duas figuras. Nenhuma cor nova, nenhuma cor "de menina".
- Quem já tem mascote salvo continua vendo exatamente o mesmo desenho (figura masculina).
- O mascote escolhido aparece igual em todo o app (cabeçalho, dock do coach, carrossel,
  onboarding) com animação, piscar, humores e parallax iguais aos de hoje.

## Contrato do mascote (API)
`mascot = {figure, skin, headwear, headwear_color, shirt}`.

- `figure` (2, sem hex): `masculino` "Masculino"; `feminino` "Feminino". Padrão `masculino`.
- Os demais campos e o padrão deles não mudam (spec 008).

`GET /v1/profile/mascot/options` (schema `MascotOptions`; `figure` vem **primeiro**):

```json
{
  "options": {
    "figure": [
      {"id": "masculino", "label": "Masculino", "hex": null},
      {"id": "feminino", "label": "Feminino", "hex": null}
    ],
    "skin": [{"id": "pele_1", "label": "Clara", "hex": "#F6D5BF"}, "... (6, sem mudança)"],
    "headwear": [{"id": "gorro", "label": "Gorro de tricô", "hex": null}, "... (4)"],
    "headwear_color": ["... (10, sem mudança)"],
    "shirt": ["... (6, sem mudança)"]
  },
  "default": {
    "figure": "masculino",
    "skin": "pele_3",
    "headwear": "gorro",
    "headwear_color": "petroleo",
    "shirt": "menta"
  }
}
```

`GET /v1/profile` (e `profile` em `GET /v1/home`) — `mascot` sempre completo, com `figure`:

```json
{
  "name": "Lia",
  "daily_goal_minutes": 15,
  "mascot": {"figure": "feminino", "skin": "pele_5", "headwear": "cabelo_cacheado",
             "headwear_color": "ruivo", "shirt": "coral"}
}
```

`PUT /v1/profile` — corpo `ProfileIn`; em `mascot` (schema `MascotIn`, `extra="forbid"`),
`figure` é **opcional com padrão `masculino`**; os outros quatro continuam obrigatórios:

```json
{"name": "Lia", "daily_goal_minutes": 15,
 "mascot": {"figure": "feminino", "skin": "pele_5", "headwear": "cabelo_cacheado",
            "headwear_color": "ruivo", "shirt": "coral"}}
```

Tipos gerados esperados em `schema.d.ts`: `Mascot.figure: "masculino" | "feminino"`
(obrigatório, saída) e `MascotIn.figure?: "masculino" | "feminino"` (entrada).

**Por que `figure` é opcional só na entrada:** a ordem de entrega é backend → tipos → front.
Entre o deploy do backend e o do front, o front antigo envia `mascot` sem `figure`; se o campo
fosse obrigatório, "Salvar mascote" daria 422. Na saída ele é obrigatório para o front não
precisar tratar `undefined`. Efeito colateral aceito: um cliente antigo que salva o mascote
grava `masculino` (é o único valor que ele conhece).

## Decisão: sem `cabelo_longo` nesta spec
O pedido é "apenas uma opção" com "as mesmas opções". Uma nova opção de `headwear` mudaria a
paleta das duas figuras, os testes de 008 e o picker, e não é necessária para a figura
feminina ser reconhecível. A figura feminina **reinterpreta o desenho** dos ids existentes
(ver AC-F4), sem id novo. `cabelo_longo` para as duas figuras fica como sugestão (Fora de
escopo), numa spec própria, se o usuário pedir.

## Critérios de aceite — backend (engenheiro-ia)
- **AC-1:** `mascot.MASCOT_OPTIONS` ganha a chave `figure` como **primeira** chave, com
  `[{id: "masculino", label: "Masculino", hex: None}, {id: "feminino", label: "Feminino",
  hex: None}]`, nessa ordem; `IDS["figure"] == ("masculino", "feminino")`; as listas de
  `skin`, `headwear`, `headwear_color` e `shirt` ficam idênticas às da spec 008.
- **AC-2:** `DEFAULT_MASCOT == {"figure": "masculino", "skin": "pele_3", "headwear": "gorro",
  "headwear_color": "petroleo", "shirt": "menta"}`.
- **AC-3:** `normalize()` devolve sempre os 5 campos: `figure` ausente, de tipo errado
  (`7`, `None`) ou fora da paleta (`"outro"`) vira `"masculino"`; `"feminino"` é preservado;
  um mascote antigo de 4 campos válidos volta com os mesmos 4 valores + `figure:
  "masculino"`.
- **AC-4:** `GET /v1/profile/mascot/options` devolve exatamente
  `{options: MASCOT_OPTIONS, default: DEFAULT_MASCOT}`; no OpenAPI, `MascotPalette` tem
  `figure` e `MascotOptions.default` (schema `Mascot`) lista `figure` em `required`.
- **AC-5:** `PUT /v1/profile` com `mascot.figure = "feminino"` grava e devolve
  `figure: "feminino"`; `GET /v1/profile` e `GET /v1/home` devolvem o mesmo objeto.
- **AC-6:** `PUT /v1/profile` com `mascot` sem `figure` (corpo da spec 008) → 200 e
  `figure: "masculino"`; com `figure` fora da paleta (`"outro"`, `""`, `null`) → 422 e nada
  é gravado; chave desconhecida continua 422 (`extra="forbid"`); faltar qualquer um dos
  outros 4 campos continua 422.
- **AC-7 (retrocompatibilidade):** um perfil gravado antes desta spec
  (`mascot_json` com os 4 campos antigos, ou `NULL`, ou JSON corrompido) é lido como o mesmo
  mascote + `figure: "masculino"` (ou o padrão completo), sem migração de banco e sem
  reescrever a linha no `GET`.
- **AC-8:** no OpenAPI, `Mascot` (saída) tem `figure` em `required` com
  `enum ["masculino", "feminino"]`; `MascotIn` tem `figure` com `default: "masculino"` e
  **fora** de `required`.
- **AC-9:** os testes da spec 008 que comparam o padrão ou o mascote completo
  (`tests/test_mascot.py::FIELDS`/`default`, `tests/test_api.py::DEFAULT_MASCOT`, `CUSTOM`)
  passam a incluir `figure`; `.venv/bin/python -m pytest -q tests/test_mascot.py
  tests/test_api.py` e `python hermes/harness/check.py` passam, sem rede.

## Critérios de aceite — tipos (front, após o backend)
- **AC-F1:** com a API desta versão rodando (`rag-cognus api`, porta 8001), `npm run
  api:types` regenera `openapi.json` (o script faz `curl $NEXT_PUBLIC_API_URL/openapi.json`;
  o arquivo **não** é copiado à mão) e `src/lib/api/schema.d.ts`; o diff de `schema.d.ts`
  mostra só `figure` em `Mascot`, `MascotIn` e `MascotPalette` (mais o que outras specs já
  tiverem mudado na API).

## Critérios de aceite — front (engenheiro do front)
- **AC-F2:** `profile-view.tsx`: `MASCOT_FIELDS` ganha `{field: "figure", title: "Figura"}`
  como **primeiro** grupo. Ele usa o `SwatchGroup` existente (opções sem `hex` viram pílulas
  de texto, `role="radiogroup"`, alvo ≥ 44 px, foco visível); nenhum componente novo.
  "Restaurar padrão" volta para `masculino`. O onboarding mostra o grupo sem edição própria.
- **AC-F3:** `mascot-math.ts` exporta `figureOf(mascot) -> "masculino" | "feminino"` (pura;
  `undefined`, `null`, ou valor desconhecido → `"masculino"`), coberta em
  `mascot-math.test.mjs` (`npm run test:mascot`). `mascot.tsx` decide o desenho só por ela.
- **AC-F4 (desenho):** com `figure = "feminino"`, `mascot.tsx` muda só estes pontos, e todos
  continuam usando as cores da API (nenhum hex novo de pele, cabelo ou roupa):
  - **olhos:** 2–3 cílios curtos (`INK`) no canto externo de cada olho, dentro de
    `g[data-layer="eye-left|eye-right"]`, para piscarem/arregalarem junto; no humor `feliz`
    (olho em arco) os cílios acompanham o arco;
  - **sobrancelhas:** traço mais fino (≈ 7 em vez de 9) e arco um pouco mais alto, nos três
    humores (tabela `BROWS` por figura), mantendo a leitura de `pensativo`;
  - **silhueta:** pescoço um pouco mais estreito e ombros da camisa levemente mais estreitos
    e arredondados; a gola polo, os botões e a cor da camisa continuam iguais;
  - **cabelo:** `cabelo_curto` vira um corte curto na altura do queixo (laterais que cobrem as
    orelhas, desenhadas na camada `headwear`, sem invadir olhos e bochechas, x ≤ ~170 e
    x ≥ ~430); `cabelo_cacheado` ganha cachos que descem pelas laterais até a altura da
    orelha; `gorro` e `nenhum` desenham igual à figura masculina (a diferença fica no rosto e
    na silhueta);
  - **não mudam:** cabeça, orelhas, nariz, boca, rubor, `viewBox`, as constantes `FACE`,
    `EYE_L`, `EYE_R`, `MOUTH_PIVOT`, a lista e a ordem das camadas `LAYERS` e o laço de
    animação. Com `figure = "masculino"` o SVG fica igual ao de hoje.
- **AC-F5 (sem estereótipo):** a figura feminina não traz rosa fixo, batom, laço, saia,
  joia, maquiagem nem corpo sexualizado; qualquer cor vem da paleta escolhida pelo usuário.
- **AC-F6 (todas as combinações):** inspeção visual, nas duas figuras, de: os 4 `headwear` ×
  3 humores (`feliz`, `neutro`, `pensativo`) com `pele_1` e com `pele_6`; `headwear_color`
  `castanho` e `preto` sobre `pele_6` e `loiro` sobre `pele_1` (piores contrastes cabelo ×
  pele); camisa `branca`; `framing="head"` (miniatura do cabeçalho, viewBox `80 70 440 440`)
  sem cabelo cortado; `prefers-reduced-motion` com pose estática. Nada vaza do `viewBox`,
  os cílios não somem no piscar e o cabelo não cobre os olhos.
- **AC-F7:** `npm run typecheck && npm run lint && npm run build` e `npm run test:mascot`
  passam; nenhuma dependência nova no `package.json`; `grep -rn "#[0-9A-Fa-f]\{6\}"
  src/components/mascot/mascot.tsx` não ganha linhas novas.

## Ordem de entrega
1. Backend (engenheiro-ia): AC-1…AC-9, harness verde.
2. Subir a API local (`rag-cognus api`) e rodar `npm run api:types` no front (AC-F1).
3. Front: AC-F2…AC-F7.

## Fora de escopo
- Nova opção `cabelo_longo` (sugestão para as duas figuras, spec própria).
- Mais figuras (não binária/neutra), acessórios, brincos, maquiagem, roupas novas.
- Mudar os textos do coach ou do onboarding para concordância de gênero (o mascote fala de
  si como "seu mascote"; os textos atuais já são neutros).
- Migrar ou reescrever perfis gravados; mudar `app.py` ou `store.py`.

## Riscos
- **Contraste cabelo × pele:** com o corte curto feminino cobrindo as orelhas, `castanho`
  (`#6B4226`) sobre `pele_6` (`#5A3825`) e `loiro` sobre `pele_1` quase somem. Mitigação:
  contorno `SHADE` na borda do cabelo (vale para as duas figuras só se for barato; senão só
  na feminina). Problema já existe na figura masculina.
- **Parallax:** as laterais do cabelo ficam na camada `headwear` (profundidade diferente da
  cabeça); no movimento máximo elas deslizam sobre a orelha. Verificar no AC-F6 com o mouse
  nos cantos da tela.
- **Testes de 008 quebram de propósito:** o padrão e o mascote completo ganham `figure`;
  atualizar junto (AC-9), não relaxar as asserções.
- **Janela de deploy:** com `figure` opcional na entrada, um front antigo regrava
  `masculino` ao salvar. Aceito (AC-6); some quando o front novo estiver no ar.
- **`api:types` depende da API rodando** com esta versão; se rodar contra uma API antiga, os
  tipos não terão `figure` e o typecheck do front falha (o que é o sinal certo).
- **Reconhecimento:** com `gorro` ou `nenhum`, a figura feminina se distingue só por cílios,
  sobrancelhas e silhueta. Se o usuário achar pouco, a resposta é `cabelo_longo`
  (Fora de escopo), não um traço estereotipado.

## Plano (preenchido depois da aprovação)
| Passo | Arquivo | Subagente | Verificação |
|---|---|---|---|
| 1 | `tests/test_mascot.py`, `tests/test_api.py` | engenheiro-ia | testes falham por AC-1…AC-8 |
| 2 | `src/rag_cognus/mascot.py`, `src/rag_cognus/api/schemas.py` | engenheiro-ia | `python hermes/harness/check.py --changed` |
| 3 | `frontend_UI/openapi.json`, `schema.d.ts` | front | `npm run api:types` (API local na 8001) |
| 4 | `mascot-math.ts`, `mascot-math.test.mjs` | front | `npm run test:mascot` |
| 5 | `mascot.tsx`, `profile-view.tsx` | front | `npm run typecheck && npm run lint && npm run build` + AC-F6 |

## AC → teste (implementação)
| AC | Verificação |
|---|---|
| AC-1 | `tests/test_mascot.py::test_018_ac1_figure_is_first_and_others_unchanged`, `test_ac1_options_default_and_normalize` |
| AC-2 | `tests/test_mascot.py::test_018_ac2_default_mascot` |
| AC-3 | `tests/test_mascot.py::test_018_ac3_bad_figure_becomes_masculino`, `test_018_ac3_feminino_kept_and_old_mascot_gets_masculino` |
| AC-4 | `tests/test_api.py::test_018_options_lists_figure_first`, `test_mascot_options_endpoint` |
| AC-5 | `tests/test_api.py::test_018_feminino_saved_and_read_everywhere` |
| AC-6 | `tests/test_api.py::test_018_missing_figure_defaults_to_masculino`, `test_018_invalid_figure_or_missing_field_is_422` |
| AC-7 | `tests/test_api.py::test_018_old_profiles_read_without_rewrite` |
| AC-8 | `tests/test_api.py::test_018_openapi_figure_required_out_optional_in` |
| AC-9 | `FIELDS`, `default`, `DEFAULT_MASCOT` e `CUSTOM` com `figure`; harness OK |
| AC-F1 | `npm run api:types` contra API temporária (porta 8011, SQLite isolado); diff só `figure`. `openapi-typescript` gera `MascotIn.figure` sem `?` (tem `default`) |
| AC-F2 | `profile-view.tsx` `MASCOT_FIELDS[0] = {field: "figure", title: "Figura"}`; build |
| AC-F3 | `mascot-math.test.mjs` › `figureOf` (`npm run test:mascot`) |
| AC-F4 | Render estático: masculino idêntico ao antigo em 25 920 combinações; grade em PNG revisada |
| AC-F5 | Revisão do desenho; nenhum hex novo em `mascot.tsx` (grep = 0 linhas, igual ao antes) |
| AC-F6 | Parcial: grades estáticas revisadas; parallax e reduced-motion pendentes no navegador |
| AC-F7 | `typecheck`, `lint`, `build`, `test:mascot` passam; `package.json` sem mudança |
