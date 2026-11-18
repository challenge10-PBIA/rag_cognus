# 013 — Mascote coach: dicas por tela e explicações

- **Status:** aprovada (decisões do usuário em 2026-11-18: só dicas e explicações, sem chat livre)
- **Módulos (backend):** novo `src/rag_cognus/coach.py`, `src/rag_cognus/api/app.py`,
  `src/rag_cognus/api/schemas.py`, `src/rag_cognus/api/store.py`
- **Módulos (front, `frontend_UI`):** novo `src/components/mascot/mascot-dock.tsx`,
  `src/components/app-shell.tsx`, `src/lib/api/{client.ts,queries.ts,schema.d.ts}`,
  `src/components/profile/profile-view.tsx`
- **Testes:** `tests/test_coach.py` (novo), `tests/test_api.py`; front: typecheck/lint/build
- **Prompt do agente:** `hermes/agents/communication-agent.md` (papel e regras de tom)
- **Depende de:** spec 008 (mascote do perfil)

## Problema
O mascote só aparece no Perfil, no cabeçalho e no carrossel do diagnóstico. O usuário não tem
quem explique o que significam "Índice Cognus", "ppm", "pausas conscientes" ou por que um
pilar caiu, e as telas não dão nenhuma orientação contextual.

## Comportamento esperado
- Um **mascote discreto** fica no canto da tela em todas as páginas (exceto gravação ao vivo
  e diagnóstico, que já têm o seu). Ele mostra **uma dica curta por tela**, gerada por
  **regras** a partir dos dados da API (sem LLM, instantânea).
- Ao abrir o mascote, o usuário escolhe **"Me explica…"** entre tópicos fechados (ex.: o que
  é o Índice, meu ponto mais fraco). A explicação é escrita pelo **LLM** a partir de
  **fatos calculados pelo backend**; o LLM nunca inventa número. Sem Ollama, a explicação
  sai por regras (glossário + fatos).
- Sem chat livre nesta entrega.
- O usuário pode **silenciar as dicas** no Perfil (o mascote continua acessível ao clique).

## Contrato
- `GET /v1/mascot/tips?route=<rota>&session_id=<id?>` →
  `{tips: [{id, text, mood, topic|null}], enabled: bool}`.
  `mood ∈ {feliz, neutro, pensativo}` (mesmos do front, spec 008 AC-11).
- `GET /v1/mascot/topics?route=<rota>&session_id=<id?>&ask_id=<id?>` →
  `[{id, label}]` — tópicos que fazem sentido naquela tela.
- `POST /v1/mascot/explain` `{topic, route, session_id?, ask_id?}` →
  `{topic, text, mood, facts: [{label, value}], source: "llm"|"regras", trace_id|null}`.
- `GET/PUT /v1/mascot/settings` → `{tips_enabled: bool}` (padrão `true`).

Tópicos (fonte única em `coach.TOPICS`): `index`, `pace`, `pauses`, `fillers`, `clarity`,
`diction`, `streak`, `level`, `daily_goal`, `weakest_pillar`, `session_summary`,
`ask_evaluation`.

## Critérios de aceite — backend (engenheiro-ia)
- **AC-1:** `coach.GLOSSARY` define, para cada tópico de conceito (`index`, `pace`, `pauses`,
  `fillers`, `clarity`, `diction`, `streak`, `level`, `daily_goal`), `label` e uma
  explicação em português de até 2 frases, sem números de usuário. As faixas citadas
  (120–160 ppm; pausas de 0,4–2 s) vêm das constantes de `speech_analysis`, não de literais
  duplicados.
- **AC-2:** `coach.tips(route, data) -> list[dict]` é pura (sem rede/disco) e devolve 0–2
  dicas, a de maior prioridade primeiro, cada uma com `id` estável (mesmo dado → mesmo id):
  - `/` sem sessões → convite à primeira prática (`feliz`); com sessões e meta do dia
    batida → parabéns (`feliz`); senão, streak ≥ 2 → "não quebre a sequência" (`neutro`);
  - `/metricas` com pilares → pilar mais fraco do período, com o tópico `weakest_pillar`
    (`pensativo` se nota < 60, senão `neutro`); sem dados → explica que as métricas
    aparecem após a 1ª sessão;
  - `/cognus` → como perguntar e que as respostas citam fontes (`neutro`);
  - `/perfil` → personalizar o mascote (`feliz`);
  - rota desconhecida → lista vazia.
- **AC-3:** `coach.facts(topic, data) -> list[{label, value}]` monta os fatos só com números
  vindos de `data` (home/progresso/sessão/avaliação). Tópico que depende de dado ausente
  (ex.: `session_summary` sem `session_id`, `weakest_pillar` sem sessões) → `ValueError`
  com mensagem em português; a API responde 422 com essa mensagem.
- **AC-4:** `coach.topics(route, data)` lista os tópicos da tela: conceitos sempre; mais
  `weakest_pillar` se houver sessões, `session_summary` se houver `session_id` válido e
  `ask_evaluation` se houver `ask_id` com avaliação `done`.
- **AC-5:** `MascotCoach.explain(topic, facts)` chama o LLM (`make_ollama`, schema
  `{text, mood}`) com o glossário do tópico e os fatos; o prompt segue o papel de
  `communication-agent.md` (curto, encorajador, traduz jargão, não inventa dado).
- **AC-6:** Guarda de fidelidade: todo número no `text` do LLM precisa aparecer nos fatos ou
  no glossário do tópico (comparação normalizada: `92`, `92%`, `92,0` casam); se algum não
  aparecer, ou o texto passar de 600 caracteres, ou vier vazio, a resposta cai para a
  explicação por regras com `source="regras"`.
- **AC-7:** Falha do LLM (exceção/timeout) → explicação por regras (`glossário + fatos`),
  `source="regras"`, HTTP 200. Nunca 500 por causa do Ollama.
- **AC-8:** Cada explicação gera trace MLflow com span raiz `AGENT` e tag `agent=mascot`,
  `topic=<id>`; `trace_id` vem na resposta (pode ser `null` se o MLflow estiver fora).
- **AC-9:** `tips` e `topics` não chamam LLM nem Gold e respondem sem Ollama.
- **AC-10:** `tips_enabled=false` → `GET /v1/mascot/tips` devolve `tips: []` e
  `enabled: false`. Persistido no SQLite (tabela `app_state` chave/valor, criada de forma
  idempotente); sobrevive a reinício.
- **AC-11:** Tópico desconhecido no `POST /explain` → 422 (validação do schema).

## Critérios de aceite — front
- **AC-12:** `<MascotDock>` montado no `AppShell`: botão fixo no canto inferior direito
  (acima da barra inferior no mobile), mascote `framing="head"`, ≥ 44 × 44 px,
  `aria-label="Abrir o mascote"`. Oculto em `/gravar*` e `/sessoes/*` (um mascote por tela,
  spec 008 AC-21) e enquanto o onboarding (spec 014) estiver aberto.
- **AC-13:** Ao entrar numa rota, se houver dica ainda não dispensada nesta aba, um balão
  aparece ao lado do mascote com o texto e o `mood`; "Entendi" dispensa (lembrado por
  `sessionStorage`, em `try/catch`). No máximo uma dica por rota por sessão do navegador.
- **AC-14:** Clique no mascote abre um painel (`role="dialog"`, foco preso, Esc fecha e
  devolve o foco) com os tópicos de `GET /v1/mascot/topics` como botões "Me explica…".
  Ao escolher, mostra carregando (mascote `pensativo`, `speaking`), depois o `text`, os
  `facts` em lista e, se `source="regras"`, a nota "Resposta rápida (modelo local
  indisponível)". Erro da API em `ErrorBox`.
- **AC-15:** Perfil ganha o interruptor "Dicas do mascote" (`role="switch"`) ligado a
  `GET/PUT /v1/mascot/settings`.
- **AC-16:** `prefers-reduced-motion`: balão sem animação de entrada. Balão com
  `aria-live="polite"`.

- **AC-17 (contexto da tela):** Um estado compartilhado do front (`coach-context.ts`, sem
  dependência nova) leva o contexto da tela ao mascote. Em `/cognus`, quando a avaliação da
  resposta fica `done`, o painel de avaliação publica o `ask_id`; o mascote passa a enviá-lo
  em `topics`/`explain`, e "Como esta resposta foi avaliada?" aparece entre os tópicos. Ao
  sair da tela ou trocar de pergunta, o `ask_id` anterior é limpo.
- **AC-18:** O resultado da avaliação ganha o botão "Me explica estas notas", que abre o
  painel do mascote já pedindo o tópico `ask_evaluation`; fechar o painel devolve o foco ao
  mascote.

## Fora de escopo
- Chat livre com o mascote; voz (TTS); dicas geradas por LLM; dicas durante a gravação.
- Relatórios diário/semanal/mensal (spec futura).

## Riscos
- Qwen 9B local leva alguns segundos por explicação: o painel mostra carregando e o mascote
  "pensando"; respostas curtas (`num_predict` baixo).
- A guarda de números (AC-6) pode rejeitar textos bons que escrevem número por extenso; isso
  só deixa a resposta mais conservadora (cai para regras), nunca inventa.

## Plano
| Passo | Arquivo | Subagente | Verificação |
|---|---|---|---|
| 1 | `tests/test_coach.py` → `coach.py` | engenheiro-ia | AC-1…AC-7 |
| 2 | `tests/test_api.py` → `api/*` | engenheiro-ia | AC-3, AC-8…AC-11 |
| 3 | `mascot-dock.tsx`, `app-shell.tsx`, `profile-view.tsx`, `lib/api/*` | front | AC-12…AC-16 |
| 3b | `coach-context.ts`, `mascot-dock.tsx`, `cognus/ask-answer.tsx` | front | AC-17, AC-18 |
| 4 | ambos | líder | `check.py` + `npm run typecheck && lint && build` |
