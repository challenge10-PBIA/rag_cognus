# Plano — Front web do Cognus (base para o app mobile)

> Referência para o repositório do front e para as specs de backend deste repositório.
> Telas de origem: projeto Stitch (mobile). Estado: planejamento, nada implementado.

## 1. Visão

O web de testes deve se comportar como o futuro app: um **treinador de fala**. O usuário
escolhe um modo, grava, vê métricas ao vivo, recebe um diagnóstico e acompanha a evolução.
RAG e agentes ficam por trás: as recomendações citam evidências da Gold.

```
rag_cognus (este repo) = backend            repo do front
├─ rag_cognus/ (RAG, agentes, voz)          ├─ apps/web       (Next.js)  ← agora
├─ rag_cognus/api/  FastAPI  ── OpenAPI ──► ├─ apps/mobile    (Expo)     ← depois
│    REST + SSE + WebSocket                 ├─ packages/api-client (gerado do OpenAPI)
├─ SQLite: sessões, progresso, hábitos      └─ packages/tokens     (design do Stitch)
├─ MLflow local: traces e avaliação
└─ chat_app.py (Streamlit) = laboratório interno, continua existindo
```

- O contrato é o OpenAPI do FastAPI; o front gera o cliente TypeScript (`openapi-typescript`).
- Dados do produto (sessões, notas, streak) ficam no **SQLite**; o **MLflow** continua só com
  traces e avaliação de qualidade.
- Tudo local: áudio e transcrição não saem da máquina.

## 2. Telas recebidas

| # | Tela | Rota web | Função |
|---|---|---|---|
| 1 | Início Prática | `/` | Saudação, streak, meta diária, pontos de clareza, modos, desafios, feedback recente, prática espontânea |
| 2 | Evolução Métricas | `/metricas` | Índice Cognus, evolução diária, conquistas, direcionamentos |
| 3 | Sessão Ativa de Fala | `/sessao/ao-vivo?modo=…` | Cronômetro, onda sonora, transcrição ao vivo, ritmo/pausas/dicção, dica em tempo real, controles |
| 4 | Detalhe do Diagnóstico | `/sessoes/[id]` | Índice geral, 4 pilares, fluxo de entonação, recomendações, ouvir com transcrição, adicionar aos hábitos |

**Telas que faltam desenhar no Stitch:** Explorar modos (`/modos`), Perfil (`/perfil`),
Meus hábitos (`/habitos`), Pergunte ao Cognus — chat RAG com evidências (`/cognus`),
estados vazios (primeiro acesso, sem sessões) e de erro (microfone negado, Ollama fora do ar).

## 3. Identidade visual (tokens aproximados — confirmar no export do Stitch)

| Token | Valor |
|---|---|
| `font-display` | Serif display (estilo Playfair Display) — títulos e números grandes (84, 92, 01:44) |
| `font-sans` | Sans geométrica (estilo Manrope / Plus Jakarta Sans); rótulos em caixa alta com tracking |
| `primary` | `#0F4C5C` (verde-petróleo: Gravar, CTAs, barras de progresso) |
| `surface-mint` / `surface-lavender` / `surface-sky` | `#BDEBD6` / `#DEDDF8` / `#CDEBF7` |
| `background` | `#F7F5FA` |
| `card` | raio ~24 px, borda 1 px, **sombra deslocada sólida** (offset 3–4 px, sem blur) |
| `pill` | chips arredondados: "5 DIAS", "3 MIN", "IDEAL", "+14% mês" |

Prioridade: exportar o código do Stitch (HTML + Tailwind) para extrair os valores exatos.

## 4. Adaptação mobile → web

| Mobile | Web ≥ 1024 px |
|---|---|
| Barra inferior (Início, Gravar, Métricas, Perfil) | Barra lateral fixa; **Gravar** como botão primário no topo dela |
| Uma coluna | Grid de 12 colunas, conteúdo + coluna lateral |
| Telas lista → detalhe | Mestre-detalhe |
| Bottom sheet | Drawer lateral / diálogo |

Abaixo de 768 px o web usa o layout mobile do Stitch (mesma experiência do app).

**Início:** linha de 3 cards (pontos de clareza · modos · feedback recente); abaixo, desafios
(8 col) + prática espontânea fixa à direita (4 col).
**Métricas:** índice (4 col) + gráfico (8 col); conquistas em 3 colunas; direcionamentos em 2.
**Sessão ativa (modo foco, barra lateral recolhida):** centro com cronômetro, onda e transcrição;
coluna direita com ritmo/pausas/dicção empilhados + dica; barra de controles fixa embaixo
(Reiniciar · Pausar · Marcar · Concluir e analisar).
**Diagnóstico:** esquerda (8 col) índice, 4 pilares em linha, fluxo de entonação e player com
transcrição; direita (4 col, fixa) recomendações com fontes + "Adicionar aos hábitos".

## 5. O que cada número significa (definições para o backend)

Todos os pilares viram nota 0–100; **Índice geral = média dos 4 pilares**. Faixas configuráveis.

| Pilar (tela) | Medida | Como | Nota |
|---|---|---|---|
| Ritmo & Cadência | palavras por minuto | timestamps por palavra do faster-whisper | 100 dentro de 120–160 ppm, cai linearmente fora |
| Pausas Conscientes | nº de pausas de 0,4–2 s; silêncios > 3 s | intervalos entre palavras | equilíbrio por minuto; penaliza silêncio > 3 s ("constrangedor") |
| Vícios Vocais | % da fala sem vícios + contagem por termo | lista PT: é/éé/ééé, hã, hum, tipo, né, aí, assim, basicamente… | 100 − taxa de vícios ponderada |
| Clareza (sugestão de nome: "Clareza da mensagem", não "mental") | legibilidade + nota de clareza do juiz | `text_metrics` + juiz do agente de comunicação | média |
| Dicção (só ao vivo/indicador) | inteligibilidade estimada | probabilidade média das palavras no Whisper | % direto |
| Fluxo de entonação ("ressonância" na tela) | contorno de F0 e finais ascendentes | `praat-parselmouth` (novo, extra `audio`) | estável/instável + nº de finais ascendentes |

**Riscos a validar antes de prometer na tela:**
- O Whisper tende a **apagar vícios** ("éé", "hum"). Mitigação: `initial_prompt` com vícios
  ("Ééé, hum, tipo, né…") para transcrição literal; validar com gravações reais.
- **Ansiedade não é medida.** "Ansiedade reduzida −28%" e "Nível Calmo" precisam virar
  autoavaliação (antes/depois da sessão) ou "calma estimada" (variação de ritmo + pausas
  preenchidas), com rótulo honesto. Mesma regra do RAG: não diagnosticar.
- Pontos, conquistas e "clareza 92%" devem vir dessas fórmulas, nunca de texto do LLM.

## 6. Backend necessário (specs deste repositório)

| Spec | Entrega | Destrava telas |
|---|---|---|
| **002 — API** | FastAPI: `/v1/meta`, `/v1/health`, `/v1/ask`, `/v1/agents/*` (SSE com etapas), `/v1/speech/transcribe`, `/v1/feedback`; CORS `localhost:3000`; OpenAPI | base de todas |
| **003 — Sessões e análise de fala** | `POST /v1/sessions` (áudio + modo) → pilares, índice, transcrição com timestamps e vícios marcados, entonação, recomendações do agente de comunicação; SQLite; áudio salvo local | Diagnóstico |
| **004 — Sessão ao vivo** | `WS /v1/sessions/live`: recebe PCM 16 kHz em blocos de ~1 s, devolve transcrição parcial, ppm, pausas, dicção e dica por regras a cada ~3–5 s | Sessão ativa |
| **005 — Progresso** | `GET /v1/progress?period=week\|month\|quarter`: índice, evolução diária, streak, meta, conquistas | Início, Métricas |
| **006 — Recomendações e hábitos** | Desafios do dia e direcionamentos: pontos fracos das sessões → agente de evidências (exercícios citados da Gold) → agente de comunicação; `/v1/habits` | Início, Métricas, Diagnóstico |

**Sessão ao vivo, em duas etapas:** v1 grava e analisa no fim (onda sonora e contagem de
pausas calculadas no navegador com Web Audio API, sem servidor); v2 liga o WebSocket com
transcrição parcial. A dica em tempo real usa **regras** (rápidas e previsíveis); o LLM entra
só no diagnóstico final — o Qwen local é lento demais para o ao vivo.

### Contrato de exemplo — resultado da sessão (para mock no front)

```json
{
  "session_id": "s_01",
  "mode": "pitch",
  "scenario": "Apresentação para stakeholders",
  "duration_seconds": 222,
  "index": 92,
  "headline": "Excelente ritmo e modulação de voz",
  "summary": "Sua fala transmitiu segurança e clareza estruturada do início ao fim.",
  "pillars": {
    "pace": {"value": 138, "unit": "ppm", "score": 90, "label": "ideal"},
    "pauses": {"value": 6, "unit": "pausas", "score": 88, "label": "otimo", "long_silences": 0},
    "fillers": {"value": 96, "unit": "% livre", "score": 96, "label": "limpo",
                "counts": {"tipo": 1, "éé": 0}},
    "clarity": {"value": "alto", "score": 87, "label": "preciso"}
  },
  "diction": 96,
  "intonation": {"contour": [0.42, 0.55, 0.61], "stability": "estavel", "rising_endings": 2},
  "transcript": [{"start": 0.0, "end": 0.32, "word": "Em", "filler": false}],
  "recommendations": [
    {"kind": "strength", "text": "Você sustentou a voz com clareza nos pontos técnicos."},
    {"kind": "next_step", "text": "Faça pausas de 1 segundo ao mudar de tópico.",
     "sources": [{"chunk_id": "c1", "title": "…", "url": "…"}]}
  ],
  "trace_id": "tr-…"
}
```

### Mensagens do WebSocket ao vivo

- Cliente → servidor: frames binários PCM16 mono 16 kHz (~1 s); JSON `{"type": "mark"}`,
  `{"type": "pause"}`, `{"type": "resume"}`, `{"type": "stop"}`.
- Servidor → cliente: `{"type": "partial", "elapsed": 104, "text": "Em resumo, os resultado…",
  "pace_ppm": 135, "pauses": 4, "diction": 96, "tip": "Faça uma pausa de 1 segundo…"}` e, no
  fim, `{"type": "final", "session_id": "s_01"}`.
- Captura no navegador com **AudioWorklet** (PCM direto, sem ffmpeg no servidor); o mesmo
  protocolo serve ao app mobile depois.

## 7. Front (novo repositório)

- **Stack:** Next.js (App Router) + TypeScript + Tailwind + shadcn/ui + TanStack Query +
  Recharts; Vitest + Playwright. Monorepo pnpm + Turborepo (`apps/web`, `packages/tokens`,
  `packages/api-client`) para o Expo reaproveitar tokens e cliente.
- **Componentes base:** `AppShell` (barra lateral ↔ barra inferior), `Card` (variações
  mint/lavender/sky + sombra deslocada), `Pill`, `StatCard`, `PillarCard` (barra de progresso),
  `ScoreHero` (índice + ilustração), `Waveform` (ao vivo e estático), `RecordControls`,
  `LiveTranscript`, `TipBanner`, `ChallengeCard`, `AchievementRow`, `GuidanceCard`,
  `SegmentedPeriod`, `DailyBarChart`, `TranscriptPlayer` (áudio + palavras sincronizadas com
  vícios destacados), `SourceList` (citações da Gold).
- **Estados obrigatórios por tela:** carregando, vazio (primeiro uso), erro (API/Ollama fora,
  microfone negado), sucesso.

## 8. Fases

| Fase | Onde | Entrega | Depende de |
|---|---|---|---|
| 0 | backend | spec 002 (API + OpenAPI) | — |
| 1 | front | monorepo, tokens, `AppShell` responsivo, componentes base, Storybook opcional | export do Stitch |
| 2 | front | as 4 telas com dados mockados do OpenAPI | contrato da 002/003 |
| 3 | backend + front | Gravar → Diagnóstico real (sessão analisada no fim) | 003 |
| 4 | backend + front | Início e Métricas reais | 005 |
| 5 | backend + front | Recomendações, hábitos, Pergunte ao Cognus | 006 |
| 6 | backend + front | Sessão ao vivo com WebSocket | 004 |
| 7 | front | acessibilidade, e2e, polimento | — |

As fases 0 e 1 podem correr em paralelo.

## 9. Decisões pendentes (com recomendação)

1. **Ansiedade:** autoavaliação antes/depois (recomendado) ou "calma estimada".
2. **Ao vivo na primeira entrega:** não — v1 analisa no fim; WebSocket na fase 6 (recomendado).
3. **Stack:** Next.js + monorepo pronto para Expo (recomendado) vs. Expo + React Native Web.
4. **Usuário:** perfil local único, sem login, até o mobile (recomendado).
5. **Novas dependências do backend:** `fastapi`, `uvicorn`, `praat-parselmouth` (extra
   `audio`) — exigem atualizar `pyproject.toml` e `uv.lock`.
