# 035 — Cenário Pitch de venda (1 minuto)

- **Status:** implementado (2026-11-27)
- **Módulos:** novo `src/rag_cognus/scenarios/pitch.py`; `src/rag_cognus/api/app.py`
  (`MODES`); `src/rag_cognus/api/schemas.py` (`PitchResult`)
- **Testes:** `tests/test_scenarios.py`, `tests/test_api.py`; AC-7 com o LLM real em `data/evaluation/pitch_cases.jsonl` (fora do pytest)
- **Relacionadas:** 034 (camada de cenários, pré-requisito), 033 (LLM local)

## Problema
No `daily_pitch` a pessoa recebe o mesmo retorno de qualquer outro modo: ritmo, vícios e
clareza. Quem treina um pitch de venda quer saber se convenceu: se o comprador compraria,
por quê, e o que faltou.

## Comportamento esperado
Novo modo **Pitch de venda** (`pitch_venda`, 1 min). No briefing a pessoa escreve o produto
ou pede um sorteio, e escolhe um comprador (ex.: diretor financeiro cético, consumidor com
pressa, investidor). Depois da gravação, além da análise de fala de sempre, recebe:
- **Veredito do comprador simulado:** compraria / talvez / não compraria, com o motivo em 1–2
  frases, sempre rotulado como simulação.
- **Checklist de persuasão:** gancho nos primeiros 10 s, problema, proposta de valor, prova,
  pedido claro (CTA). Cada item marcado presente/ausente com o trecho da fala que o justifica.
- **Objeção principal** que esse comprador levantaria, e o convite para uma rodada de 30 s
  "responder à objeção" (nova sessão no mesmo modo, com o briefing herdado).

## Critérios de aceite
- **AC-1:** `GET /v1/meta` lista `pitch_venda` com briefing: `produto` (texto, ≤ 200, opcional)
  e `comprador` (choice, obrigatório). `GET /v1/scenarios/pitch_venda/suggestions` devolve 5 produtos
  sorteados de uma lista fixa em português (sem LLM).
- **AC-2:** `mode_result` tem `kind="pitch_venda"`, `verdict` ∈ `compraria|talvez|nao_compraria`,
  `reason`, `buyer`, `product`, `checklist` (5 itens fixos `gancho|problema|valor|prova|cta`,
  `present: bool`, `evidence` ≤ 160 caracteres ou `null`), `present_count`, `objection` e
  `simulated: true`.
- **AC-3:** Cada `evidence` com `present=true` é um trecho que existe na transcrição
  (normalizado); senão o item vira `present=false`. O número de itens presentes é contado no
  Python, nunca vem do LLM.
- **AC-4:** Regra de consistência: com 0–1 item presente, `verdict` não pode ser `compraria`
  (rebaixado para `talvez`). Fica registrado no trace quando o rebaixamento acontecer.
- **AC-5:** Transcrição com menos de 15 palavras → `mode_result: null` e
  `mode_result_error: "Fala curta demais para avaliar o pitch."`, sem chamar o LLM.
- **AC-6:** Uma rodada de objeção (`briefing.objecao_de=<session_id>`) avalia só se a resposta
  trata a objeção da sessão de origem: `mode_result.kind="pitch_objecao"`, `objection`,
  `addressed: bool`, `reason`. Sessão de origem inexistente ou sem objeção → 422.
- **AC-7 (avaliação):** conjunto fixo de ≥ 10 transcrições rotuladas (pitch forte, médio e
  fraco) em `data/` com o juiz rodando localmente: o veredito bate com o rótulo em ≥ 70% e,
  com o mesmo áudio e a mesma seed, repete em ≥ 90%. Resultado registrado no MLflow local.

## Riscos
- O acervo não cobre vendas e persuasão (`NICHOS` em `config.py`). Até haver conteúdo, o
  retorno do pitch não cita fontes do acervo e diz isso; nada de inventar técnica como se
  viesse da base.
- Latência: cada chamada do LLM local leva 15–60 s; por isso o avaliador roda em segundo
  plano (spec 034) e o app mostra o cartão do pitch quando ficar pronto.

## Fora de escopo
- Telas do `mobile_cognus` (spec própria).
- Personas criadas pelo usuário e pitch com mais de 1 minuto.

## Resultado do AC-7 (2026-11-27, `eriktonon/deepseek-v4.1-flash-1017:latest`, seed 42)
| Rodada | Concordância | Repetibilidade | Latência p50 / máx |
|---|---|---|---|
| 1 (rubrica inicial) | 58% (7/12) ✗ | 100% | 27,8 s / 37,5 s |
| 2 (checklist antes do veredito + critérios explícitos) | **75% (9/12) ✓** | **100% ✓** | 25,5 s / 35,4 s |

Erros restantes: 3 de 4 pitches fracos saem `talvez` em vez de `nao_compraria` (o modelo evita
o veredito negativo). Runs no MLflow local, experimento `rag-cognus-pitch`.
