# 034 — Camada de cenários por modo de treino

- **Status:** implementado (2026-11-27)
- **Módulos:** `src/rag_cognus/api/app.py` (`MODES`, `create_session`, `analyze_session`),
  `src/rag_cognus/api/schemas.py`, `src/rag_cognus/api/store.py`, novo
  `src/rag_cognus/scenarios/` (`__init__.py`, `base.py`)
- **Testes:** `tests/test_api.py`, novo `tests/test_scenarios.py`
- **Relacionadas:** 032 (contrato mobile), 035 (Pitch, primeiro cenário), 033 (LLM local)

## Problema
Os cinco modos (`daily_pitch`, `reuniao_1_1`, `apresentacao_tecnica`, `espontanea`,
`pratica_plateia`) passam pelo mesmo `analyze_session`: a única diferença é o
`audience/context/minutes` dado ao agente que reescreve o texto. Para quem usa o app, todos
devolvem o mesmo resultado (pilares, vícios, ritmo e texto adaptado). Não há onde o usuário
diga o que vai treinar (produto, ideia central, objetivo da conversa), nem um resultado que
dependa do modo.

## Comportamento esperado
Cada modo pode declarar um **cenário** com três partes:
1. **Briefing** antes de gravar: campos que o usuário preenche ou sorteia (ex.: produto e
   comprador no Pitch). `GET /v1/meta` descreve os campos de cada modo, para o app montar a tela.
2. **Avaliador do cenário**: uma única chamada extra ao LLM, com rubrica fixa, sobre a
   transcrição e o briefing.
3. **`mode_result`** no `SessionResult`: bloco opcional e tipado por modo. A análise de fala
   atual continua idêntica; o app só ganha um cartão a mais.

Modos sem cenário continuam exatamente como hoje. O avaliador roda **em segundo plano**
(mesmo executor da avaliação online do `/v1/ask`, spec 004): o `POST /v1/sessions` volta logo
com `mode_result_status: "pending"` e o app consulta `GET /v1/sessions/{id}` até `ready` ou
`error`. Assim a análise de fala aparece sem esperar mais 15–60 s do LLM local. Se o avaliador
falhar (LLM fora, JSON inválido), a sessão fica com `mode_result: null`, status `error` e
`mode_result_error` com motivo curto em português.

## Critérios de aceite
- **AC-1:** `GET /v1/meta` traz em cada modo `briefing`: lista de campos (`id`, `label`,
  `kind` ∈ `text|choice`, `required`, `options` quando `choice`, `max_length`) ou `[]`.
- **AC-2:** `POST /v1/sessions` aceita o campo de formulário opcional `briefing` (JSON). Campo
  obrigatório ausente, desconhecido ou acima do limite → 422 com mensagem em português.
- **AC-3:** Modo sem cenário: a resposta é igual à atual, com `mode_result: null`,
  `mode_result_status: "none"` e `briefing: null` (testado com o mesmo áudio fake de hoje).
- **AC-4:** Modo com cenário: o `POST` responde com `mode_result_status: "pending"`; o
  avaliador roda uma vez em segundo plano, depois da transcrição, e grava `mode_result` (com
  `kind` do cenário) e `mode_result_status: "ready"` na sessão salva. O texto do briefing e da transcrição
  entra no prompt como dado, nunca como instrução (mesma regra dos trechos no `chain.py`).
- **AC-5:** Falha do avaliador não derruba a sessão: `mode_result: null`,
  `mode_result_status: "error"`, `mode_result_error` preenchido, `POST` com 201. Avaliação
  `pending` de um processo anterior vira `error` ao iniciar a API (como na spec 004 AC-4).
- **AC-6:** `briefing` e `mode_result` são salvos e voltam em `GET /v1/sessions/{id}`;
  sessões antigas são lidas com `briefing`/`mode_result` `null` e status `none`.
- **AC-7:** O OpenAPI descreve `mode_result` como união discriminada por `kind`, para o
  `mobile_cognus` gerar os tipos sem `any`.
- **AC-8:** Cada avaliação de cenário vira um trace no MLflow local com `flow=scenario` e a
  tag `scenario=<id>`.

## Fora de escopo
- Análise ao vivo durante a gravação (exige streaming de áudio).
- Telas do app mobile (spec própria no `mobile_cognus`).
- Cenários de Apresentação com documento, 1:1 com role-play e Q&A da plateia (specs futuras).

## Plano (preenchido depois da aprovação)
| Passo | Arquivo | Subagente | Verificação |
|---|---|---|---|
| 1 | `tests/test_scenarios.py`, `tests/test_api.py` | engenheiro-ia | testes falham por AC-1..AC-8 |
| 2 | `src/rag_cognus/scenarios/base.py` | engenheiro-ia | AC-4, AC-5, AC-8 verdes |
| 3 | `api/schemas.py`, `api/app.py`, `api/store.py` | engenheiro-ia | AC-1..AC-3, AC-6, AC-7 |
| 4 | — | engenheiro-devops | `python hermes/harness/check.py` |

Contrato para o app mobile: `/Users/estevaolins/OpenBot/Shared/cognus-contrato-cenarios-pitch.md`.
