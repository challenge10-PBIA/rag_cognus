# 024 — Prática com Plateia

- **Status:** aprovada (2026-11-23)
- **Módulos:** backend `src/rag_cognus/api/app.py` (`MODES`); front irmão `frontend_UI/`
  (Next 16): `src/components/session/session-flow.tsx`, `src/components/train/train-hub.tsx`,
  `src/lib/audio/use-recorder.ts` (máscara de silêncio durante reações, AC-8), novos `src/lib/audience/sounds.ts`,
  `src/lib/audience/plan.ts`, `src/lib/audience/plan.test.mjs`, `public/audios/plateia/`,
  `package.json` (script `test:audience`)
- **Testes:** `tests/test_api.py` (AC-1); front: `npm run test:audience` (node `--test`, padrão
  de `src/components/mascot/mascot-math.test.mjs`) + `typecheck`/`lint`/`build`
- **Relacionadas:** 022 (hub `/treinar`, sessão em `/treinar/sessao`), 023 (tokens), 025
  (palco escuro e contagem 3-2-1, pré-requisito)

## Problema
Os modos de sessão (`MODES` em `api/app.py`: `daily_pitch`, `reuniao_1_1`,
`apresentacao_tecnica`, `espontanea`) treinam a fala em silêncio. Falar em público envolve
reação da plateia e distrações, e nada no app simula essa pressão. A pasta
`audios/Áudios Cognus/` tem hoje três efeitos de plateia (ambiente de auditório, burburinho e
aplausos), mas nenhum é usado nem está publicado no front.

## Comportamento esperado
Um novo modo **Prática com Plateia** aparece em "Sessão de fala". Antes de começar, a pessoa
escolhe a intensidade da plateia. Na contagem da spec 025 a plateia se acomoda (ambiente de
auditório em fade-in), e esse ambiente segue baixo em loop durante a fala; a plateia reage às
métricas ao vivo que já existem (silêncio longo vira burburinho, ritmo bom vira aplauso
curto); na intensidade mais alta há ondas de burburinho aleatórias. Ao concluir, aplausos. A
análise da fala continua sendo da fala, não da plateia.

### Áudios publicados (AC-4)
Durações e tamanhos de origem medidos nos arquivos; o tamanho do `.m4a` é estimado
(30,7 s × 64 kbps) e será conferido no AC-4. A pasta de origem tem ainda
`freesound_community-group-walking-in-auditorium-75855 2.mp3`, cópia idêntica (`cmp`) do
arquivo Freesound, que é ignorada.
| Publicado (`public/audios/plateia/`) | Origem (`audios/Áudios Cognus/`) | Categoria | Rótulo | Duração | Tamanho |
|---|---|---|---|---|---|
| `auditorio.m4a` | `freesound_community-group-walking-in-auditorium-75855.mp3` (984 KB, mono 48 kHz), reencodado AAC mono 64 kbps (`afconvert -f m4af -d aac -b 64000 -c 1`) | ambiente | Plateia se acomodando | 30,7 s | ≈ 0,25 MB |
| `burburinho.mp3` | `ElevenLabs__“Crowd_murmuring_in_background,_people_whispering_in_shock,_faint_crying,_chaotic_village_atmospher.mp3` (cópia) | inquietacao | Plateia inquieta | 8,5 s | 137 KB |
| `aplausos.mp3` | `ElevenLabs_crowd_applause.mp3` (cópia) | aplauso | Plateia aplaude | 8,0 s | 129 KB |

Total ≈ 0,5 MB (limite do AC-4: ≤ 3 MB). Origem: os dois `.mp3` vêm do ElevenLabs Sound
Effects; o ambiente vem do Freesound (community, id 75855).

### Intensidades (AC-3, AC-5)
| | Leve | Moderada (padrão) | Intensa |
|---|---|---|---|
| Ambiente (`auditorio`): fade-in na contagem, loop na gravação | sim, ganho ≤ 0,15 | sim, ganho ≤ 0,2 | sim, ganho ≤ 0,3 |
| Burburinho no silêncio ao vivo (> 3 s; sobe um degrau > 6 s) | não | sim | sim |
| Aplauso curto por ritmo "Ideal" | não | sim | sim |
| Ondas de burburinho aleatórias (20–45 s, duração 4–8 s) | não | não | sim |
| Encerramento | aplauso completo | aplauso completo | aplauso completo |

## Critérios de aceite
- **AC-1:** `MODES` em `src/rag_cognus/api/app.py` ganha `pratica_plateia` com `label`
  "Prática com Plateia", `scenario` "Apresentação para um auditório que reage ao vivo",
  `audience` "leigo" (um auditório aberto; está em `AUDIENCES`), `context` "palestra" (está em
  `CONTEXTS`) e `minutes` 3. O modo aparece em `GET /v1/meta` (e em `GET /v1/home`, que usa o
  mesmo `_modes()`), e `POST /v1/sessions` com `mode=pratica_plateia` responde 201 e devolve
  `mode_label` "Prática com Plateia". Teste em `tests/test_api.py` (estender
  `test_meta_and_profile` ou teste novo), com os fakes de sempre, sem Whisper nem Ollama.
- **AC-2:** O modo aparece no hub `/treinar` (cartão "Sessão de fala", que já lista
  `meta.modes`) e na grade "Escolha o modo" do Setup, ambos com o selo **"Imersivo"**; no
  Setup, com o modo selecionado, aparece o aviso **"Use fones de ouvido"** com uma frase
  explicando que o som da plateia não deve vazar para o microfone. A grade do Setup
  (`lg:grid-cols-4`) acomoda o 5º modo sem quebrar o layout em 360 px e no desktop.
- **AC-3:** Com o modo selecionado, o Setup mostra um seletor de intensidade **Leve /
  Moderada / Intensa** (grupo de rádio acessível, rótulos em português, Moderada marcada por
  padrão), cada opção com uma frase curta do que toca, conforme a tabela de intensidades. A
  intensidade escolhida vale para a sessão inteira, inclusive após "Reiniciar". Os demais
  modos não mostram o seletor nem tocam som.
- **AC-4:** Os 3 arquivos da tabela "Áudios publicados" são gravados em
  `frontend_UI/public/audios/plateia/` com nomes ASCII: `auditorio.m4a` (o `.mp3` do Freesound
  reencodado em AAC mono 64 kbps com `afconvert -f m4af -d aac -b 64000 -c 1`, disponível no
  macOS), `burburinho.mp3` e `aplausos.mp3` (cópias sem recodificar dos `.mp3` do ElevenLabs).
  A cópia duplicada `... 75855 2.mp3` é ignorada. Os originais em `rag_cognus/audios/` ficam
  intocados (`git status` sem mudança nessa pasta por causa desta spec). O total publicado em
  `public/audios/plateia/` é ≤ 3 MB (`du -ch public/audios/plateia/*`). A pasta tem um
  `CREDITOS.md` com a origem de cada arquivo: `burburinho.mp3` e `aplausos.mp3` gerados no
  ElevenLabs Sound Effects; `auditorio.m4a` do Freesound (community, id 75855). O manifesto
  tipado `src/lib/audience/sounds.ts` lista cada som com `id`, `file`, `category`
  (`"ambiente" | "inquietacao" | "aplauso"`) e `label` em português: "Plateia se acomodando"
  (`auditorio`), "Plateia inquieta" (`burburinho`), "Plateia aplaude" (`aplausos`); todo
  arquivo de áudio do manifesto existe na pasta e vice-versa (`CREDITOS.md` não conta).
  Licença: confirmar que o plano ElevenLabs usado permite uso comercial sem atribuição e qual
  a licença do item Freesound 75855 fica como pendência no PR; não bloqueia o desenvolvimento
  local, mas o modo não vai para produção pública antes de ela ser resolvida.
- **AC-5:** Comportamento na sessão, por intensidade (tabela de intensidades):
  (a) durante a contagem da spec 025 (AC-6 dela) o `auditorio` entra em fade-in (plateia se
  acomodando) e segue em loop como ambiente durante a gravação ativa, com ganho por
  intensidade (relativo ao volume da plateia): Leve ≤ 0,15, Moderada ≤ 0,2, Intensa ≤ 0,3;
  (b) Moderada e Intensa: com o silêncio ao vivo (`live.silence`) > 3 s (`LONG_SILENCE` de
  `use-recorder.ts`), o `burburinho` entra em fade-in e sai em fade-out (~1 s) quando a fala
  volta; se o silêncio passar de 6 s, o ganho do burburinho sobe mais um degrau;
  (c) Moderada e Intensa: com o ritmo ao vivo (`ppm`) na faixa "Ideal" de `paceLabel`
  (120–160) em duas leituras seguidas (~20 s) toca um aplauso curto (~3 s de `aplausos`, com
  fade-out);
  (d) Intensa acrescenta ondas de burburinho em intervalos aleatórios de 20 a 45 s, cada uma
  com duração de 4 a 8 s (fade-in/fade-out), nunca nos primeiros 30 s da gravação;
  (e) Leve toca só o ambiente e, ao concluir, o aplauso final;
  (f) nunca há duas reações ao mesmo tempo (o ambiente não conta) e há um intervalo mínimo de
  8 s entre reações;
  (g) ao clicar "Concluir e Analisar com IA", o ambiente para e toca o aplauso completo.
- **AC-6:** O agendamento das reações é uma função pura em `src/lib/audience/plan.ts`:
  `planReactions(estado, intensidade, rng)` recebe o estado da plateia (tempo decorrido,
  silêncio atual, leituras de `ppm`, reação em curso e seu degrau de ganho, fim da última
  reação, próximo instante e duração da onda de burburinho), a intensidade e um
  `rng: () => number` injetado, e devolve as ações a aplicar agora (iniciar/subir/encerrar
  burburinho, tocar aplauso curto) e o novo estado, sem tocar áudio nem ler relógio. `plan.ts`
  só importa tipos (nada em tempo de execução de outro `.ts`), como `articulation-math.ts`,
  para rodar no `node --test` com type stripping. `src/lib/audience/plan.test.mjs` cobre, com
  `rng` fixo: cada regra do AC-5 (b)–(f) (burburinho > 3 s e degrau > 6 s, saída quando a
  fala volta, aplauso por ritmo, ondas entre 20–45 s com 4–8 s e nunca antes de 30 s, uma
  reação por vez e ≥ 8 s entre reações) e que Leve nunca devolve reação durante a fala. O `package.json` ganha
  `"test:audience": "node --disable-warning=MODULE_TYPELESS_PACKAGE_JSON --test
  src/lib/audience/plan.test.mjs"`.
- **AC-7:** Controles na sessão: botão **"Silenciar plateia"** (alternável, `aria-pressed`) e
  controle de volume da plateia (`input type="range"` com rótulo), sem afetar a gravação.
  Pausar a sessão pausa o ambiente e as reações (e o agendador não avança); retomar continua.
  Concluir, Sair (spec 025 AC-5), Reiniciar, navegar para fora ou desmontar o componente para
  todo som e libera o contexto de áudio da plateia. Nenhum som toca antes de um gesto do
  usuário: o contexto de áudio da plateia é criado/retomado de forma síncrona no clique de
  "Começar sessão", antes de qualquer `await` (política de autoplay); se ainda assim o
  navegador bloquear, a sessão segue sem som e mostra "Não consegui tocar o som da plateia".
- **AC-8:** Integridade da análise. Achado: `use-recorder.ts` já pede
  `getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } })`;
  esse AC exige que continue assim nos dois campos. `autoGainControl` fica como hoje (padrão do
  navegador), porque mudá-lo alteraria a métrica de projeção de todos os modos. A abordagem:
  (a) o som da plateia toca num `AudioContext` próprio, ligado só à saída, nunca ao nó do
  gravador; (b) o aviso de fone (AC-2) é repetido na contagem, já que o ambiente toca durante a
  gravação (spec 025 AC-6); (c) no medidor ao vivo, enquanto o `burburinho` ou o `aplausos`
  estiver tocando (o ambiente não conta) e por 300 ms depois do fim do fade-out, o silêncio em
  curso não é encerrado nem contado como fala, de modo que o burburinho do silêncio não "se
  cancela" e a contagem de pausas ao vivo não muda por causa dele. **Risco documentado:** sem
  fone, o cancelamento de eco do navegador reduz, mas não garante zerar, o vazamento da
  plateia (ambiente, burburinho, aplausos) para o WAV; a análise final do backend (Whisper +
  `analyze_words`) pode então perder pausas ou transcrever murmúrios. Isso não é garantível sem mudar a API (fora de escopo); o PR registra o
  teste manual com e sem fone.
- **AC-9:** Acessibilidade: o início do ambiente na contagem mostra a legenda "Plateia se
  acomodando", e cada reação tocada mostra a legenda com o `label` do manifesto ("Plateia
  inquieta" no burburinho, "Plateia aplaude" no aplauso curto e no final) por ~3 s, numa
  região `aria-live="polite"`; a legenda do burburinho não se repete quando o ganho sobe de
  degrau. Com "Silenciar plateia" ligado, as legendas não aparecem. Efeitos
  visuais da plateia (ex.: brilho ou ícone pulsando junto da legenda) respeitam
  `prefers-reduced-motion: reduce` (sem animação; só o texto).
- **AC-10:** Verificação: no `frontend_UI`, `npm run typecheck && npm run lint && npm run build
  && npm run test:audience` passam (e `test:mascot`/`test:articulation` seguem verdes); no
  backend, `python hermes/harness/check.py` passa.

## Fora de escopo
- Plateia visual (avatares, vídeo) e reações a vícios de linguagem em tempo real.
- Mudar a API de sessões para receber os instantes das reações e descontá-los da análise
  (possível spec futura, ver AC-8).
- Gravar ou guardar a escolha de intensidade no backend; métricas novas sobre "fala sob
  pressão".
- Plateia nos outros modos, no exercício fonético e no roteiro do Preparar.

## Riscos
- **Licença dos áudios:** origem conhecida (ElevenLabs Sound Effects; Freesound community id
  75855), mas falta confirmar que o plano ElevenLabs usado permite uso comercial sem
  atribuição e a licença do item Freesound. Não bloqueia o desenvolvimento local; bloqueia
  publicação externa.
- **Conteúdo do burburinho:** o arquivo foi gerado com um prompt que cita "faint crying,
  chaotic village atmosphere"; pode soar como choro ou caos de vila, não como plateia. O
  usuário deve ouvir e validar antes do PR (pendência).
- **Vazamento para o microfone sem fone:** ver AC-8.
- **Loop em AAC:** o encoder AAC acrescenta silêncio de *priming*; um `<audio loop>` pode ter
  um "clique" na emenda. Tocar o ambiente com `AudioBufferSourceNode` (`loop`, `loopStart`/
  `loopEnd`) ou aceitar a emenda após teste de ouvido.
- **Reação ao ritmo depende da IA ao vivo:** o `ppm` vem de `transcribe` a cada 10 s; com a IA
  indisponível (`aiOnline` falso), o aplauso por ritmo não dispara, e isso é aceito.
- **CSS atrasado no dev:** mesma nota operacional da spec 025 (parar o dev, apagar `.next`,
  subir de novo após mudar `globals.css`).

## Dependências e sequência
- Depois da **025** no front (as duas mexem em `session-flow.tsx`; a 024 usa o palco e a
  contagem). O AC-1 (backend) pode correr em paralelo à 025.

## Impacto
- Métricas do RAG e juízes: nenhum. O modo usa `audience`/`context` já existentes, então a
  adaptação ao público (`EvidenceToAudience`) segue igual.
- Métricas da fala: com fone, nenhum; sem fone, risco de pausas a menos e de palavras
  espúrias na transcrição (AC-8).

## Plano (preenchido depois da aprovação)
| Passo | Arquivo | Subagente | Verificação |
|---|---|---|---|
| 1 | `tests/test_api.py` | engenheiro-ia | AC-1 vermelho |
| 2 | `src/rag_cognus/api/app.py` | engenheiro-ia | `python hermes/harness/check.py --changed` |
| 3 | `public/audios/plateia/` (+ `CREDITOS.md`), `sounds.ts` | engenheiro-frontend | AC-4, `du -ch` ≤ 3 MB |
| 4 | `plan.test.mjs` → `plan.ts`, `package.json` | engenheiro-frontend | AC-6 vermelho → verde |
| 5 | `session-flow.tsx`, `train-hub.tsx`, `use-recorder.ts` | engenheiro-frontend | AC-2, AC-3, AC-5, AC-7…AC-9 |
| 6 | — | líder técnico | AC-10 |
