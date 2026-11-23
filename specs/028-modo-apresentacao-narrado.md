# 028 — Modo apresentação narrado (V2)

- **Status:** aprovada (2026-11-23)
- **Depende de:** 027 (voz, tocador único, lip sync e fallback)
- **Módulos:** backend `src/rag_cognus/voice.py` (função de síntese e cache da 027),
  `src/rag_cognus/cli.py` (subcomando `voice-pregen`). Front irmão `frontend_UI/` (Next 16):
  novos `public/presentation/roteiro.json`, `public/presentation/audio/` (mp3 gerados +
  `manifest.json`), `src/lib/presentation/machine.ts`,
  `src/lib/presentation/machine.test.mjs`, `src/lib/presentation/roteiro.test.mjs`,
  `src/components/presentation/presentation.tsx`; alterados
  `src/components/app-shell.tsx` (monta o modo), `src/components/profile/profile-view.tsx`
  (botão), `src/components/mascot/mascot-dock.tsx` (some durante o modo),
  `src/components/onboarding/onboarding.tsx` (reuso de `visibleAnchor` e `.tour-spotlight`;
  não abre por cima do modo), âncoras `data-present` nas telas do roteiro, `package.json`
  (script `test:presentation`)
- **Testes:** `tests/test_voice.py` (pré-geração com provedor falso); front:
  `npm run test:presentation` (node `--test`) + `typecheck`/`lint`/`build`
- **Relacionadas:** 014 (tour com `data-tour`), 022 (rotas), 023 (contraste AA), 024 e 025
  (plateia, palco escuro/scrim), 026 (Início), 027 (voz)

## Problema
A apresentação do projeto hoje depende de alguém clicar pelas telas e explicar tudo de
memória. O tour do onboarding (spec 014) só aponta os itens da navegação com texto curto e
sem voz. Queremos que o próprio mascote guie a apresentação: fale com voz calma, leve a tela
para o lugar certo e destaque o que está explicando, funcionando mesmo sem internet no dia.

## Comportamento esperado
No Perfil, o botão **"Modo apresentação"** (ou a URL `?apresentacao=1`) abre uma camada em
tela cheia: o fundo escurece, o mascote aparece grande e fala o primeiro passo do roteiro com
a legenda em letra grande. Cada passo leva o app para uma tela, acende um holofote
(spotlight) no elemento explicado e toca o áudio pré-gerado daquele passo, com a boca em
sincronia. O apresentador avança com o teclado ou um passador de slides; um indicador mostra
"3/10". No fim, o mascote convida a plateia a fazer perguntas.

Os áudios são gerados **antes**, por um comando que o usuário roda uma vez
(`rag-cognus voice-pregen`); no dia, a apresentação toca os arquivos locais, sem rede.

### Formato do roteiro (`frontend_UI/public/presentation/roteiro.json`)
Versionado no git, lido pelo front (estático) e pelo CLI (Python). Fica em `public/` para
os dois lerem o mesmo arquivo sem duplicar texto.
```json
{
  "version": 1,
  "voice_note": "texto revisado pelo usuário em AAAA-MM-DD",
  "steps": [
    {"id": "abertura", "route": "/", "anchor": null, "mood": "feliz",
     "text": "...", "audio": "abertura.mp3"}
  ]
}
```
- `anchor`: `null` (mascote no centro, sem holofote), `"tour:<id>"` (usa `data-tour` da
  navegação) ou `"present:<id>"` (novo atributo `data-present` posto na tela).
- `mood`: `feliz` | `neutro` | `pensativo` (mesmos humores do mascote).
- `text`: até 3 frases, ≤ 600 caracteres (limite da 027), português, tom calmo.
- `audio`: `<id>.mp3` em `public/presentation/audio/`.
`audio/manifest.json` (gerado): `{"<id>": {"file": "<id>.mp3", "sha256": "<chave do cache da
027>"}}` — permite saber se o texto mudou depois da última geração.

### Rascunho do roteiro (o usuário revisa o texto antes de gerar o áudio)
| # | id | route | anchor | mood | text |
|---|---|---|---|---|---|
| 1 | `abertura` | `/` | — | feliz | Olá, eu sou o mascote do Cognus. O Cognus é um treinador de comunicação que escuta você falar e devolve um retorno claro e gentil. Hoje eu vou mostrar como ele funciona. |
| 2 | `problema` | `/` | — | pensativo | Falar com clareza e com calma é difícil, principalmente quando alguém está olhando. Quase ninguém recebe um retorno honesto sobre o próprio ritmo, as pausas e os vícios de linguagem. O Cognus nasceu para dar esse retorno, todos os dias. |
| 3 | `inicio` | `/` | `present:home-next-step` | neutro | Esta é a tela de Início. Ela responde uma pergunta só: qual é o meu próximo passo? Um toque em "Começar agora" e o treino do dia já começa. |
| 4 | `treinar` | `/treinar` | `tour:treinar` | neutro | Em Treinar ficam as práticas. Você grava uma sessão de fala e recebe a análise de ritmo, pausas, vícios, clareza e dicção. |
| 5 | `articulacao` | `/treinar/articulacao` | `present:articulation-3d` | feliz | Aqui é a Articulação. Uma boca em 3D mostra como formar cada som, e você repete no seu tempo. |
| 6 | `plateia` | `/treinar/sessao` | `present:audience-mode` | neutro | E quando a pressão aumenta? Na Prática com Plateia, a sala escurece, uma contagem prepara você e a plateia reage à sua fala. Silêncio longo vira burburinho; ritmo bom vira aplauso. |
| 7 | `progresso` | `/progresso` | `tour:progresso` | feliz | Em Progresso você acompanha a sua evolução. O app aponta o pilar que mais vale treinar e guarda o histórico das suas sessões. |
| 8 | `aprender` | `/aprender` | `tour:aprender` | neutro | Em Aprender você tira dúvidas sobre comunicação. Cada resposta cita as fontes da base de conhecimento e, quando a base não sabe, eu digo que não sei. |
| 9 | `privacidade` | `/perfil` | `present:privacy` | neutro | Uma coisa importante: o seu áudio e a análise da sua fala ficam no seu computador. A transcrição e o modelo de linguagem rodam localmente, e você decide o que é registrado. |
| 10 | `encerramento` | `/` | — | feliz | Esse é o Cognus: um lugar calmo para treinar a sua voz todos os dias. Obrigado por me ouvir. Agora a palavra é de vocês: quais são as suas perguntas? |

Novas âncoras `data-present` (o engenheiro-frontend coloca): `home-next-step` (cartão "Seu
próximo passo", spec 026), `articulation-3d` (viewer 3D), `audience-mode` (opção "Prática com
Plateia" no setup da sessão, sem iniciar gravação), `privacy` (bloco de privacidade do
Perfil).

## Critérios de aceite
- **AC-1 (roteiro versionado):** Existe `frontend_UI/public/presentation/roteiro.json` com
  `version` e 8 a 10 passos no formato acima, cobrindo, nesta ordem: abertura, problema,
  Início/próximo passo, Treinar, Articulação 3D, Prática com Plateia + início imersivo,
  Progresso, Aprender (respostas com fontes), privacidade (áudio e análise locais) e
  encerramento convidando perguntas. Cada `text` tem no máximo 3 frases e 600 caracteres,
  em português. O texto final é o revisado pelo usuário (campo `voice_note` com a data).
- **AC-2 (pré-geração):** `rag-cognus voice-pregen [--roteiro CAMINHO] [--out PASTA]
  [--force]` (padrões: `../frontend_UI/public/presentation/roteiro.json` e
  `../frontend_UI/public/presentation/audio/`) lê o roteiro, sintetiza cada `text` com a
  **mesma função de síntese e o mesmo cache** da spec 027 (sem exigir a API no ar nem
  `voice_enabled`, pois o próprio usuário roda o comando), grava `<id>.mp3` e
  `manifest.json`, e pula passos cujo `sha256` no manifesto não mudou (sem `--force`). Com
  provedor `off` ou falha num passo, imprime em português quais passos faltaram e sai com
  código ≠ 0, mantendo os arquivos já gerados. O comando só roda quando o usuário o executa
  (rede real); nenhum teste o chama contra o ElevenLabs. Com os arquivos gerados, a
  apresentação funciona com a rede desligada.
- **AC-3 (entrada):** O Perfil tem o botão **"Modo apresentação"**; abrir qualquer rota com
  `?apresentacao=1` também entra no modo. Ao entrar: o dock do mascote e o onboarding não
  aparecem; o mascote aparece grande; o passo atual navega para `route` (`router.push`),
  espera a âncora ficar visível (até 3 s; reuso de `visibleAnchor`) e a destaca com o
  holofote `.tour-spotlight`; sem âncora (ou `null`), o mascote fica centralizado. A fala
  começa no primeiro gesto do apresentador (o botão de entrada ou uma tecla), por causa da
  política de autoplay.
- **AC-4 (controles):** Próximo: `→`, `Espaço`, `PageDown` (passadores de slide enviam
  `PageDown`/`PageUp`); Anterior: `←`, `PageUp`; Pausar/Retomar: `P` e botão; Sair: `Esc` e
  botão (volta à tela de onde entrou e remove `?apresentacao=1`). Botões visíveis com
  `aria-label` em português e indicador "N/total" (`aria-live="polite"`). Trocar de passo
  interrompe a fala anterior (tocador único da 027). Avanço automático ao fim do áudio é uma
  opção ("Avançar sozinho", padrão desligado). Teclas não agem quando o foco está num campo
  de texto.
- **AC-5 (imersão e legibilidade):** Fora do holofote o fundo escurece (reuso do scrim/palco
  das specs 014/025); a legenda fica numa faixa inferior com fonte
  `clamp(1.75rem, 3.2vw, 3rem)`, no máximo 3 linhas, legível a 3 m num projetor 1080p;
  todo texto e controle tem contraste AA (≥ 4.5:1) nos temas claro e escuro (tokens da
  023). Com `prefers-reduced-motion: reduce`, sem transições de holofote nem do mascote
  (troca direta) e boca em abrir/fechar (027 AC-6).
- **AC-6 (robustez):** Áudio do passo ausente ou com erro → cadeia de fallback da 027: TTS
  ao vivo (`POST /v1/voice/speak` com `purpose="presentation"`, só se a voz estiver ligada e
  disponível) → voz pt-BR do navegador → só legenda; a apresentação nunca para por isso. Rota
  com dados vazios (sem sessões, sem Gold) mostra o estado vazio da tela e o passo segue;
  âncora que não aparece em 3 s → passo sem holofote. Nenhum desses casos mostra erro em
  tela.
- **AC-7 (testes):** `src/lib/presentation/machine.ts` é uma máquina de estados pura
  (`idle → speaking ⇄ paused → ended`, eventos `START`, `NEXT`, `PREV`, `PAUSE`, `RESUME`,
  `AUDIO_END`, `EXIT`) testada com `node --test`: próximo/anterior nos limites (PREV no 1
  fica no 1; NEXT no último vai a `ended`), pausa e retomada no mesmo passo, `AUDIO_END` só
  avança com "Avançar sozinho", `EXIT` de qualquer estado. `roteiro.test.mjs` valida o
  `roteiro.json`: ids únicos, 8–10 passos, campos obrigatórios, ≤ 3 frases e ≤ 600
  caracteres, `mood` válido, `route` existente em `src/app/**/page.tsx`, `audio = <id>.mp3`
  e, se `audio/manifest.json` existir, todo passo listado nele. No backend,
  `tests/test_voice.py` cobre o `voice-pregen` com provedor falso em `tmp_path` (gera,
  pula inalterados, `--force`, falha parcial com código ≠ 0).
- **AC-8 (verificação):** `python hermes/harness/check.py` termina em `HARNESS OK`; no
  `frontend_UI`, `npm run typecheck && npm run lint && npm run build`,
  `npm run test:presentation`, `npm run test:voice` e os testes existentes passam. Ensaio
  manual (registrado no relatório): roteiro completo com a rede desligada e com um passador
  de slides.

## Fora de escopo / próximas specs
- **V3 — Conversa por voz (push-to-talk):** segurar um botão (ou tecla) para falar com o
  mascote; o áudio é transcrito localmente com faster-whisper (`speech.py`), o texto vai ao
  coach ou ao RAG e a resposta volta falada pela 027. O áudio nunca sai da máquina; só o
  texto da resposta vai ao TTS. Exige spec própria para latência, interrupção (barge-in) e
  guarda de números nas respostas faladas.
- **V4 — Co-apresentador:** durante o modo apresentação, a plateia faz perguntas sobre o
  projeto e o mascote responde com o RAG sobre uma base de documentos do próprio Cognus
  (README, specs), sempre citando a fonte ou se abstendo. Depende da V3 e de um índice
  separado da Gold; precisa de avaliação própria (juízes, precision@k) antes de ir ao palco.
- Editor do roteiro na interface, vários roteiros e gravação em vídeo da apresentação.

## Riscos
- **Texto e áudio fora de sincronia:** editar o roteiro sem rodar `voice-pregen` deixa áudio
  velho; o manifesto com `sha256` e o teste do roteiro acusam a diferença.
- **Tamanho do repo:** 10 mp3 de ~15 s a 128 kbps ≈ 2,5 MB; aceitável, mas a decisão de
  versionar os mp3 é do usuário.
- **Âncoras que mudam:** refatorar uma tela pode remover um `data-present`; o passo segue sem
  holofote (AC-6), e o ensaio manual pega o caso.

## Decisões (usuário, 2026-11-23)
1. **Roteiro:** o rascunho acima é revisado pelo usuário **antes** do `voice-pregen`; só o
   texto aprovado (com `voice_note` datado) vira áudio.
2. **Áudios versionados:** os mp3 gerados ficam no git do `frontend_UI`
   (`public/presentation/audio/`), para a apresentação funcionar em qualquer máquina sem rede.
3. **Avanço manual por padrão:** "Avançar sozinho" começa desligado.
4. **Sem passo de MLflow/Grafana** no roteiro.
5. **Voz híbrida (spec 027):** a pré-geração usa `purpose="presentation"`, isto é,
   `TTS_PRESENTATION_PROVIDER` (padrão `elevenlabs`; sem chave/voz cai para o Piper local).
   Com ElevenLabs o arquivo é `<id>.mp3`; se cair para o Piper, `<id>.wav` (o campo `audio`
   do roteiro e o manifesto registram o arquivo realmente gerado).

## Impacto
- Nenhum impacto em métricas do RAG, juízes ou MLflow. Custo do ElevenLabs (plano gratuito,
  uso não comercial, com atribuição): uma geração por
  fala (≈ 2 mil caracteres no roteiro todo), regenerada só quando o texto muda.

## Plano (preenchido depois da aprovação)
| Passo | Arquivo | Subagente | Verificação |
|---|---|---|---|
| 1 | `roteiro.json` (texto aprovado) | líder técnico + usuário | AC-1 |
| 2 | `cli.py` (`voice-pregen`), `tests/test_voice.py` | engenheiro-devops + engenheiro-ia | AC-2, AC-7 (backend) |
| 3 | `machine.ts` + teste, `roteiro.test.mjs`, `package.json` | engenheiro-frontend | AC-7 |
| 4 | `presentation.tsx`, `app-shell.tsx`, `profile-view.tsx`, âncoras `data-present` | engenheiro-frontend | AC-3…AC-6 |
| 5 | rodar `rag-cognus voice-pregen` (rede real) | usuário | áudios + manifesto |
| 6 | — | líder técnico | AC-8 + ensaio offline |
