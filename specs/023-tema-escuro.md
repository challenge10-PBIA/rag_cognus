# 023 — Tema escuro (Sistema / Claro / Escuro)

- **Status:** aprovada (2026-11-23)
- **Módulos:** front irmão `frontend_UI/` (Next 16): `src/app/globals.css`,
  `src/app/layout.tsx`, `src/components/profile/profile-view.tsx`,
  `src/components/cognus/articulation-3d-drawer.tsx`, `src/components/mascot/mascot.tsx` e os
  11 componentes com `text-white` (lista no Problema)
- **Testes:** front sem runner de testes (spec 008 AC-12); `npm run test:mascot` e
  `npm run test:articulation` (node `--test`) continuam verdes; nenhum teste Python muda
- **Relacionadas:** 008 (paleta fechada do mascote), 018 (mascote feminino),
  017-articulacao-3d-perfis-catalogo (drawer 3D). Há duas specs 017
  (`017-articulacao-3d-perfis-catalogo.md` e `017-mlflow-grafana.md`); não são renumeradas.
  022 (navegação) — ver Dependências.

## Problema
O front só tem tema claro. `globals.css` define 17 tokens de cor em `:root` sem nenhum valor
escuro, e não há `prefers-color-scheme` nem seletor de tema. Há cores fixas que não seguem os
tokens:
- `text-white` aparece **19 vezes em 11 arquivos**, sempre sobre `bg-primary`/
  `bg-primary-soft`: `nav.tsx` (2), `ui.tsx` (2), `metrics-view.tsx` (2), `audio-consent.tsx`
  (2), `articulation-3d-drawer.tsx` (2), `mascot-dock.tsx` (2), `session-flow.tsx` (3),
  `phonetics-guide.tsx`, `profile-view.tsx`, `onboarding.tsx`, `transcript.tsx` (1 cada).
- `shadow-offset` (10 usos) e `shadow-offset-sm` (22 usos) desenham a sombra com `var(--ink)`;
  no escuro, com `--ink` claro, a sombra viraria um brilho.
- `articulation-3d-drawer.tsx` tem **6 hex fixos** (5 valores): gradiente `#e57373`/`#b94a48`
  (linhas 980–981) e `fill="#d96b6b"`, `fill="#e07a7a"`, `stroke="#9e3b39"` ×2 (1116–1126).
- `mascot.tsx` desenha olhos, boca e sobrancelhas com `INK = var(--ink)` e o brilho com
  `GLINT = var(--card)`: no escuro os traços do rosto clareariam e o brilho escureceria.
  `SHADE` e `BLUSH` são `rgba` fixos; `.tour-spotlight` usa `rgb(21 25 28 / 0.55)` fixo.

## Comportamento esperado
Quem usa escolhe no Perfil entre **Sistema** (padrão, segue o sistema operacional), **Claro** e
**Escuro**. A escolha vale na hora, persiste no navegador e é aplicada antes da primeira
pintura. Todo texto segue legível (AA) nos dois temas; o drawer 3D e o mascote continuam
reconhecíveis no escuro.

### Valores escuros sugeridos (ponto de partida; o AC-5 é o que vale)
| Token | Claro (hoje) | Escuro (sugerido) |
|---|---|---|
| `--bg` | `#f7f5fa` | `#121518` |
| `--card` | `#ffffff` | `#1b1f24` |
| `--surface` | `#f0edf4` | `#22272d` |
| `--ink` | `#15191c` | `#eef0f3` |
| `--muted` | `#5d6570` | `#a3acb7` |
| `--line` | `#e7e3ed` | `#2e343c` |
| `--primary` | `#0f4c5c` | `#7fd0e0` |
| `--primary-soft` | `#1d6273` | `#a2dfeb` |
| `--on-primary` (novo) | `#ffffff` | `#0b2a33` |
| `--shadow` (novo) | `#15191c` (= ink) | `#6b7682` |
| `--mint` / `--mint-ink` | `#bdebd6` / `#1e6b52` | `#173d30` / `#9be3c3` |
| `--lavender` / `--lavender-ink` | `#dfdef8` / `#3d3a8c` | `#25244a` / `#c9c7f7` |
| `--sky` / `--sky-ink` | `#cdebf7` / `#1f5f78` | `#143444` / `#a6dcf2` |
| `--warn` / `--warn-ink` | `#f6e3c4` / `#8a5a12` | `#3d2e14` / `#f2c983` |
| `--danger-ink` | `#a23b3b` | `#ff9b94` |

## Critérios de aceite
- **AC-1:** Todo token de cor de `:root` em `globals.css` (os 17 atuais e os 2 novos do AC-4)
  tem valor escuro. O escuro vale por `@media (prefers-color-scheme: dark)` em
  `:root:not([data-theme="light"])` (escolha "Sistema", sem `data-theme`) e por
  `:root[data-theme="dark"]` (escolha "Escuro"); `:root[data-theme="light"]` força o claro
  mesmo com o sistema no escuro. `color-scheme` acompanha o tema (barras de rolagem e
  controles nativos). Nenhum componente usa `dark:` do Tailwind nem cor fixa nova.
- **AC-2:** O Perfil tem um seletor **Sistema / Claro / Escuro** (grupo de rádio acessível,
  rótulos em português), com "Sistema" marcado por padrão. A escolha aplica `data-theme` em
  `<html>` na hora (ou remove o atributo em "Sistema") e persiste em `localStorage` (chave
  `cognus:tema`). Leitura ou escrita do storage que falhe (modo privado, bloqueio) não quebra a
  página: cai em "Sistema", sem erro no console visível para quem usa.
- **AC-3:** Sem flash de tema errado: um script inline em `<head>` (`layout.tsx`), executado
  antes da pintura, lê `cognus:tema` (em `try/catch`) e aplica `data-theme`; `<html>` tem
  `suppressHydrationWarning` só por causa desse atributo. Recarregar `/` e `/perfil` com
  "Escuro" salvo não mostra o claro antes, e o console do navegador não tem erro de
  hidratação.
- **AC-4:** Tokens novos `--on-primary` (texto/ícone sobre `primary` e `primary-soft`) e
  `--shadow` (sombra deslocada), expostos ao Tailwind como `text-on-primary` e
  `--color-shadow`. `@utility shadow-offset` e `shadow-offset-sm` usam `var(--shadow)` em vez
  de `var(--ink)`. As 19 ocorrências de `text-white` sobre `bg-primary`/`bg-primary-soft`
  viram `text-on-primary`; `grep -rn "text-white" src/components` não encontra nada.
- **AC-5:** Contraste WCAG AA (≥ 4.5:1, texto normal) medido nos dois temas para estes pares
  (fundo à direita): `ink/bg`, `ink/card`, `ink/surface`, `muted/bg`, `muted/card`,
  `muted/surface`, `on-primary/primary`, `on-primary/primary-soft`, `primary/bg`,
  `primary/card` (links e ícones `text-primary`), `mint-ink/mint`, `lavender-ink/lavender`,
  `sky-ink/sky`, `warn-ink/warn`, `danger-ink/card`, e `ink` sobre `mint`, `lavender`, `sky` e
  `warn` (cards coloridos com texto `ink`). Os valores da tabela acima foram medidos e
  passam: menor razão no claro = `warn-ink/warn` 4.70 e `mint-ink/mint` 4.88; menor no escuro
  = `ink/surface` 13.17 e `muted/surface` 6.55. A tabela final de razões vai no PR.
- **AC-6:** No escuro, o drawer 3D e o mascote continuam legíveis.
  **Drawer 3D:** os 6 hex fixos de `articulation-3d-drawer.tsx` viram tokens (ex.:
  `--tongue`, `--tongue-deep`, `--tongue-edge`, `--lip`) com valor claro igual ao de hoje e
  valor escuro próprio; a língua e os lábios contrastam ≥ 3:1 (contraste não-textual) com o
  fundo do palco 3D nos dois temas. **Mascote:** mantém a paleta fechada de
  `src/rag_cognus/mascot.py` (spec 008; nenhum hex da paleta muda nem ganha variante escura);
  os traços do rosto usam um tom fixo escuro (`--mascot-ink`, igual nos dois temas) e o brilho
  um tom fixo claro (`--mascot-glint`), para não inverterem; a silhueta ganha contorno externo
  visível (≥ 3:1 contra `--bg` e `--card` no escuro), inclusive com o tom de pele mais escuro
  da paleta. `.tour-spotlight` usa um token em vez de `rgb(21 25 28 / 0.55)`.
- **AC-7:** Verificação: `npm run typecheck && npm run lint && npm run build &&
  npm run test:mascot && npm run test:articulation` passam no `frontend_UI`; o backend não
  muda (`python hermes/harness/check.py` segue verde).

## Fora de escopo
- Tema por horário, alto contraste e tamanho de fonte.
- Persistir o tema no backend (`PUT /v1/profile`): fica só no navegador.
- Telas do Streamlit (`chat_app.py`, `agents_ui.py`) e painéis do Grafana/MLflow.
- Mudança da paleta do mascote (spec 008) ou do contrato 3D (spec 017).

## Dependências e sequência
- Pode ser implementada em paralelo à **022**, **exceto o AC-2** (seletor no Perfil), que toca
  `profile-view.tsx` junto com o AC-6 da 022 (Histórico e Hábitos saem do Perfil). Fazer o
  AC-2 desta spec **depois** do AC-6 da 022.
- `nav.tsx`, `session-flow.tsx`, `phonetics-guide.tsx`, `metrics-view.tsx` e `onboarding.tsx`
  também são tocados pela 022; a troca `text-white` → `text-on-primary` (AC-4) entra depois da
  022 nesses arquivos, ou em um único passo combinado.

## Impacto
- Nenhum impacto em métricas do RAG, juízes ou API.

## Plano (preenchido depois da aprovação)
| Passo | Arquivo | Subagente | Verificação |
|---|---|---|---|
| 1 | `globals.css` (tokens, `--on-primary`, `--shadow`, utilities) | (front) | AC-1, AC-4, AC-5 |
| 2 | `layout.tsx` (script no `<head>`) | (front) | AC-3, sem erro de hidratação |
| 3 | 11 componentes com `text-white` | (front) | `grep -rn "text-white" src/components` vazio |
| 4 | `articulation-3d-drawer.tsx`, `mascot.tsx` | (front) | AC-6, `test:mascot`, `test:articulation` |
| 5 | `profile-view.tsx` (depois da 022 AC-6) | (front) | AC-2 |
| 6 | — | líder técnico | AC-7 |
