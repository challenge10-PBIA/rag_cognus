# 025 — Início imersivo em todas as práticas

- **Status:** aprovada (2026-11-23)
- **Módulos:** front irmão `frontend_UI/` (Next 16): `src/components/session/session-flow.tsx`
  (`SessionFlowContent`, `Setup`, `LiveSession`, `FinishStep`, `TopBar`),
  `src/lib/audio/use-recorder.ts`, `src/app/globals.css`; leitura de
  `src/components/app-shell.tsx`, `src/components/nav.tsx` (`SESSION_PREFIX`),
  `src/components/mascot/mascot-dock.tsx` (`HIDDEN_PREFIXES`),
  `src/components/onboarding/onboarding.tsx`
- **Testes:** front sem runner de componentes (spec 008 AC-12): verificação por
  `npm run typecheck && npm run lint && npm run build`; `test:mascot` e `test:articulation`
  continuam verdes; nenhum teste Python muda
- **Relacionadas:** 022 (rotas `/treinar/*`, sessão em `/treinar/sessao`), 023 (tokens escuros e
  contraste AA medido), 024 (Prática com Plateia, que usa o palco e a contagem desta spec)

## Problema
Começar uma prática hoje é abrupto. Em `session-flow.tsx`, `begin()` chama `recorder.start()`
(que pede o microfone e já começa a capturar) e troca direto para `LiveSession`: não há
transição, contagem nem sinal claro de "começou". A sessão ativa usa o mesmo tema e o mesmo
layout do resto do app: no desktop, a barra lateral de `AppShell` (`<aside>` com `lg:flex`)
continua visível com todos os links de navegação; só a navegação inferior, o mascote e o
onboarding somem (pelo prefixo `/treinar/sessao`). O estado "PAUSADO" é só um rótulo pequeno ao
lado do cronômetro.

## Comportamento esperado
Em qualquer prática (os modos de `GET /v1/meta`, o exercício fonético `?exercicio=` e o roteiro
do Preparar `?roteiro=1`), ao clicar **"Começar sessão"** o app pede o microfone; com a
permissão, a tela escurece, aparece uma contagem **3-2-1** com "Prepare-se" e, no fim dela, a
gravação começa com um indicador animado de **"Gravando"**. Enquanto a sessão está ativa, tudo
acontece num **palco** escuro, sem a barra lateral nem outra distração. Pausar suaviza o palco;
concluir clareia de volta para a tela de conclusão no tema escolhido.

### Linha do tempo
| Etapa | Tela | Áudio do microfone |
|---|---|---|
| Setup | tema do usuário, como hoje | nenhum |
| Clique em "Começar sessão" | botão em "carregando" enquanto pede o microfone | permissão obtida, nada gravado |
| Contagem (~3 s) | fade para o palco (~600 ms) + "Prepare-se" 3 → 2 → 1 | nada gravado |
| Ao vivo | palco + anel/pulso "Gravando" | gravando (cronômetro parte de 0:00) |
| Pausado | palco atenuado + "Pausado" | suspenso |
| Concluir | fade de volta ao tema do usuário, `FinishStep` | parado |

## Critérios de aceite
- **AC-1:** Dado o Setup de qualquer prática, quando a pessoa clica em "Começar sessão", então a
  permissão do microfone é obtida **antes** de qualquer mudança visual (o botão fica
  desabilitado com o ícone de carregamento, como hoje com `recorder.status === "requesting"`).
  Se a permissão é negada ou falha, a tela não escurece e o erro aparece no Setup, como hoje.
  Com a permissão, a tela escurece numa transição de ~600 ms e mostra "Prepare-se" com a
  contagem 3 → 2 → 1 (1 s por número). A gravação começa ao fim da contagem: o cronômetro
  parte de `0:00` nesse instante e o WAV enviado em `createSession` não contém áudio do
  período da contagem. Isso exige separar, em `use-recorder.ts`, "obter o microfone"
  (`getUserMedia` + `AudioContext` + worklet, com o contexto suspenso ou os blocos
  descartados) de "começar a gravar". Na gravação ativa aparece o indicador "Gravando" com
  anel/pulso animado. "Reiniciar" refaz a contagem antes de gravar de novo.
- **AC-2:** Durante a contagem, a sessão ativa e a pausa, a tela usa um **palco escuro**
  independente do tema escolhido no Perfil (spec 023): um atributo no contêiner da sessão (ex.:
  `data-stage`) redefine os tokens com os valores escuros. Os hex escuros continuam só em
  `globals.css` e não ganham uma terceira cópia: o seletor do palco entra na mesma regra de
  `:root[data-theme="dark"]` (ex.: `:root[data-theme="dark"], [data-stage]`), e
  `color-scheme: dark` vale dentro do palco. O palco ocupa a viewport inteira e a barra lateral
  do desktop (`<aside>` de `AppShell`) fica oculta e fora da ordem de foco: com Tab, nenhum
  link da navegação lateral é alcançável durante a sessão ativa. A navegação inferior, o
  mascote e o onboarding continuam ocultos como hoje. O Setup e o `FinishStep` seguem no tema
  do usuário, com a barra lateral visível.
- **AC-3:** Pausar deixa a imersão visivelmente menor: o anel/pulso de "Gravando" para, o palco
  fica atenuado (ex.: véu mais claro ou menor contraste da onda) e aparece o selo "Pausado" em
  destaque, não só o rótulo pequeno de hoje. Retomar volta ao estado "Gravando". "Concluir e
  Analisar com IA" faz o fade inverso (~600 ms) do palco para o tema do usuário e mostra o
  `FinishStep`.
- **AC-4:** Com `prefers-reduced-motion: reduce`, não há escala, pulso nem anel animado: a
  entrada e a saída do palco são um fade curto (≤ 200 ms) e a contagem mostra só o texto
  ("3", "2", "1"), sem animar os números. O indicador "Gravando" vira um ponto estático com o
  texto.
- **AC-5:** Acessibilidade: ao terminar a contagem o foco vai para o controle principal da
  sessão (Pausar/Retomar); uma região `aria-live="polite"` anuncia "Prepare-se", depois
  "Gravação iniciada", "Sessão pausada" e "Gravação retomada". Durante a sessão ativa há um
  botão visível **"Sair"** e a tecla **Esc** faz o mesmo (se o drawer 3D do exercício estiver
  aberto, Esc fecha só o drawer, como hoje). Sair pausa a gravação e pede confirmação ("Sair
  da sessão? A gravação será descartada.") antes de levar para o `back` da spec 022 AC-7.
  Todo texto do palco tem contraste AA (≥ 4.5:1), o que vale por usar os tokens escuros já
  medidos na spec 023 AC-5.
- **AC-6:** Na Prática com Plateia (spec 024), o ambiente do auditório entra em fade-in
  durante a contagem (plateia se acomodando) e continua em loop, em volume baixo, durante a
  gravação. Isso é intencional: o ambiente é a própria simulação, e por isso vale o aviso de
  fone de ouvido (spec 024 AC-2 e AC-8). Nas demais práticas a contagem e a gravação são
  silenciosas.
- **AC-7:** Verificação: `npm run typecheck && npm run lint && npm run build &&
  npm run test:mascot && npm run test:articulation` passam no `frontend_UI`; o backend não
  muda (`python hermes/harness/check.py` segue verde).

## Fora de escopo
- Telas fora da sessão (Início, Progresso, Aprender, Perfil) e o `Analyzing`.
- Som na contagem das práticas sem plateia, vibração e modo tela cheia do navegador
  (Fullscreen API).
- Mudar métricas ao vivo, `live-coach.ts` ou a análise do backend.

## Riscos
- **CSS atrasado no dev:** editar `globals.css` com `next dev` ligado serve CSS antigo (defeito
  conhecido do `@tailwindcss/turbopack`). Depois de mudar CSS: parar o dev, apagar `.next` e
  subir de novo antes de conferir o palco.
- **Permissão vs. gravação:** hoje `start()` pede o microfone e grava no mesmo passo. Separar
  em duas etapas não pode deixar o microfone aberto ao sair na contagem: sair/desmontar durante
  a contagem libera o `MediaStream` (mesma `release()` de hoje).
- **Esc acidental:** por isso Esc pausa e pede confirmação, nunca descarta direto.

## Dependências e sequência
- Vem **antes** da 024: as duas tocam `session-flow.tsx`, e a 024 usa o palco e a contagem.
- Depende da 022 (rotas) e da 023 (tokens escuros), já aprovadas.

## Impacto
- Nenhum impacto em métricas do RAG, juízes ou API. O WAV analisado deixa de incluir o
  instante entre o clique e o início real da fala (antes começava a gravar já no clique).

## Plano (preenchido depois da aprovação)
| Passo | Arquivo | Subagente | Verificação |
|---|---|---|---|
| 1 | `use-recorder.ts` (obter microfone × gravar) | engenheiro-frontend | AC-1, `typecheck` |
| 2 | `globals.css` (seletor do palco na regra escura) | engenheiro-frontend | AC-2, dev reiniciado |
| 3 | `session-flow.tsx` (contagem, palco, pausa, Sair/Esc, `aria-live`) | engenheiro-frontend | AC-1…AC-5 |
| 4 | — | líder técnico | AC-7 |
