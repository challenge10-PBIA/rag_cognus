# 027 — Voz do avatar (V1)

- **Status:** aprovada (2026-11-23) — modelo híbrido: Piper local (padrão) + ElevenLabs
  (opcional, apresentação)
- **Módulos:** backend novo `src/rag_cognus/voice.py` (provedor TTS, cache, guarda);
  `src/rag_cognus/api/app.py` (rota `POST /v1/voice/speak`, `GET /v1/health`,
  `/v1/mascot/settings`), `src/rag_cognus/api/schemas.py` (`SpeakIn`, `Health`,
  `MascotSettings`), `src/rag_cognus/config.py` (variáveis `TTS_*`/`PIPER_*`/`ELEVENLABS_*`),
  `.env.example`; leitura de `src/rag_cognus/coach.py` (`grounded`, `_numbers`).
  Front irmão `frontend_UI/` (Next 16): `src/components/mascot/mascot.tsx` (prop `speaking`,
  boca na linha ~211), `src/components/mascot/mascot-dock.tsx` (balão de dica e painel
  "Me explica…"), `src/components/profile/profile-view.tsx` (seção "Mascote, privacidade e
  tutorial"), `src/lib/api/client.ts`, novos `src/lib/voice/player.ts`,
  `src/lib/voice/lipsync.ts`, `src/lib/voice/lipsync.test.mjs`, `package.json`
  (script `test:voice`)
- **Testes:** `tests/test_voice.py` (novo), `tests/test_api.py` (rotas), `tests/test_config.py`
  (variáveis novas); front: `npm run test:voice` (node `--test`, padrão de
  `mascot-math.test.mjs`) + `typecheck`/`lint`/`build`
- **Relacionadas:** 008 (mascote), 013 (mascote coach: dicas, explicações e guarda de
  números), 014 (onboarding e privacidade), 023 (tokens e contraste AA), 024 (padrão de
  `AudioContext` próprio em `src/lib/audience/engine.ts`), 028 (modo apresentação, depende
  desta)

## Problema
O mascote só fala por texto: dicas no balão e explicações no painel "Me explica…". A boca
anima com uma senoide enquanto a explicação carrega (`speaking={explain.isPending}`), sem som
nenhum. Para a apresentação do projeto ser imersiva o avatar precisa falar de verdade, com
voz calma e o mais humana possível, e a boca precisa acompanhar o som. O app não tem hoje
nenhuma saída de voz.

## Comportamento esperado
A **"Voz do mascote"** vem ligada no Perfil, porque a voz padrão é o **Piper**, que roda no
próprio computador (nada sai da máquina). Há um botão **"Ouvir"** no balão de dica e no
painel "Me explica…". Ao tocar, o mascote fala o texto com uma voz pt-BR calma; a boca abre e
fecha seguindo o volume real do áudio; a legenda (o próprio texto) continua visível. Com
**"Falar automaticamente"** (desligado por padrão), dicas e explicações novas são faladas sem
precisar tocar. Trocar de tela ou pedir outra fala corta a anterior. Sem voz disponível
(modelo Piper não baixado, provedor desligado), o app usa a voz pt-BR do navegador ou fica só
na legenda, sem erro na tela.

Para a **apresentação** (spec 028, `purpose="presentation"`) a voz pode vir do
**ElevenLabs** (mais humana), se houver chave e voz configuradas; senão cai para o Piper.
Só nesse caso o texto sai da máquina, com o nome do perfil trocado por "você"; áudio e dados
da pessoa nunca saem. A mesma fala é gerada uma vez e depois vem do cache local.

### Contrato da API (entre engenheiro-ia e engenheiro-frontend)
```
POST /v1/voice/speak
  corpo:  {"text": str (1..600, após normalizar espaços),
           "purpose": "tip" | "explain" | "presentation" = "tip",
           "facts": [{"label": str, "value": str}] = []}   # obrigatório se purpose=explain
  200:    audio/wav (piper) | audio/mpeg (elevenlabs) (bytes)
          X-Voice-Cache: hit | miss
          X-Voice-Provider: piper | elevenlabs
  403:    {"detail": "A voz do mascote está desligada no Perfil."}
  422:    texto vazio/longo, purpose inválido, ou (explain) número fora dos fatos:
          {"detail": "Esse texto cita números que não estão nos fatos; não vou falar."}
  503:    {"detail": "Voz indisponível agora: <motivo em português>."}
          sem modelo Piper: {"detail": "Voz local não instalada: rode `rag-cognus voice-download`."}

GET /v1/health   → campos novos: "voice_available": bool,
                   "voice_provider": "piper"|"elevenlabs"|"off",
                   "presentation_voice_provider": "piper"|"elevenlabs"|"off"
GET/PUT /v1/mascot/settings → campos novos: "voice_enabled": bool = true,
                                            "voice_autoplay": bool = false
```
Os campos do `health` são calculados pela configuração, pela existência do modelo Piper em
disco (`PIPER_DATA_DIR/<PIPER_VOICE>.onnx` e `.onnx.json`) e do pacote `piper` instalado; o `health` **não** sintetiza nem
chama o ElevenLabs (custo e latência). `voice_provider` é o provedor efetivo de
`TTS_PROVIDER`; `presentation_voice_provider` é o efetivo de `TTS_PRESENTATION_PROVIDER`
(ElevenLabs sem chave/voz → `piper`; Piper sem modelo → `off`).

### Provedor Piper (local, padrão)
Pacote `piper` (projeto `piper-tts`, fork mantido `OHF-Voice/piper1-gpl`), extra `voice` do
`pyproject.toml`, importado só dentro da função (o app funciona sem ele). Modelo
`PIPER_VOICE` em `PIPER_DATA_DIR`, baixado uma vez com `rag-cognus voice-download`. Saída WAV
mono 16 bits (`audio/wav`).

### Provedor ElevenLabs (verificar na doc oficial antes de implementar)
Usado quando `purpose="presentation"` e `TTS_PRESENTATION_PROVIDER=elevenlabs` (ou quando
`TTS_PROVIDER=elevenlabs`). Plano gratuito: uso não comercial e atribuição obrigatória
("Voz gerada com ElevenLabs"). Endpoint REST conhecido, a confirmar em https://elevenlabs.io/docs/api-reference/text-to-speech:
```
POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128
cabeçalhos: xi-api-key: <ELEVENLABS_API_KEY>, Accept: audio/mpeg,
            Content-Type: application/json
corpo: {"text": "...", "model_id": "eleven_multilingual_v2", "language_code": "pt"?,
        "voice_settings": {"stability": 0.65, "similarity_boost": 0.75,
                           "style": 0.0, "use_speaker_boost": true, "speed": 0.95}}
```
Itens a confirmar: nome e faixa de `speed` (0,7–1,2?), se `language_code` é aceito pelo
`eleven_multilingual_v2`, o parâmetro `enable_logging=false` (retenção zero; pode ser só do
plano enterprise) e os códigos de erro de cota (401/429). Chamada via `httpx`, sem SDK
novo; `httpx` já está no extra `api` do `pyproject.toml`, o mesmo que a API usa (nenhuma
dependência nova para o DevOps).

### Variáveis do `.env` (só nomes; o `.env` real não é tocado)
| Variável | Padrão | Uso |
|---|---|---|
| `TTS_PROVIDER` | `piper` | `piper` \| `elevenlabs` \| `off`; outro valor → `ValueError` claro |
| `TTS_PRESENTATION_PROVIDER` | `elevenlabs` | idem; usado com `purpose="presentation"`; ElevenLabs sem chave/voz → Piper |
| `PIPER_VOICE` | `pt_BR-faber-medium` | nome do modelo `.onnx` |
| `PIPER_DATA_DIR` | `.cache/piper` | onde fica o modelo (ignorado pelo git) |
| `PIPER_LENGTH_SCALE` | `1.1` | > 1 = mais lento e calmo (faixa 0,5–2,0) |
| `PIPER_NOISE_SCALE` | padrão da lib (`0.667`) | variação da voz (0–1,5) |
| `PIPER_NOISE_W` | padrão da lib (`0.8`) | variação do ritmo (0–1,5) |
| `ELEVENLABS_API_KEY` | vazio | segredo; `repr=False` como `token` |
| `ELEVENLABS_VOICE_ID` | vazio | voz pt-BR calma escolhida pelo usuário |
| `ELEVENLABS_MODEL` | `eleven_multilingual_v2` | modelo de TTS |
| `ELEVENLABS_STABILITY` | `0.65` | 0–1; alto = voz estável e calma |
| `ELEVENLABS_SIMILARITY` | `0.75` | 0–1; fidelidade à voz escolhida |
| `ELEVENLABS_STYLE` | `0.0` | 0–1; baixo = sem dramatização |
| `ELEVENLABS_SPEED` | `0.95` | ritmo levemente mais lento (faixa a confirmar) |
| `TTS_TIMEOUT` | `20` | segundos por chamada |
| `VOICE_CACHE_DIR` | `.cache/voice` | já ignorado pelo `.gitignore` (`.cache/`) |

## Critérios de aceite
- **AC-1 (rota de fala):** Dado `voice_enabled=true`, quando o front chama
  `POST /v1/voice/speak` com `text` de 1 a 600 caracteres (espaços normalizados, marcação
  removida) e `purpose` em `tip`/`explain`/`presentation`, então a resposta é `200` com os
  bytes do provedor, `media_type` `audio/wav` (Piper) ou `audio/mpeg` (ElevenLabs) e os
  cabeçalhos `X-Voice-Cache` e `X-Voice-Provider`. O provedor é `TTS_PROVIDER` (padrão
  `piper`) para `tip`/`explain` e `TTS_PRESENTATION_PROVIDER` (padrão `elevenlabs`) para
  `presentation`; ElevenLabs sem chave ou voz → Piper. O Piper recebe `PIPER_LENGTH_SCALE`,
  `PIPER_NOISE_SCALE` e `PIPER_NOISE_W`; a chamada ao ElevenLabs usa `httpx` contra
  `/v1/text-to-speech/{voice_id}` com `model_id = ELEVENLABS_MODEL` e `voice_settings` vindos
  de `ELEVENLABS_STABILITY`, `ELEVENLABS_SIMILARITY`, `ELEVENLABS_STYLE` e `ELEVENLABS_SPEED`.
  Todos configuráveis no `.env` e validados em `Settings` (faixas da tabela). Provedor com
  valor desconhecido → `ValueError` em português ao montar o `Settings`. A chave nunca
  aparece em `repr`, log ou resposta.
- **AC-2 (cache em disco):** O áudio é salvo em
  `VOICE_CACHE_DIR/<sha256(provedor|parâmetros do provedor em JSON|texto_normalizado)>.<wav|mp3>`
  (Piper: voz e as três escalas; ElevenLabs: voz, modelo e `voice_settings`; extensão
  conforme o formato)
  (escrita atômica: arquivo temporário + `rename`). Dada uma fala já gerada com a mesma
  configuração, quando ela é pedida de novo, então o provedor **não** é chamado e a resposta
  traz `X-Voice-Cache: hit`; a primeira vez traz `miss`. Mudar voz, modelo ou qualquer ajuste
  de voz gera outra chave. `purpose` não entra na chave (mesma frase, mesmo áudio).
- **AC-3 (falhas):** Provedor `off`, modelo Piper não baixado (`503` "Voz local não
  instalada: rode `rag-cognus voice-download`."), pacote `piper` ausente, erro do Piper, erro HTTP do ElevenLabs (401,
  429, 5xx), timeout (`TTS_TIMEOUT`) ou resposta que não seja áudio → `503` com `detail` em
  português explicando o motivo sem expor a chave (ex.: "Voz indisponível agora: limite do
  ElevenLabs atingido."); nunca `500`, e nenhum arquivo parcial fica no cache.
  `GET /v1/health` passa a informar `voice_available`, `voice_provider` e
  `presentation_voice_provider` sem sintetizar nem chamar o provedor.
- **AC-4 (privacidade):** Com o Piper nada sai do computador, por isso `voice_enabled` vem
  `true` e `voice_autoplay` `false`. O ElevenLabs só recebe texto quando
  `purpose="presentation"` (ou `TTS_PROVIDER=elevenlabs`); só o campo `text` vai ao provedor,
  sem áudio, transcrição, id de sessão, nome de arquivo nem outro dado do usuário (teste
  confere o JSON enviado ao fake). Com `purpose="explain"`, o texto passa por
  `coach.grounded(text, allowed)` com `allowed` = rótulos e valores de `facts`: número fora
  dos fatos → `422` e nada é sintetizado. Com `voice_enabled=false`, `POST /v1/voice/speak`
  responde `403` sem chamar o provedor. No Perfil, a seção "Mascote, privacidade e tutorial"
  ganha o interruptor **"Voz do mascote"** (ligado por padrão) com o aviso: "A voz do dia a
  dia é gerada no seu computador. Na apresentação, o texto falado pode ser enviado ao
  ElevenLabs para virar voz; seu áudio e suas análises não saem do computador." e o crédito
  "Voz gerada com ElevenLabs" (exigido pelo plano gratuito, uso não comercial).
- **AC-4b (nome do perfil):** Antes de enviar ao ElevenLabs, o nome do perfil (se houver)
  é trocado por "você" no texto (palavra inteira, sem diferenciar maiúsculas); o teste
  confere que o nome não aparece no JSON enviado. O Piper recebe o texto original.
- **AC-5 (falar no front):** Com a voz ligada, o balão de dica e o painel "Me explica…" têm
  um botão **"Ouvir"** (`aria-label` "Ouvir o mascote"; vira "Parar" enquanto fala). O
  Perfil ganha **"Falar automaticamente"** (padrão desligado, só habilitado com a voz
  ligada), que fala cada dica ou explicação nova uma vez. A legenda (o texto) fica sempre
  visível enquanto fala. Há um único tocador (`src/lib/voice/player.ts`): uma fala nova,
  mudar de rota (`usePathname`) ou fechar o painel interrompe a fala em curso. A prop
  `speaking` do mascote fica `true` só enquanto há áudio tocando (não mais durante o
  carregamento da explicação, que usa o humor "pensativo").
- **AC-6 (lip sync):** O tocador usa um `AudioContext` próprio (padrão de
  `src/lib/audience/engine.ts`) com `AnalyserNode`; a cada quadro calcula o RMS do sinal e a
  função pura `mouthOpen(rms, previous, { reduced })` em `src/lib/voice/lipsync.ts` devolve a
  abertura da boca em `[1, 1.28]` (mesma escala da animação atual), com piso de ruído
  (silêncio → 1), ataque rápido e soltura suave. `Mascot` recebe a abertura (ex.: prop
  `mouthLevel?: () => number`) e a usa no lugar da senoide quando há áudio; sem áudio, segue a
  senoide atual. Com `prefers-reduced-motion: reduce`, a boca só alterna aberta/fechada (acima
  ou abaixo do limiar), sem interpolação. `npm run test:voice` cobre silêncio, pico, limites,
  suavização e modo reduzido.
- **AC-7 (fallback):** Se a rota responder `403`, `503` ou falhar a rede, o tocador usa
  `window.speechSynthesis` com uma voz cujo `lang` começa com `pt-BR` (ritmo `rate` 0,95), e a
  boca usa a senoide atual durante `onstart`→`onend`; sem voz pt-BR ou sem
  `speechSynthesis`, mostra só a legenda. Nenhum desses casos mostra erro em tela nem quebra o
  dock; um aviso discreto "Voz do navegador" ou "Só legenda" aparece no painel.
- **AC-8 (testes sem rede):** `tests/test_voice.py` usa um Piper falso (adaptador
  `_piper_synthesize` trocado por `monkeypatch`) e um ElevenLabs falso (transporte
  `httpx.MockTransport`) para cobrir AC-1…AC-4b: corpo e cabeçalhos enviados,
  hit/miss do cache em `tmp_path`, cada falha → `503`, guarda de números → `422`, sem chave →
  `off`. `tests/test_api.py` cobre a rota, `403` com a voz desligada, `health` e os campos
  novos de `/v1/mascot/settings` usando `FakeServices(tmp_path)`. Nenhum teste chama o
  ElevenLabs; o fake falha o teste se receber uma URL fora do esperado.
- **AC-9 (verificação):** `python hermes/harness/check.py` termina em `HARNESS OK`; no
  `frontend_UI`, `npm run typecheck && npm run lint && npm run build`, `npm run test:voice` e
  os testes existentes (`test:mascot`, `test:articulation`, `test:session`, `test:audience`,
  `test:home`) passam.

## Fora de escopo
- Modo apresentação narrado e pré-geração do roteiro (spec 028).
- Conversa por voz (push-to-talk) e co-apresentador (ver fim da spec 028).
- Outros provedores (OpenAI etc.) — o `TTS_PROVIDER` deixa a porta aberta.
- Streaming de áudio (`/stream`) e limpeza/limite de tamanho do cache.
- Falar respostas do RAG em Aprender (o texto com citações não foi desenhado para voz).

## Riscos
- **Custo/cota do ElevenLabs:** só a apresentação usa o ElevenLabs, com cache e
  pré-geração (028); o dia a dia é Piper local, sem custo.
- **Modelo Piper ausente:** sem `rag-cognus voice-download` a voz local responde `503` e o
  front usa a voz do navegador.
- **Autoplay bloqueado:** navegadores só tocam áudio após um gesto; o `AudioContext` é criado
  ou retomado no primeiro clique ("Ouvir" ou o interruptor). Antes disso, "Falar
  automaticamente" mostra só a legenda.
- **Nome da pessoa no texto:** resolvido pelo AC-4b (troca por "você").
- **Uso do texto pelo provedor:** sem retenção zero confirmada, o ElevenLabs pode guardar o
  texto; o aviso do AC-4 deixa isso claro.

## Decisões (usuário, 2026-11-23)
1. Modelo híbrido: Piper local é o padrão (`TTS_PROVIDER=piper`); ElevenLabs opcional para
   a apresentação (`TTS_PRESENTATION_PROVIDER=elevenlabs`), com queda para o Piper.
2. Voz local padrão `pt_BR-faber-medium`, `PIPER_LENGTH_SCALE=1.1` (um pouco mais calma).
3. Nome do perfil vira "você" antes de qualquer envio ao ElevenLabs (AC-4b).
4. Ajustes iniciais do ElevenLabs mantidos (`stability 0.65`, `similarity 0.75`,
   `style 0.0`, `speed 0.95`), a ajustar ouvindo frases de teste; `ELEVENLABS_VOICE_ID`
   escolhido pelo usuário.

## Impacto
- Nenhum impacto em métricas do RAG, juízes ou MLflow: a voz só lê textos já produzidos e
  guardados pelo coach (spec 013). A guarda de números é reaproveitada, não alterada.

## Plano (preenchido depois da aprovação)
| Passo | Arquivo | Subagente | Verificação |
|---|---|---|---|
| 1 | extra `voice = ["piper-tts"]`, `uv.lock`, `.env.example`, `cli.py voice-download`, modelo em `.cache/piper` | engenheiro-devops | instalação + `--changed` |
| 2 | `config.py` (`TTS_*`/`PIPER_*`/`ELEVENLABS_*`), `tests/test_voice.py`, `voice.py` (provedores, cache, guarda) | engenheiro-ia | AC-1…AC-4b, AC-8 |
| 3 | `api/app.py`, `api/schemas.py`, `tests/test_api.py` (rota, health, settings) | engenheiro-ia | AC-3, AC-4, AC-8 |
| 4 | `player.ts`, `lipsync.ts` + teste, `mascot.tsx`, `mascot-dock.tsx`, `profile-view.tsx`, `client.ts` | engenheiro-frontend | AC-5…AC-7 |
| 5 | — | líder técnico | AC-9 |
