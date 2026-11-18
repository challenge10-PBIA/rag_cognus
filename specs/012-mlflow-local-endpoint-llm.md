# 012 — MLflow local usa o Ollama como LLM dos juízes

- **Status:** implementado (2026-11-18): AC-1…AC-3 verdes; AC-4 entregue como texto ao líder;
  **AC-5 (manual) pendente** (ver "Andamento")
- **Dono:** engenheiro-devops
- **Depende de:** spec 011 (engenheiro-ia; interface pronta) — define o contrato
  `openai:/<OLLAMA_JUDGE_MODEL>` (padrão `openai:/qwen3.5:9b`) e entrega em
  `src/rag_cognus/evaluation.py` as funções puras `ui_judge_model_uri(settings)` e
  `ui_judge_env(settings)` (`OPENAI_API_BASE`, `OPENAI_API_KEY=ollama`,
  `MLFLOW_GENAI_JUDGE_DEFAULT_MODEL`). Esta spec **consome** `ui_judge_env` no `mlflow-local`;
  o passo 2 do Plano só começa depois que a 011 estiver verde.
- **Módulos:** `src/rag_cognus/cli.py` (comando `mlflow-local`), `.env.example` (comentário),
  `README.md` (seção MLflow)
- **Testes:** `tests/test_cli_mlflow_local.py` (novo; `subprocess.call` e `port_in_use` falsos)

## Problema
Juízes LLM criados na UI do MLflow local (`http://127.0.0.1:5001`, aba de juízes/scorers) e as
avaliações agendadas pelo servidor não têm LLM configurado: o MLflow tenta provedores de nuvem
(OpenAI etc.) e falha sem chave. Queremos que rodem no `qwen3.5:9b` do Ollama local, sem
segredo nenhum e sem sair da máquina.

## Diagnóstico (2026-11-18, MLflow 3.18.0 instalado em `.venv`)
Conferido no código instalado (`mlflow/genai/judges/adapters/`, `mlflow/metrics/genai/model_utils.py`,
`mlflow/gateway/providers/ollama.py`, bundle da UI):
1. **Juízes criados na UI usam o AI Gateway do próprio servidor**: o formulário pede
   "Select an endpoint to use for this judge" e grava `model: "gateway:/<endpoint>"`; a UI avisa
   "Automatic evaluation is only available for judges that use gateway endpoints". O Gateway
   precisa de backend SQL (o `mlflow-local` já usa `sqlite:///.cache/mlflow/mlflow.db`) e tem o
   provedor **Ollama** (`DEFAULT_API_BASE = http://localhost:11434/v1`, sem chave por padrão).
   Credenciais do Gateway ficam cifradas no banco com `MLFLOW_CRYPTO_KEK_PASSPHRASE`
   (sem ela, usa uma frase padrão "development only" — aceitável em uso local).
   `mlflow.server.gateway_api` importa sem os extras `mlflow[gateway]`
   (`slowapi`, `boto3`, `tiktoken`, `watchfiles` não estão instalados); se a tela de setup do
   Gateway exigir esses pacotes em execução, **a confirmar** com o servidor no ar.
2. **Juízes em código** (`make_judge`, scorers registrados) com URI direto passam pelo
   `GatewayAdapter` (testado offline):
   - `openai:/qwen3.5:9b` → exige `OPENAI_API_KEY` no processo (qualquer valor, ex. `ollama`) e
     usa `OPENAI_API_BASE`/`OPENAI_BASE_URL` como base → `http://127.0.0.1:11434/v1`.
   - `ollama:/qwen3.5:9b` → provedor nativo, base fixa `http://localhost:11434/v1`, sem env.
3. Jobs do servidor (scorers online, avaliação disparada pela UI) rodam em subprocesso que herda
   `os.environ` do `mlflow server` (`server/jobs/utils.py`), e a execução de jobs vem ligada por
   padrão (`MLFLOW_SERVER_ENABLE_JOB_EXECUTION=True`; `huey` instalado). Portanto as variáveis
   precisam estar **no processo do servidor**, não só no cliente.
4. `rag-cognus mlflow-local` hoje chama `python -m mlflow server --host 127.0.0.1 --port 5001
   --backend-store-uri sqlite:///… --serve-artifacts --artifacts-destination …` sem passar env
   específico (herda o ambiente do shell + `.env` carregado por `load_dotenv`).
5. Estado: MLflow 5001 **fora do ar** (`/health` sem resposta); Ollama no ar com `qwen3.5:9b`
   e `/v1/models` respondendo 200.

## Comportamento esperado
- `rag-cognus mlflow-local` sobe o servidor com o ambiente de `ui_judge_env(settings)` (spec 011):
  `OPENAI_API_BASE` apontando para o Ollama (`$OLLAMA_BASE_URL/v1`, padrão
  `http://127.0.0.1:11434/v1`), `OPENAI_API_KEY=ollama` e
  `MLFLOW_GENAI_JUDGE_DEFAULT_MODEL=openai:/qwen3.5:9b` (juiz padrão da UI e dos scorers sem
  modelo), **só para as variáveis que ainda não estiverem definidas** (respeita quem já
  configurou), e imprime uma linha com o URI do juiz e a base (nunca o valor de uma chave).
- Assim funcionam no servidor: juízes da UI via endpoint do Gateway com provedor Ollama
  (`gateway:/ollama-qwen`), e juízes em código com `openai:/qwen3.5:9b` ou `ollama:/qwen3.5:9b`.
- Nenhuma mudança no tracking (continua só `http://127.0.0.1:5001`; `databricks://` proibido).

## Critérios de aceite
- **AC-1:** Dado ambiente sem `OPENAI_API_BASE`/`OPENAI_BASE_URL`/`OPENAI_API_KEY` e
  `OLLAMA_BASE_URL=http://127.0.0.1:11434`, quando `mlflow-local` monta o processo, então o `env`
  passado ao `subprocess.call` tem `OPENAI_API_BASE=http://127.0.0.1:11434/v1`,
  `OPENAI_API_KEY=ollama` e `MLFLOW_GENAI_JUDGE_DEFAULT_MODEL=openai:/qwen3.5:9b` (vindos de
  `evaluation.ui_judge_env`), e o comando continua igual ao atual (host 127.0.0.1, porta,
  SQLite, `--serve-artifacts`).
- **AC-2:** Dado `OPENAI_API_BASE`, `OPENAI_API_KEY` ou `MLFLOW_GENAI_JUDGE_DEFAULT_MODEL` já
  definidos no ambiente, quando
  `mlflow-local` roda, então esses valores não são sobrescritos e nenhum valor de chave aparece
  na saída (`capsys`).
- **AC-3:** Dado `OLLAMA_BASE_URL` com barra final ou já terminando em `/v1`, quando montado o
  `OPENAI_API_BASE`, então o resultado termina em exatamente um `/v1` (se a normalização
  ficar em `ui_judge_env`, este AC vira teste da 011 e aqui só se confere o repasse).
- **AC-4:** Dado o `.env.example`, quando lido, então documenta (comentado) `OPENAI_API_BASE`,
  `OPENAI_API_KEY=ollama` e `MLFLOW_CRYPTO_KEK_PASSPHRASE` como opcionais, sem valores reais.
  (O guard bloqueia edição de `.env.example` por agentes — ver Riscos; o texto vai para o líder.)
- **AC-5 (manual, documentado):** Com `mlflow-local` e Ollama no ar, um endpoint `ollama-qwen`
  criado na UI (provedor Ollama, modelo `qwen3.5:9b`) e um juiz da UI usando esse endpoint
  avaliam um trace e gravam um assessment; repetir com um juiz em código
  `openai:/qwen3.5:9b`. Resultado registrado no relatório (sem teste automático: exige rede).

## Fora de escopo
- Escolher o URI final dos juízes e escrever os juízes (spec 011, engenheiro-ia).
- Instalar `mlflow[gateway]`/`mlflow[genai]` ou mudar `uv.lock` — só se o AC-5 mostrar que é
  necessário; aí vira mudança de dependência justificada (faixa `mlflow[genai]>=3.6,<4`).
- `--expose-prometheus`/Grafana (spec 009 e spec futura).

## Interface com a spec 011 (engenheiro-ia)
| Onde o juiz roda | URI do modelo | Requisito no servidor |
|---|---|---|
| Juiz criado na UI / avaliação automática da UI | `gateway:/ollama-qwen` | endpoint `ollama-qwen` criado no AI Gateway (passo 3 abaixo) |
| Juiz em código, formato pedido | `openai:/qwen3.5:9b` | `OPENAI_API_BASE` + `OPENAI_API_KEY` no processo (AC-1) |
| Juiz em código, alternativa sem env | `ollama:/qwen3.5:9b` | nenhum (base fixa `localhost:11434`) |

O modelo vem de `OLLAMA_JUDGE_MODEL` (manter configurável; juiz = gerador tem viés).
**Dependência:** a 011 já escolheu `openai:/` como contrato (linha 2) e, via
`MLFLOW_GENAI_JUDGE_DEFAULT_MODEL`, ele vira o padrão dos juízes pré-prontos. Para a
**avaliação automática agendada pela UI**, o bundle 3.18 exige endpoint do Gateway (linha 1):
**a confirmar no AC-5** se um juiz da UI sem endpoint escolhido cai no
`MLFLOW_GENAI_JUDGE_DEFAULT_MODEL`; se não cair, o endpoint `ollama-qwen` é obrigatório.

### Pedidos da spec 011 para esta spec
- Ollama com `OLLAMA_CONTEXT_LENGTH` = `OLLAMA_NUM_CTX` e `OLLAMA_NUM_PARALLEL=1`: é
  configuração do serviço do Ollama (fora do `mlflow-local`); entra no passo a passo manual.
  **Conflito:** o perfil Hermes pede `OLLAMA_NUM_PARALLEL=3` (pai + 2 subagentes,
  `hermes/install.sh`). Decisão do líder: 1 ao avaliar, 3 ao usar o Hermes, ou 2 como meio-termo.
- Desligar o raciocínio do qwen3.5 pelo `/v1`: **a confirmar** (Ollama 0.32.0). Candidatos:
  parâmetro `reasoning_effort: "none"` no corpo do `/v1/chat/completions` ou `think: false` no
  `/api/chat` nativo; o provedor `openai` do MLflow não expõe esse parâmetro por env. Validar
  com uma chamada real quando o usuário autorizar (não feita neste diagnóstico).

## Passo a passo manual (usuário)
1. Ollama no ar com o modelo: `ollama list` mostra `qwen3.5:9b` (senão `ollama pull qwen3.5:9b`).
   Para avaliar: `launchctl setenv OLLAMA_CONTEXT_LENGTH <valor de OLLAMA_NUM_CTX>` e
   `launchctl setenv OLLAMA_NUM_PARALLEL 1`, depois reiniciar o app do Ollama (ver conflito com
   o Hermes acima).
2. Subir o MLflow: `.venv/bin/rag-cognus mlflow-local` (porta 5001). Depois da implementação, a
   saída avisa que `OPENAI_API_BASE` aponta para o Ollama. Antes dela, equivalente manual:
   `OPENAI_API_BASE=http://127.0.0.1:11434/v1 OPENAI_API_KEY=ollama
   MLFLOW_GENAI_JUDGE_DEFAULT_MODEL=openai:/qwen3.5:9b .venv/bin/rag-cognus mlflow-local`
   (uma linha só).
   Opcional: `MLFLOW_CRYPTO_KEK_PASSPHRASE` no `.env` (frase sua; não compartilhe).
3. Na UI (`http://127.0.0.1:5001`) → **AI Gateway** → criar endpoint `ollama-qwen`: provedor
   **Ollama**, modelo `qwen3.5:9b`, base `http://127.0.0.1:11434/v1` (se pedir chave, use
   `ollama`). Testar o endpoint pela própria tela.
4. No experimento → **Judges/Scorers** → novo juiz LLM → instruções em português → **Endpoint:**
   `ollama-qwen` → salvar e rodar em alguns traces. Conferir o assessment no trace.
5. Conferência rápida: `.venv/bin/rag-cognus mlflow-check` e `curl -s http://127.0.0.1:5001/health`.
6. Se o 9B errar o formato da resposta do juiz, reduzir a instrução e usar saída sim/não;
   relatar ao engenheiro-ia (spec 011).

## Riscos e dúvidas
- `OPENAI_API_KEY=ollama` no processo do servidor faz qualquer `openai:/gpt-…` ir para o Ollama
  e falhar com "model not found" — desejado aqui, mas deve ficar documentado.
- O guard (`hermes/hooks/guard.py`, `PROTECTED` por prefixo `.env`) impede agentes de editar
  `.env.example`: o AC-4 será entregue como texto para o líder/usuário aplicar.
- Telas do Gateway podem exigir extras `mlflow[gateway]` em runtime (a confirmar no AC-5); isso
  mudaria `pyproject.toml` e `uv.lock` (`uv lock`) com pedido explícito.
- Qwen 9B como juiz e gerador: viés de autoavaliação e latência; com `OLLAMA_NUM_PARALLEL` baixo,
  jobs do MLflow competem com o chat/Hermes pelo mesmo slot.
- Hoje o `mlflow-local` não chama `Settings.from_env()`; se `ui_judge_env` exigir `Settings` e
  o `.env` estiver incompleto (ex.: sem Databricks), o MLflow não pode deixar de subir: em erro
  de configuração, subir sem o env extra e avisar em uma linha (incluir no teste do AC-1).
- `localhost` x `127.0.0.1`: o provedor nativo `ollama:/` usa `localhost`; o Ollama escuta em
  `*:11434`, então ambos funcionam nesta máquina.

## Plano (preenchido depois da aprovação)
| Passo | Arquivo | Subagente | Verificação |
|---|---|---|---|
| 1 | `tests/test_cli_mlflow_local.py` (AC-1…AC-3) | engenheiro-devops | falha: env não passado |
| 2 | `src/rag_cognus/cli.py` (`mlflow-local`: `{**ui_judge_env(settings), **os.environ}` → `subprocess.call(env=…)`), depois da 011 | engenheiro-devops | `python hermes/harness/check.py --changed` |
| 3 | texto do `.env.example` e `README.md` (AC-4) | engenheiro-devops → líder aplica `.env.example` | revisão |
| 4 | AC-5 manual com serviços no ar | usuário + engenheiro-devops | assessment gravado no trace |
| 5 | tudo | líder técnico | `python hermes/harness/check.py` → `HARNESS OK` |

## Plano de documentação para estudo (escrever depois)
- `docs/estudos/mlflow-juizes-ollama.md` — AI Gateway x URI direto (`gateway:/`, `openai:/`,
  `ollama:/`), por que o env precisa estar no processo do servidor (jobs herdam `os.environ`),
  passo a passo da UI, solução de problemas (porta 5000 do AirPlay, chave ausente, formato JSON).
  **Feito**; índice em `docs/estudos/README.md`.

## Andamento (2026-11-18)
| AC | Situação | Teste |
|---|---|---|
| AC-1 | verde | `tests/test_cli_mlflow_local.py::test_mlflow_local_passes_ollama_judge_env`, `::test_mlflow_local_uses_judge_model`; `tests/test_local_server.py::test_local_server_uses_loopback_and_private_artifacts` (env = `os.environ` + juiz) |
| AC-2 | verde | `::test_mlflow_local_keeps_existing_vars_and_hides_key`, `::test_mlflow_local_never_prints_default_key`, `::test_mlflow_local_respects_openai_base_url` |
| AC-3 | verde (normaliza em `ui_judge_env`; aqui confere o repasse) | `::test_mlflow_local_single_v1_suffix` (3 casos) |
| `.env` inválido | verde | `::test_mlflow_local_starts_with_defaults_on_bad_settings` |
| AC-4 | texto entregue ao líder (o guard bloqueia `.env.example` para agentes) | — |
| AC-5 | **pendente (manual)** | passo a passo abaixo |

Implementação: `src/rag_cognus/cli.py`, `mlflow_local_env()` → `subprocess.call(command,
env=env)`; o comando do servidor não mudou. Decisão do líder (substitui o risco acima): com
`.env` inválido, o comando sobe **com os padrões do `Settings`** (não sem o env extra) e avisa
em uma linha. Se `OPENAI_BASE_URL` já existir, `OPENAI_API_BASE` não é criado (evita duas bases).

### AC-5: o que o usuário roda (Ollama no ar)
1. `launchctl setenv OLLAMA_NUM_PARALLEL 1` e `launchctl setenv OLLAMA_CONTEXT_LENGTH 16384`
   (= `OLLAMA_NUM_CTX`); reiniciar o app do Ollama.
2. `.venv/bin/rag-cognus mlflow-local` → conferir a linha
   `Juízes da UI: openai:/qwen3.5:9b (base http://127.0.0.1:11434/v1)`.
3. UI `http://127.0.0.1:5001` → **AI Gateway** → endpoint `ollama-qwen` (provedor Ollama, modelo
   `qwen3.5:9b`, base `http://127.0.0.1:11434/v1`, chave `ollama` se pedir) → testar na tela.
4. Gerar 2 ou 3 traces (uma pergunta no chat ou a avaliação em lote com `--generate --limit 3`).
5. Experimento → **Judges/Scorers** → novo juiz LLM com endpoint `ollama-qwen` → rodar nos
   traces → o assessment aparece no trace.
6. Repetir com um juiz em código `openai:/qwen3.5:9b`.
7. Anotar aqui: a tela do Gateway funcionou sem `mlflow[gateway]`? Um juiz da UI sem endpoint
   cai no `MLFLOW_GENAI_JUDGE_DEFAULT_MODEL`? Ao terminar, voltar `OLLAMA_NUM_PARALLEL 3` e
   `OLLAMA_CONTEXT_LENGTH 32768` (Hermes).
