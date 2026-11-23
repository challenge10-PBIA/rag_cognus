# 030 — Avaliação de um mascote 3D low-poly (spike)

- **Status:** aprovada (2026-11-23) — protótipo isolado; nada muda no mascote em produção
- **Módulos:** só no front irmão `frontend_UI/` (Next 16): nova rota
  `src/app/lab/mascote-3d/page.tsx`, novos `src/components/mascot3d/` (cena, montagem do
  personagem, laço de animação, painel de medição) e `src/components/mascot3d/mascot3d-math.ts`
  (lógica pura), `package.json` (dependências `three` e `@types/three`; script
  `test:mascot3d`). Leitura, sem alterar: `src/components/mascot/mascot.tsx` e
  `mascot-math.ts` (tipos `Mood`/`Figure`, constantes de piscar), `src/lib/voice/lipsync.ts`
  (`mouthOpen`, `rms`), `src/lib/voice/player.ts`, `public/presentation/audio/abertura.mp3`,
  `src/lib/api/queries.ts` (configurações do mascote do perfil). Backend: nenhum
  (`src/rag_cognus/mascot.py` é só a fonte da paleta, lida pela API existente)
- **Testes:** front sem runner de componentes (spec 008 AC-12): `npm run test:mascot3d`
  (novo, `node --test`, padrão de `mascot-math.test.mjs`) + `typecheck`/`lint`/`build` e os
  `test:*` existentes; backend: `python hermes/harness/check.py` (deve seguir verde, sem
  mudança)
- **Relacionadas:** 008 (mascote e paleta fechada do perfil), 013 (mascote coach), 018
  (figura feminina), 023 (tokens e temas), 027 (voz do avatar, `mouthOpen`), 028 (modo
  apresentação, candidato a palco do 3D)

## Problema
O mascote é um SVG 2D em camadas (`mascot.tsx`, specs 008/013/018/027) e o "3D" da
articulação é SVG com projeção própria, sem WebGL. O usuário quer saber se um mascote 3D
low-poly no estilo de "Moments of Happiness" (EPIC Agency / Karim Maaloul "Yakudoo":
personagens procedurais em Three.js, flat shading, animação ociosa, olhar que segue o cursor,
squash & stretch) deixa a apresentação e a interação com o avatar melhores. Trocar o mascote
direto custaria caro (personalização da spec 008, voz da 027, apresentação da 028) sem saber
se vale a pena; por isso primeiro um protótipo isolado, medido, para decidir.

## Comportamento esperado
Existe uma página de laboratório, `/lab/mascote-3d`, que não aparece em nenhum menu. Nela, o
mascote 3D e o mascote 2D atual ficam lado a lado, com as mesmas cores do perfil. O 3D
respira, balança, pisca, segue o cursor com os olhos e a cabeça, troca de humor, dá um
"pulinho" e fala a abertura da apresentação com a boca acompanhando o som. Um painel mostra
FPS, custo de desenho e tempo de inicialização. Nada fora dessa rota muda; o resto do app não
baixa o `three`.

## Critérios de aceite
- **AC-1 (rota isolada e peso):** Dado o app em execução, quando se abre `/lab/mascote-3d`,
  então a página carrega; nenhum link da navegação, do Perfil ou da Home aponta para ela.
  `three` é importado **só** a partir dessa rota (import dinâmico/`next/dynamic` com
  `ssr: false`), gerando um chunk separado. O relatório do spike traz o tamanho **gzip** desse
  chunk e confirma (pela saída do `npm run build` ou inspeção de `.next/`) que as demais rotas
  não incluem `three`. Dependências novas: só `three` e `@types/three` (sem GSAP nem outra
  lib de animação); `three` é MIT.
- **AC-2 (personagem procedural low-poly):** O mascote 3D é montado em código com primitivas
  do Three.js (sem modelo `.glb`/`.gltf` nem textura baixada), geometria low-poly e
  **flat shading**. As cores de pele, cabelo/gorro e roupa vêm da **paleta do perfil**
  (spec 008, via a mesma consulta usada pelo 2D); um seletor na página troca a pele entre as
  6 opções e a cor do cabelo/gorro entre as opções da paleta, e o 3D atualiza sem recarregar.
  Nenhuma cor fora da paleta aparece no personagem (o fundo/cena pode usar os tokens da
  spec 023).
- **AC-3 (ocioso):** Parado, o personagem respira (escala vertical do tronco oscilando, período
  entre 3 s e 5 s), balança levemente (rotação da cabeça/corpo de amplitude ≤ 6°) e **pisca em
  intervalos irregulares** entre `BLINK_MIN_DELAY_MS` e `BLINK_MAX_DELAY_MS` (2–6 s), com
  piscadas duplas ocasionais, reusando as constantes de `mascot-math.ts`. A escolha do próximo
  intervalo é função pura com gerador aleatório injetável.
- **AC-4 (olhar segue o cursor):** Com o ponteiro sobre a página, olhos e cabeça giram em
  direção a ele; a rotação é **limitada** (cabeça ≤ 25° em guinada e ≤ 15° em arfagem; pupilas
  presas dentro do olho) e **suavizada** (interpolação exponencial dependente de `dt`, sem
  saltos ao entrar/sair o ponteiro). Sem ponteiro por 2 s, o olhar volta ao centro. O mapeamento
  ponteiro → ângulos e a suavização são funções puras.
- **AC-5 (fala com boca guiada pelo áudio):** Um botão **"Ouvir abertura"** toca
  `public/presentation/audio/abertura.mp3`; durante o som, a abertura da boca 3D é guiada por
  `mouthOpen` (spec 027) a partir do `rms` do áudio real (`AnalyserNode`), com os mesmos
  `ATTACK`/`RELEASE`; ao terminar ou pausar, a boca fecha. O 2D ao lado recebe o mesmo valor,
  para comparar a sincronia. Clicar de novo interrompe.
- **AC-6 (humores e reação):** Três botões aplicam os humores `feliz`, `neutro` e `pensativo`
  (o tipo `Mood` existente), mudando boca, sobrancelhas e postura de forma distinguível. Um
  botão **"Pulinho"** dispara uma reação com **squash & stretch**: achata antes de subir,
  estica no ar, achata ao pousar e volta ao normal, **preservando o volume aproximado**
  (`sx · sy · sz ≈ 1`, tolerância ±10%) em toda a curva, em ≤ 900 ms. A curva da reação é
  função pura do tempo.
- **AC-7 (comparação lado a lado):** O `Mascot` 2D atual (sem alteração no componente) aparece
  ao lado do 3D, no mesmo tamanho aparente, com o mesmo humor, as mesmas cores e a mesma boca
  (AC-5). Em viewport ≤ 640 px os dois ficam empilhados, sem rolagem horizontal.
- **AC-8 (medição na tela):** Um painel mostra, atualizado a cada ~1 s: **FPS médio** e
  **FPS mínimo** dos últimos 5 s, **triângulos** e **draw calls** (`renderer.info.render`), e o
  **tempo de inicialização** (do início do carregamento do chunk até o primeiro quadro
  desenhado, em ms). Um botão "Copiar medições" copia os valores em texto, para registrar no
  relatório do spike. O cálculo de FPS médio/mínimo numa janela deslizante é função pura.
- **AC-9 (robustez):** (a) Sem WebGL (falha ao criar o contexto ou contexto perdido), a página
  mostra só o 2D e o aviso "Seu navegador não suporta 3D; mostrando o mascote 2D.", sem erro no
  console além do registro do motivo. (b) Com `prefers-reduced-motion: reduce`, nada se move
  sozinho (sem respiração, balanço nem pulinho; piscar e boca no modo `reduced` da 027), e o
  olhar só muda sem animação. (c) Com a aba oculta (`visibilitychange`), o laço de animação
  pausa e o medidor não conta o tempo oculto. (d) Ao sair da rota, geometrias, materiais,
  renderer e o `AudioContext` são liberados (`dispose`/`close`) e os ouvintes removidos;
  entrar e sair 5 vezes não aumenta `renderer.info.memory` nem deixa contexto WebGL ativo.
- **AC-10 (lógica pura testada):** `mascot3d-math.ts` concentra a lógica sem Three.js nem DOM:
  intervalo de piscar (AC-3), ponteiro → ângulos com limites e suavização (AC-4), curva do
  pulinho com volume preservado (AC-6) e FPS médio/mínimo na janela (AC-8). Um teste
  `mascot3d-math.test.mjs` cobre cada uma (limites, `dt` = 0, gerador aleatório fixo, janela
  vazia) e roda com `npm run test:mascot3d` (`node --test`).
- **AC-11 (verificação):** No `frontend_UI`, `npm run typecheck && npm run lint &&
  npm run build`, `npm run test:mascot3d` e os `test:*` existentes passam. No backend,
  `python hermes/harness/check.py` segue terminando em `HARNESS OK`.

## Critério de decisão (depois do spike)
Com a página do AC-1 aberta e o relatório (tamanho do chunk, medições do AC-8 num notebook
comum e no projetor, se houver), o **usuário** escolhe uma das três saídas, registrada aqui
com a data:
- **(a) 3D no app todo:** substituir o `Mascot` 2D em todas as telas.
- **(b) 3D só no palco da apresentação:** o 3D entra apenas no modo apresentação (spec 028);
  o resto continua 2D.
- **(c) 2D melhorado (nível A):** manter SVG e trazer para o 2D o que o spike mostrar que vale:
  olhar que segue o cursor, ocioso mais vivo, reações a eventos, deslocamento pelo palco na
  apresentação e transições entre humores.

Critérios: **aparência** (comparação lado a lado do AC-7); **FPS médio ≥ 50** e mínimo
aceitável num notebook comum (sem GPU dedicada); **peso do chunk** gzip do AC-1;
**estimativa de paridade** com o 2D (personalização completa da spec 008 e figura da 018,
voz da 027, apresentação da 028), em dias de trabalho. Se o FPS ficar abaixo de 50, (a) fica
descartada.

Decisão: **(b) 3D só no palco da apresentação; 2D no resto do app** — decidido pelo usuário
em 2026-11-23 após o protótipo `/lab/mascote-3d` (chunk ~140 KB gz isolado; estimativa (b)
4–6 dias vs (a) 12,5–17,5). Continuação na spec 031.

## Fora de escopo
- Trocar o mascote em produção (Home, dock, Perfil, apresentação).
- Personalização 3D completa (todas as chaves da spec 008, figura feminina da 018, acessórios).
- V3/V4 da voz (visemas, fonemas, expressões guiadas pelo texto).
- GSAP ou qualquer outra biblioteca de animação; modelos/texturas externos.
- Mudanças no backend, na API ou nas métricas do RAG.

## Riscos
- **Peso do bundle:** `three` é grande; mitigado pelo chunk só da rota de laboratório e pela
  medição do AC-1. Em (a) o peso entraria no app todo.
- **GPU fraca/projetor:** notebooks com GPU integrada ou projetor em resolução alta podem cair
  abaixo de 50 FPS; o AC-8 mede, e o fallback do AC-9 cobre ausência de WebGL. Considerar
  limitar `devicePixelRatio` se o FPS cair.
- **Paridade da personalização (spec 008):** cada opção de cabelo/gorro e a figura feminina
  viram geometria própria; o spike só cobre cores, então a estimativa de paridade é a parte
  mais incerta.
- **Licença:** `three` é MIT; o estilo "Moments of Happiness" serve só de referência visual —
  nenhum código, modelo ou asset do projeto original é copiado.

## Impacto
- Nenhum impacto em métricas do RAG, juízes ou avaliação; nada no backend muda.

## Plano (preenchido depois da aprovação)
| Passo | Arquivo | Subagente | Verificação |
|---|---|---|---|
| 1 | `specs/030-avaliacao-mascote-3d.md` | engenheiro-ia | revisão do líder |
| 2 | `mascot3d-math.ts` + `mascot3d-math.test.mjs`, `package.json` (`test:mascot3d`, `three`, `@types/three`) | engenheiro-frontend | AC-10 vermelho → verde |
| 3 | `src/app/lab/mascote-3d/page.tsx`, `src/components/mascot3d/` | engenheiro-frontend | AC-1…AC-9, `typecheck`/`lint`/`build` |
| 4 | relatório do spike (chunk gzip, medições) | engenheiro-frontend + líder técnico | AC-1, AC-8 |
| 5 | seção "Critério de decisão" | usuário + líder técnico | decisão registrada |
| 6 | — | líder técnico | AC-11, harness completo |
