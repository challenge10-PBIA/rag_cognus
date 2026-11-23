# Mascote: figura masculina e feminina (spec 018)

Estudo curto do campo `figure` do mascote: o que muda no contrato, como o desenho foi feito,
como gerar os tipos do front e como testar.

## Contrato
- `mascot = {figure, skin, headwear, headwear_color, shirt}`; `figure` ∈ `masculino` |
  `feminino`, padrão `masculino`, sem `hex` (`src/rag_cognus/mascot.py`).
- `figure` é a **primeira** chave de `MASCOT_OPTIONS` (o picker mostra "Figura" primeiro).
- Saída (`Mascot`): `figure` obrigatório. Entrada (`MascotIn`, `extra="forbid"`): opcional com
  padrão `masculino`, para o front antigo não levar 422 na janela de deploy.
- Perfis antigos não migram: `mascot.normalize()` completa `figure` na leitura e o `GET` não
  reescreve a linha.
- Observação: `openapi-typescript` (padrão `defaultNonNullable`) gera `MascotIn.figure`
  como obrigatório no TypeScript, porque o campo tem `default`. Não muda nada no front novo,
  que sempre envia o mascote completo.

## Decisões de desenho (`frontend_UI/src/components/mascot/mascot.tsx`)
- Tudo decide por `figureOf(mascot)` (`mascot-math.ts`, pura): o que não é `feminino` desenha
  a figura de sempre.
- A feminina muda só: cílios curtos (`INK`) no canto externo, dentro de
  `g[data-layer="eye-left|eye-right"]` (piscam junto; no `feliz` seguem o arco); sobrancelhas
  com traço 7 e arco mais alto (`BROWS` por figura); pescoço e ombros mais estreitos e
  arredondados (`SILHOUETTE`), com a mesma gola e botões; `cabelo_curto` vira corte na altura
  do queixo cobrindo as orelhas (borda interna em x ≈ 160–168 e 432–440);
  `cabelo_cacheado` ganha 3 cachos por lado até a altura da orelha. `gorro` e `nenhum` são iguais.
- Sem estereótipo: nada de rosa fixo, batom, laço, saia, joia ou maquiagem. Nenhum hex novo;
  todas as cores vêm da paleta da API.
- Contorno `SHADE` (traço 4) só no cabelo feminino, para separar cabelo e pele nos piores
  contrastes (`castanho`/`preto` sobre `pele_6`, `loiro` sobre `pele_1`). Na masculina ele
  não entrou, para o desenho antigo ficar igual.

## Gerar os tipos do front
Com a API desta versão rodando:

```bash
cd ../frontend_UI
NEXT_PUBLIC_API_URL=http://127.0.0.1:8001 npm run api:types
```

O `curl` grava o `openapi.json` minificado; o arquivo versionado é indentado (2 espaços, sem
`\n` final), então reformate antes de comparar o diff para ele mostrar só o que mudou. Para
gerar sem mexer na API principal, suba uma instância temporária em outra porta com outro
`data_dir`: `Store()` marca avaliações `pending` como erro ao abrir o banco, então uma segunda
API no mesmo `.cache/app/cognus.db` interromperia uma avaliação em andamento.

## Como testar
- Backend: `.venv/bin/python -m pytest -q tests/test_mascot.py tests/test_api.py -k "018 or
  mascot"` e `python hermes/harness/check.py`.
- Front: `npm run test:mascot` (`figureOf`), `npm run typecheck && npm run lint && npm run build`.
- Figura masculina idêntica: renderizar o componente antigo e o novo com
  `react-dom/server` (transpilando o `.tsx` com o `typescript` do próprio front) e comparar o
  `<svg>` em todas as combinações; na entrega deram 25 920 renderizações e 0 diferenças.
- Visual (AC-F6): grade figura × `headwear` × humor com `pele_1`/`pele_6`, `framing="head"`,
  e os pares de pior contraste. Parallax e `prefers-reduced-motion` só no navegador.
