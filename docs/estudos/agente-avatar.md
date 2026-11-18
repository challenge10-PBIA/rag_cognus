# Agente de comunicação via avatar

Guia de estudo do papel `[avatar]` (skill `hermes/skills/rag-avatar-agent/SKILL.md`).

## 1. Situação
O agente já existe fora deste repositório e vai ser integrado depois. Este repo já tem as
peças em que ele vai encaixar; a skill descreve o contrato para a integração não começar do
zero e para o modelo local não inventar código.

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
