# Agente de comunicação via avatar

Guia de estudo do papel `[avatar]` (skill `hermes/skills/rag-avatar-agent/SKILL.md`).

## 1. Situação
O agente entrou no repo como o **mascote coach** (spec `specs/013-mascote-coach-dicas.md`,
código em `src/rag_cognus/coach.py`, papel em `hermes/agents/communication-agent.md`) e conduz
o onboarding (spec 014). As seções 3 e 4 abaixo eram a proposta inicial; o que foi
implementado está na seção 5.

## 2. Peças que já existem
- **Mascote** (`src/rag_cognus/mascot.py`, spec 008): paleta fechada (pele, cabelo/gorro,
  cores). `options()` alimenta `GET /v1/profile/mascot/options`; `normalize()` troca qualquer
  valor fora da paleta pelo padrão. Por quê fechada: o front desenha o mascote e precisa de
  ids conhecidos; o LLM nunca escolhe cor.
- **Agente de comunicação** (`src/rag_cognus/agents/communication.py`): adapta um texto ao
  público (`AudienceProfile`) sem acrescentar fatos; métricas objetivas (palavras, tempo de
  fala) são calculadas em Python, não pelo modelo.
- **Feedback da sessão** (`src/rag_cognus/feedback.py`): recomendações e exercícios.
- **API** (`src/rag_cognus/api/app.py`): `POST /v1/agents/communication` devolve o texto
  adaptado e o `trace_id`; `POST /v1/feedback` registra o 👍/👎 da pessoa nesse trace.

## 3. Contrato proposto
Entrada: `text`, `mascot` (normalizado), `profile`, `source_claims`.
Saída: `utterances` (falas curtas com `emotion` de um conjunto fechado e `pause_ms`),
`mascot` (inalterado), `citations` (só as recebidas) e `trace_id`.

Por que assim:
- **Falas curtas e pausas**: o avatar fala em voz; frases longas ficam artificiais.
- **Emoções de um conjunto fechado**: o front precisa de animações conhecidas, como a paleta.
- **Não acrescentar fatos**: o avatar é a "boca" do sistema; a verdade vem do agente de
  evidências (RAG com citações). Um teste deve provar que nenhuma fala traz fato novo.
- **`trace_id`**: liga o que a pessoa ouviu ao feedback dela no MLflow, que o agente de
  observabilidade lê depois.

## 4. Quando o código chegar
1. Spec `specs/013-agente-avatar.md` (número sugerido) com AC testáveis.
2. Testes em `tests/test_avatar.py`, com LLM falso (veja os fakes de `tests/test_agents.py`).
3. Código em `src/rag_cognus/agents/avatar.py`; rota opcional `POST /v1/agents/avatar`.
4. `python hermes/harness/check.py` até `HARNESS OK`.

No Hermes: `goal: "[avatar] integrar o agente de avatar"`, com "carregue a skill
rag-avatar-agent" no `context`. No Claude Code: `engenheiro-ia`.

## 5. O que foi implementado (spec 013)
Diferenças em relação à proposta, e por quê:
- **Texto, não falas com `pause_ms`**: sem voz (TTS) nesta entrega; o balão mostra até 3
  frases. `utterances` volta quando houver voz.
- **`mood` em vez de `emotion`**: o mesmo conjunto fechado de expressões que o front já anima
  (`feliz`, `neutro`, `pensativo`, spec 008).
- **Fatos em vez de `source_claims`**: o mascote explica métricas do próprio usuário; os
  números vêm de `coach.facts()` (SQLite), e a guarda `grounded()` troca por regras qualquer
  texto com número que não esteja nos fatos. Dicas por tela são só regras, sem LLM.
- **`trace_id`** continua: cada explicação é um trace `flow=mascot` (contrato da spec 011),
  com a tag `mascot_source` que o agente de observabilidade acompanha.
