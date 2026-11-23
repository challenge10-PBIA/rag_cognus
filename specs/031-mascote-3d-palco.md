# 031 — Mascote 3D no palco da apresentação

- **Status:** aprovada (2026-11-23)
- **Depende de:** 028 (modo apresentação narrado), 030 (spike 3D, decisão (b) de 2026-11-23),
  027 (voz, `mouthLevel`)
- **Módulos:** só no front irmão `frontend_UI/` (Next 16). Alterados:
  `src/components/presentation/presentation.tsx` (palco 3D no lugar do `MascotDisk` grande,
  posição, transições, painel de diagnóstico), `src/components/mascot3d/scene.ts` (alvo do
  olhar, gestos, pausa, token de bochecha, leitura dos tokens na troca de tema),
  `src/components/mascot3d/mascot-3d.tsx` (props de alvo/gesto/pausa, aviso de contexto
  perdido), `src/lib/mascot3d/motion.ts` (se preciso, só reexportar/estender),
  `src/lib/presentation/roteiro.ts` (campo `gesture`), `src/lib/presentation/roteiro.test.mjs`,
  `public/presentation/roteiro.json` (campo `gesture` por passo),
  `src/components/mascot/mascot.tsx` (bochecha via `--mascot-blush`, sem outra mudança),
  `src/app/globals.css` (token `--mascot-blush`), `package.json` (`test:mascot3d` inclui o
  novo teste). Novos: `src/lib/mascot3d/stage.ts` e `src/lib/mascot3d/stage.test.mjs` (lógica
  pura de palco: posição, olhar para alvo, gestos). Leitura, sem alterar:
  `src/lib/presentation/machine.ts`, `src/lib/voice/player.ts`. Backend: nenhum
  (`rag-cognus voice-pregen` lê só `id` e `text` de cada passo; campos extras são ignorados)
- **Testes:** `npm run test:mascot3d` (`motion.test.mjs` + novo `stage.test.mjs`),
  `npm run test:presentation` (`roteiro.test.mjs` valida `gesture`), `typecheck`/`lint`/`build`
  e os demais `test:*`; backend: `python hermes/harness/check.py` segue verde, sem mudança
- **Relacionadas:** 008 (paleta do perfil), 014 (holofote `.tour-spotlight`), 018 (figura
  feminina), 023 (tokens e temas), 027 (voz), 028 (apresentação), 030 (spike)

## Problema
O spike da spec 030 mostrou que o mascote 3D low-poly fica melhor no palco, mas não compensa no
app todo (estimativa (a) 12,5–17,5 dias contra (b) 4–6). Hoje o modo apresentação (spec 028)
mostra o mascote 2D num disco: grande no centro quando o passo não tem âncora e pequeno na
faixa da legenda quando tem. Ele não olha para o que explica, não se move e não gesticula, e o
holofote e o mascote competem pela atenção da plateia em vez de trabalhar juntos.

## Comportamento esperado
Ao abrir o modo apresentação, o mascote grande passa a ser o 3D do spike. Ele entra com um
pulinho, fica ao lado do holofote sem cobri-lo, vira a cabeça e os olhos para o elemento
destacado, faz um gesto no início de cada fala (acenar, apontar, pulinho, pensar), mexe a boca
com o áudio e, no fim, se despede com um aceno. Entre telas, o palco faz uma transição curta.
Fora do modo apresentação nada muda: o app continua 2D e não baixa o `three`. Sem WebGL, ou se
algo falhar, a apresentação continua com o mascote 2D atual, sem parar a fala.

### Campo novo no roteiro
`gesture` (opcional): `"aceno" | "apontar" | "pulinho" | "pensar" | null`. Ausente = `null`
(sem gesto, só ocioso). O gesto **não** muda o texto, e o `sha256` do `voice-pregen` é calculado
sobre provedor + voz + texto; por isso mudar `gesture` não exige regerar os áudios.

| # | id | anchor | mood | gesture | por quê |
|---|---|---|---|---|---|
| 1 | `abertura` | — | feliz | `aceno` | "Olá": cumprimenta a plateia (depois do pulinho de entrada, AC-4) |
| 2 | `problema` | — | pensativo | `pensar` | fala da dificuldade; mão no queixo combina com o humor |
| 3 | `inicio` | `present:home-next-step` | neutro | `apontar` | mostra o cartão "Seu próximo passo" |
| 4 | `treinar` | `tour:treinar` | neutro | `apontar` | mostra o item Treinar da navegação |
| 5 | `articulacao` | `present:articulation-3d` | feliz | `apontar` | mostra a boca 3D |
| 6 | `plateia` | `present:audience-mode` | neutro | `pensar` | abre com a pergunta "E quando a pressão aumenta?" |
| 7 | `progresso` | `tour:progresso` | feliz | `pulinho` | comemora a evolução |
| 8 | `aprender` | `tour:aprender` | neutro | `apontar` | mostra o item Aprender da navegação |
| 9 | `privacidade` | `present:privacy` | neutro | `null` | tom sério e calmo; só o olhar para o bloco de privacidade |
| 10 | `encerramento` | — | feliz | `apontar` | "a palavra é de vocês": aponta para a plateia (sem âncora = frente) |

## Critérios de aceite
- **AC-1 (3D no palco, carregado sob demanda, com fallback):** Dado o modo apresentação aberto,
  quando um passo está em cena, então o mascote grande é o 3D, reusando `scene.ts` e
  `motion.ts` com as configurações do mascote do perfil; ele substitui o `MascotDisk` grande do
  centro e o disco pequeno da faixa da legenda. O `three` entra só por `import()` dinâmico
  disparado pelo modo: o cartão "Começar" pré-carrega o chunk (`import("…/scene")` ao montar),
  e nenhuma outra tela o baixa (com o modo fechado, a aba Rede não mostra o chunk do `three`;
  a saída do `npm run build` não o coloca no JS compartilhado das rotas). Uma única cena/contexto
  WebGL dura o modo inteiro (trocar de passo ou de rota não recria a cena). Sem WebGL, se o
  chunk falhar ao carregar ou se o contexto for perdido (`webglcontextlost`), o palco volta ao
  layout 2D atual da spec 028 no mesmo passo, sem interromper nem reiniciar a fala do
  `voicePlayer` e sem erro em tela (o motivo vai só para o console).
- **AC-2 (olhar dirigido):** Num passo com âncora visível, cabeça e olhos apontam para o centro
  do retângulo da âncora, convertido em direção a partir do centro do mascote na tela (mesmos
  limites de `LOOK_LIMITS` e mesma lógica de `lookFromPointer`); se a âncora se mover (rolagem,
  redimensionamento), o alvo acompanha. Sem âncora (ou âncora que não apareceu em 3 s), olha
  para a plateia (frente: `yaw = pitch = 0`). A troca de alvo é suave (`damp`, sem salto em
  nenhum quadro). O ponteiro do mouse não comanda o olhar no palco.
- **AC-3 (posição ao lado do holofote):** Com âncora, o mascote fica ao lado do retângulo do
  holofote (âncora + `SPOT_PAD`) sem nenhuma interseção com ele, no lado (esquerdo/direito,
  ou acima/abaixo) com mais espaço livre; em viewport estreita (≤ 640 px) ou sem espaço lateral,
  vai para o canto oposto ao da legenda (legenda embaixo → canto de cima; legenda em cima,
  `captionOnTop` → canto de baixo), reduzindo o tamanho até um mínimo legível. O mascote nunca
  cobre a faixa da legenda nem os controles. Sem âncora, fica no centro da área acima (ou
  abaixo) da legenda, como hoje. Entre passos, desloca-se de forma suave até a nova posição.
  O cálculo da posição é função pura (AC-10).
- **AC-4 (entrada e saída):** Ao começar o primeiro passo, o mascote aparece com o pulinho do
  spike (`hopPose`, squash & stretch) e só então faz o gesto do passo 1. Ao entrar em `ended`
  (cartão "Perguntas?"), o mascote 3D se despede com um aceno e fica ocioso e feliz. Ao sair do
  modo (`Esc`/botão), o palco some sem animação de saída longa (≤ 400 ms).
- **AC-5 (gestos por passo):** O `roteiro.json` ganha o campo opcional `gesture` com os valores
  da tabela acima. O gesto do passo começa junto com a fala (início do áudio, da voz do
  navegador ou da legenda sozinha), por cima do humor (`mood`) do passo, e termina voltando à
  pose ociosa; `null`/ausente = sem gesto. Trocar de passo durante um gesto o encerra (volta à
  pose ociosa sem salto) antes do gesto seguinte. `apontar` estende o braço para o alvo do olhar
  (AC-2): para a âncora ou, sem âncora, para a frente. `parseRoteiro` preserva `gesture`; valor
  desconhecido vira `null` (o app não quebra) e o teste do roteiro acusa. Mudar só `gesture` não
  altera o `sha256` do manifesto, portanto não exige `voice-pregen`. Para `aceno`, `apontar`
  e `pensar`, o mascote 3D ganha **braços e mãos low-poly** (mesmo estilo procedural e flat
  shading, cores da paleta), com ombro e cotovelo articulados e uma pose ociosa relaxada que
  acompanha a respiração. As poses dos braços (ociosa e de cada gesto) são lógica pura em
  `stage.ts` (AC-10), e os braços aparecem também no `/lab/mascote-3d`.
- **AC-6 (fala e pausa):** A boca 3D segue `voicePlayer.mouthLevel` (spec 027, via
  `mouthOpenness`) também com os mp3 pré-gerados e com a voz do navegador; sem fala, fica
  fechada no humor do passo. Pausar (`P` ou botão) congela a boca (fechada, como no tocador) e o
  gesto no quadro em que estava; retomar continua o gesto do mesmo ponto. Respiração e piscar
  seguem durante a pausa.
- **AC-7 (transições entre telas):** Quando o passo seguinte muda de rota, o overlay faz uma
  transição curta de "câmera" (fade ou deslize, ≤ 400 ms) cobrindo a troca de tela, e o holofote
  só aparece depois que a âncora estiver posicionada. Com `prefers-reduced-motion: reduce`:
  corte simples, sem transição; o mascote não se desloca (troca direta de posição), não pula nem
  gesticula e não faz respiração/balanço — só pisca e mexe a boca (modo `reduced` da 027).
- **AC-8 (desempenho e diagnóstico):** No ensaio, o roteiro completo roda com **FPS médio ≥ 50**
  no computador da apresentação (`devicePixelRatio` limitado, por exemplo a 2, se preciso). Um
  painel de diagnóstico, oculto por padrão, aparece com `?debug=1` na URL ou com a tecla `D`
  durante o modo (alterna; não age com foco em campo de texto e não conflita com as teclas da
  028), mostrando FPS médio/mínimo (`fpsStats`), draw calls, triângulos e
  `renderer.info.memory` (geometrias e texturas). Com a aba oculta, o laço de render pausa. Ao
  sair do modo, tudo é liberado (`dispose` de geometrias, materiais, texturas e renderer;
  ouvintes removidos): o relatório de `dispose` volta a 0 geometrias e 0 texturas, e entrar e
  sair 5 vezes não deixa contexto WebGL ativo nem faz a memória crescer.
- **AC-9 (acabamento):** As variações do perfil que o palco usa — figura (masculino/feminino,
  spec 018), cabelo/gorro (`headwear`) e cores da paleta (spec 008) — aparecem corretamente no
  3D, nos temas claro e escuro; trocar o tema com o modo aberto atualiza as cores lidas de
  tokens sem recriar a cena. Novo token `--mascot-blush` em `globals.css` (valores para claro e
  escuro, no `:root`, no `prefers-color-scheme: dark` e no `[data-theme="dark"]`, como os demais
  tokens do mascote) substitui a constante `BLUSH` do `mascot.tsx` e o uso de `--tongue` na
  bochecha do `scene.ts`; no tema claro o 2D fica visualmente igual ao de hoje.
- **AC-10 (lógica pura testada):** `src/lib/mascot3d/stage.ts` (sem Three.js, DOM nem relógio)
  concentra: posição do mascote dado viewport, retângulo do holofote, faixa da legenda e tamanho
  (AC-3); direção do olhar para um alvo de tela (AC-2); pose de cada gesto em função do tempo
  decorrido, com duração fixa e volta à pose neutra no fim, e tempo congelado na pausa (AC-5,
  AC-6), incluindo os ângulos de ombro e cotovelo de cada braço (pose ociosa ligada à
  respiração e poses de `aceno`/`apontar`/`pensar`, com `apontar` mirando o alvo do AC-2). `stage.test.mjs` cobre: lado com mais espaço, nenhuma interseção com holofote nem
  legenda, tela estreita → canto oposto à legenda, sem âncora → centro; alvo à direita/esquerda,
  limites e alvo nulo → frente; cada gesto começa e termina na pose neutra, `null` = neutra,
  tempo além da duração = neutra. Roda em `npm run test:mascot3d`. `roteiro.test.mjs` passa a
  validar `gesture` (ausente, `null` ou um dos quatro valores).
- **AC-11 (verificação):** No `frontend_UI`, `npm run typecheck && npm run lint &&
  npm run build` e todos os `test:*` passam; no backend, `python hermes/harness/check.py`
  termina em `HARNESS OK`. Ensaio manual registrado no relatório: roteiro completo com a rede
  desligada, com o passador de slides, com FPS médio/mínimo do painel (AC-8) no computador da
  apresentação, fallback 2D forçado (WebGL desligado no navegador) e `prefers-reduced-motion`.

## Fora de escopo / próxima spec sugerida
- 3D no dock, no cabeçalho, no Perfil, no onboarding ou em qualquer tela fora do modo
  apresentação (decisão (b) da 030).
- **Próxima spec sugerida — 2D vivo (nível A):** levar ao mascote 2D do app o que o spike
  mostrou que vale: olhar que segue o cursor, ocioso mais vivo, reações a eventos e transições
  entre humores.
- V3/V4 da voz (push-to-talk, co-apresentador) e visemas/fonemas.
- Gesto sincronizado com palavras do texto (o gesto começa no início da fala).
- Mudanças no backend, na API, no `voice-pregen` ou nas métricas do RAG.

## Riscos
- **Contexto perdido no projetor:** trocar de monitor ou espelhar a tela pode derrubar o
  contexto WebGL; o fallback 2D do AC-1 cobre, e o ensaio do AC-11 testa.
- **GPU integrada + projetor de alta resolução:** o FPS pode cair abaixo de 50; limitar o
  `devicePixelRatio` e medir no painel do AC-8 antes do dia.
- **Holofote e mascote disputando espaço** em telas pequenas ou âncoras largas (barra de
  navegação inteira): a regra do canto oposto à legenda (AC-3) evita cobrir, ao custo de um
  mascote menor.
- **Overlay em todas as rotas:** o modo é montado no `app-shell`; um `import` estático do
  `scene.ts` levaria o `three` ao app todo. O AC-1 exige import dinâmico e verificação no build.

## Impacto
- Nenhum impacto em métricas do RAG, juízes ou MLflow; nada no backend muda. Os áudios
  pré-gerados continuam válidos (o `gesture` não entra no `sha256`). Estimativa: 5–7 dias
  (4–6 do spike + 1 dia dos braços e mãos).

## Plano (preenchido depois da aprovação)
| Passo | Arquivo | Subagente | Verificação |
|---|---|---|---|
| 1 | `stage.ts` + `stage.test.mjs`, `package.json` (`test:mascot3d`) | engenheiro-frontend | AC-10 vermelho → verde |
| 2 | `roteiro.ts`, `roteiro.test.mjs`, `roteiro.json` (`gesture`) | engenheiro-frontend | AC-5, AC-10 |
| 3 | `scene.ts`, `mascot-3d.tsx` (braços e mãos, alvo, gestos, pausa, contexto perdido; braços também no `/lab/mascote-3d`) | engenheiro-frontend | AC-2, AC-5, AC-6, AC-8 |
| 4 | `presentation.tsx` (palco 3D, posição, transições, diagnóstico, fallback) | engenheiro-frontend | AC-1, AC-3, AC-4, AC-7, AC-8 |
| 5 | `globals.css` (`--mascot-blush`), `mascot.tsx`, `scene.ts` | engenheiro-frontend | AC-9 |
| 6 | ensaio offline com passador e FPS | líder técnico | AC-11 |

Estimativa total: **5–7 dias** (+1 dia pelos braços e mãos do AC-5).
