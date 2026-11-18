# 010 — Configuração do LLM por papel (gerador, juiz, rápido)

- **Status:** implementada (IA, 2026-11-18); pendências no fim
- **Módulos:** IA: `src/rag_cognus/llm.py`, `src/rag_cognus/chain.py`,
  `src/rag_cognus/judges.py`, `src/rag_cognus/evaluation.py`,
  `src/rag_cognus/agents/evidence.py`, `src/rag_cognus/agents/communication.py`,
  `src/rag_cognus/agents/agents_judges.py`, `src/rag_cognus/api/app.py` (só o
  `make_ollama` do verificador de pleonasmos); DevOps: `src/rag_cognus/config.py`
  (novos campos de `Settings`), `.env.example`
- **Testes:** `tests/test_config.py`, `tests/test_chain.py`, `tests/test_agents.py`,
  `tests/test_response_metrics.py`, `tests/test_evaluation.py`

## Problema
`make_ollama` (`llm.py:14-33`) fixa `temperature=0`, `reasoning=False`, `timeout=300` e
não envia `top_p`, `top_k`, `repeat_penalty`, `presence_penalty` nem `seed`. O que não é
enviado vem do Modelfile do `qwen3.5:9b` (Ollama 0.32.0, `/api/show`): `temperature 1`,
`top_p 0.95`, `top_k 20`, **`presence_penalty 1.5`**. Com `temperature=0` a amostragem é
gulosa e `top_p`/`top_k` deixam de importar; a penalidade de presença continua agindo e
pune repetir tokens já gerados. Isso atrapalha justamente o que o prompt pede:
copiar `trecho` literal e repetir o mesmo `chunk_id` em `fontes` e `cited_chunk_ids`
(`chain.py:24-29`). O `ChatOllama` 1.1.0 não tem campo `presence_penalty`, então hoje
não há como mudar isso pelo código.

Outros pontos:
- `num_predict` está fixo em cada chamada (`chain.py:98` 900, `judges.py:77` 700,
  `agents_judges.py:78` 600, `evidence.py:73` 200, `evidence.py:75` 1200,
  `communication.py:80` 1500, `api/app.py:113` 300). Se o JSON for cortado, o parser falha
  e a pergunta vira erro, sem nenhum ajuste pelo `.env`.
- Juiz e gerador usam a mesma temperatura e, por padrão, o mesmo modelo
  (`config.py:69`), sem `seed`. Nada disso aparece nos params do MLflow
  (`evaluation.py:144-155`), então não dá para comparar runs com configurações diferentes.
- `num_ctx` é um só (`config.py:40`). Está certo para o mesmo modelo, mas não existe um
  valor próprio quando juiz ou rápido usam outro modelo.
- `.env.example` sugere `OLLAMA_FAST_MODEL=qwen3.5:4b`, que não está instalado
  (`ollama list` mostra só `qwen3.5:9b` e `embeddinggemma`). Nesse caso a decomposição falha
  e cai em silêncio no fallback (`evidence.py:94-95`), e o agente nunca divide o tema.

## Comportamento esperado
- Cada chamada ao Ollama declara um **papel**: `generator` (RAG, síntese de evidências,
  adaptação), `judge` (juízes do RAG e dos agentes) ou `fast` (decomposição, pleonasmos).
- Cada papel tem temperatura, `num_predict`, `think` e penalidades configuráveis pelo `.env`.
  `seed`, `top_p`, `top_k`, `repeat_penalty` e `presence_penalty` são globais e podem ser
  sobrescritos só no juiz.
- **Sem nenhuma variável nova no `.env`, o payload enviado ao Ollama é o de hoje.**
  Valores recomendados ficam comentados no `.env.example` e só são adotados depois de uma
  comparação no `rag-cognus evaluate`.
- `num_ctx` é único por **modelo**: um papel que usa o mesmo modelo do chat sempre recebe
  `OLLAMA_NUM_CTX`, para o Ollama não recarregar o modelo.
- As opções efetivas de cada papel aparecem nos params do run de avaliação.

### Novas variáveis (`.env.example`; o `.env` não é tocado)
| Variável | Padrão (vazio = como hoje) | Recomendado (comentado) | Por quê |
|---|---|---|---|
| `OLLAMA_TEMPERATURE` | `0` | `0` | RAG factual e com citação |
| `OLLAMA_JUDGE_TEMPERATURE` | `0` | `0` | notas reprodutíveis |
| `OLLAMA_FAST_TEMPERATURE` | `0` | `0` | decomposição estável |
| `OLLAMA_SEED` | vazio | `42` | reprodutível se alguém subir a temperatura |
| `OLLAMA_TOP_P` / `OLLAMA_TOP_K` | vazio (Modelfile 0.95 / 20) | vazio | inertes com temperatura 0 |
| `OLLAMA_REPEAT_PENALTY` | vazio | `1.0` | não punir a cópia literal |
| `OLLAMA_PRESENCE_PENALTY` | vazio (Modelfile 1.5) | `0` | idem; JSON repete IDs e chaves |
| `OLLAMA_JUDGE_PRESENCE_PENALTY` | vazio (= global) | `0` | o juiz repete nomes de critério |
| `OLLAMA_GENERATOR_NUM_PREDICT` | vazio (padrão de cada chamada) | — | teto para o JSON longo |
| `OLLAMA_JUDGE_NUM_PREDICT` | vazio | — | idem |
| `OLLAMA_FAST_NUM_PREDICT` | vazio | — | idem |
| `OLLAMA_THINK` / `OLLAMA_JUDGE_THINK` | `false` | `false` | o raciocínio triplica a latência |
| `OLLAMA_JUDGE_NUM_CTX` / `OLLAMA_FAST_NUM_CTX` | vazio (= `OLLAMA_NUM_CTX`) | — | só vale se o modelo for outro |
| `OLLAMA_TIMEOUT` | `300` | `300` | segundos por chamada |

Também no `.env.example`: `OLLAMA_FAST_MODEL=` vazio, com um comentário sobre instalar o
modelo antes de usá-lo.

## Critérios de aceite
- **AC-1:** Dado `Settings()` sem variáveis novas, quando chamo
  `ollama_options(settings, role)` para `generator`, `judge` e `fast`, então recebo
  `temperature=0`, `think=False`, `num_ctx=16384`, `keep_alive="30m"`, `timeout=300` e
  nenhuma das chaves `top_p`, `top_k`, `repeat_penalty`, `presence_penalty` ou `seed`.
- **AC-2:** Dado o ambiente com as novas variáveis (monkeypatch), quando chamo
  `Settings.from_env()`, então cada campo recebe o valor tipado. Temperatura fora de [0, 2],
  `top_p` fora de (0, 1], `num_predict < 64`, `timeout <= 0` ou um `role` desconhecido
  levantam `ValueError` com mensagem em português que cita o nome da variável.
- **AC-3:** Dado `OLLAMA_PRESENCE_PENALTY=0`, `OLLAMA_REPEAT_PENALTY=1.0`, `OLLAMA_SEED=42` e
  `OLLAMA_TOP_P=0.8`, quando chamo `make_ollama(settings, Schema, role="generator")` e
  `chat._chat_params([HumanMessage("x")])`, sem rede, então `options` contém exatamente
  esses valores, além de `temperature`, `num_ctx` e `num_predict`, e o parâmetro `think`
  é `False`.
- **AC-4:** Dado `OLLAMA_JUDGE_NUM_CTX=8192` e `judge_model` vazio ou igual ao
  `chat_model`, quando monto o juiz, então `num_ctx=16384`, porque é o mesmo modelo. Com
  `judge_model="outro:7b"`, então `num_ctx=8192`. A mesma regra vale para `fast`.
- **AC-5:** Dado `make_ollama` substituído por um fake que registra os argumentos, quando
  construo `RagPipeline`, `EvidenceAgent`, `CommunicationAgent`, `make_judge`,
  `make_evidence_judge`, `make_communication_judge` e o verificador de pleonasmos, então
  os papéis registrados são: `RagPipeline` → generator; `EvidenceAgent` → fast
  (decomposição) e generator (síntese); `CommunicationAgent` → generator; os três juízes
  → judge; pleonasmos → fast.
- **AC-6:** Sem `OLLAMA_*_NUM_PREDICT`, o `num_predict` de cada chamada continua o de hoje
  (900, 1200, 1500, 700, 600, 200, 300). Com `OLLAMA_JUDGE_NUM_PREDICT=1000`, todas as
  chamadas de papel `judge` usam 1000 e as outras não mudam.
- **AC-7:** Dado `evaluate(...)` com `isolated_tracking`, pipeline e juiz fakes, quando o run
  termina, então os params incluem `generator_options` e `judge_options` (JSON com
  modelo, temperatura, seed, penalidades, `num_predict` e `num_ctx` efetivos) e
  `judge_is_generator` (`"true"` ou `"false"`).
- **AC-8:** Dado um decompositor fake que levanta exceção, quando `EvidenceAgent.decompose`
  recebe um tema composto, então devolve `[tema]` como hoje e o span `decompose_topic`
  ganha o atributo `fallback_reason` com o nome da exceção (verificado no trace em
  `isolated_tracking`).
- **AC-9:** O `.env.example` lista todas as variáveis da tabela, com padrão vazio ou o atual
  e o valor recomendado em comentário. `Settings.from_env()` com o `.env.example` carregado
  produz o mesmo `ollama_options` do AC-1.

## Impacto nas métricas
- Com os padrões: nenhum, porque o payload é idêntico ao atual (AC-1).
- Com os recomendados (`presence_penalty=0`, `repeat_penalty=1.0`): espera-se
  `citation_integrity` e `groundedness` iguais ou maiores, com menos respostas descartadas
  por "citou ID ausente" ou trecho não literal. A adoção depende de dois runs de
  `rag-cognus evaluate` (antes e depois) com o mesmo `gold_fingerprint`, comparados no
  MLflow local.
- O juiz igual ao gerador continua com viés de autoavaliação. `judge_is_generator` deixa
  isso visível em cada run.

## Fora de escopo
- Trocar de modelo, fazer quantização ou criar um Modelfile próprio (apelido com
  `PARAMETER`). Isso fica como alternativa da spec 012, a cargo do DevOps.
- Mudar prompts ou juízes.
- Streaming.

## Plano (preenchido depois da aprovação)
| Passo | Arquivo | Subagente | Verificação |
|---|---|---|---|
| 1 | `config.py`, `.env.example` (campos e validação) | engenheiro-devops | AC-2, AC-9 |
| 2 | `tests/test_config.py` | engenheiro-ia | AC-1, AC-3, AC-4 vermelhos |
| 3 | `llm.py` (`ollama_options`, `role`, `options` explícito) | engenheiro-ia | AC-1, AC-3, AC-4 |
| 4 | chamadas em `chain.py`, `judges.py`, `agents/*`, `api/app.py` | engenheiro-ia | AC-5, AC-6 |
| 5 | `evaluation.py` (params), `evidence.py` (`fallback_reason`) | engenheiro-ia | AC-7, AC-8 |
| 6 | — | líder | `python hermes/harness/check.py` |

## Pendências (após a implementação da IA)
- AC-9: colar o bloco de variáveis no `.env.example` e remover o `xfail(strict=True)` de
  `test_env_example_lists_llm_variables`.
- O campo de amostragem `top_k` chama-se `llm_top_k` no `Settings`, porque `top_k` já é o
  `RAG_TOP_K`. A variável continua sendo `OLLAMA_TOP_K`.
