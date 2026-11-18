# 019 — Docker Compose único para os serviços locais

- **Status:** rascunho
- **Módulos:** `compose.yaml` (novo, raiz), `Dockerfile` (novo, raiz), `.dockerignore` (novo),
  `src/rag_cognus/config.py` (`ensure_local_tracking`), `src/rag_cognus/cli.py`
  (`mlflow-local --host/--allowed-hosts`), `infra/alloy/config.alloy` (targets por variável)
- **Testes:** `tests/test_docker_compose.py` (novo), `tests/test_config.py`,
  `tests/test_cli_mlflow_check.py`
- **Revisão obrigatória:** engenheiro de IA (o `config.py` é compartilhado)

## Problema
Para usar o projeto hoje é preciso abrir até cinco terminais: `rag-cognus mlflow-local`,
`rag-cognus api`, `rag-cognus mlflow-exporter`, o Alloy (`infra/alloy/docker-compose.yml`),
o Streamlit e o `npm run dev` do `../frontend_UI`. O usuário quer subir tudo com um comando
(Mac M4, 24 GB, Docker Desktop). Além disso, dentro de uma rede do Compose o MLflow se chama
`http://mlflow:5001`, e `ensure_local_tracking` recusa essa URI porque só aceita loopback.

## Decisões (do líder técnico)
- **Ollama fica no host.** O Docker Desktop no Mac roda uma VM Linux sem acesso à GPU Metal;
  dentro de um container o Qwen 9B rodaria só em CPU (lento demais). Os containers usam
  `OLLAMA_BASE_URL=http://host.docker.internal:11434`. O Compose não sobe Ollama.
- **Hermes fica no host** (CLI interativa; `hermes/harness/services.py` continua checando
  `127.0.0.1:<porta>`, que segue válido porque as portas são publicadas no loopback).
- **Uma imagem Python** para `mlflow`, `api`, `mlflow-exporter` e `streamlit`, com `command`
  diferente por serviço.
- **Portas só em `127.0.0.1`** no host.
- Os comandos `rag-cognus ...` sem Docker continuam iguais (sem regressão).

## Achados da investigação (só leitura, 2026-11-18)
- **A API não fala com o Databricks.** `api/app.py` lê só o snapshot `ROOT/.cache/gold.jsonl`
  (+ `gold.manifest.json`) e grava o SQLite/áudios em `ROOT/.cache/app` (`cognus.db`). Quem fala
  com o Databricks é `rag-cognus sync-gold` e o botão de sync do `chat_app.py`. Portanto a API
  **não precisa de nenhum segredo**.
- `ROOT` é calculado por `Path(__file__).parents[...]`: só aponta para a raiz do repositório
  se o pacote estiver instalado **editável** a partir de `/app/src`. O Dockerfile precisa manter
  `uv sync` editável (padrão) com o código em `/app/src`; `--no-editable` quebraria os caminhos.
- `rag-cognus mlflow-local` fixa `--host 127.0.0.1` no `mlflow server`: dentro do container
  ninguém de fora o alcança. Precisa de `--host` (padrão `127.0.0.1`).
- **MLflow 3.18 tem middleware anti DNS rebinding** (`--allowed-hosts`, padrão "localhost +
  IPs privados"). Um pedido com `Host: mlflow:5001` vindo da API seria recusado. O servidor do
  compose precisa de `--allowed-hosts mlflow,mlflow:5001,localhost,localhost:5001,127.0.0.1,`
  `127.0.0.1:5001` (a lista substitui o padrão, então o loopback tem que estar nela).
- Juízes da UI do MLflow (spec 012): `mlflow_local_env()` deriva `OPENAI_API_BASE`,
  `OPENAI_API_KEY=ollama` e `MLFLOW_GENAI_JUDGE_DEFAULT_MODEL` de `OLLAMA_BASE_URL` e
  `OLLAMA_JUDGE_MODEL`/`OLLAMA_CHAT_MODEL`. Rodando `rag-cognus mlflow-local` no container com
  `OLLAMA_BASE_URL=http://host.docker.internal:11434`, a base vira
  `http://host.docker.internal:11434/v1` sem código novo.
- MLflow usa `--serve-artifacts`: a API envia artefatos pelo servidor, então API e MLflow não
  precisam compartilhar volume de artefatos.
- `uv.lock` (mlflow 3.18.0, streamlit 1.67.0, faster-whisper 1.2.1) tem wheels
  `manylinux_2_28_aarch64` para os nativos: ctranslate2 4.9.0, onnxruntime 1.32.0, av 18.1.0
  (cp311-abi3) / 19.0.2 (cp312-abi3), tokenizers 0.23.3 (abi3), numpy, scipy, pyarrow,
  pydantic-core, hf-xet. Base `python:3.12-slim-bookworm` (glibc 2.36 ≥ 2.28) instala sem
  compilar. Python 3.12 é o mesmo do CI.
- `uv` local: 0.12.15. `dev` é um *extra* (não um grupo), então basta não pedir `--extra dev`.
- Whisper (`speech.py`): `WhisperModel(settings.whisper_model, device="cpu", int8)` baixa o
  modelo do Hugging Face na primeira transcrição (~460 MB para `small`). Precisa de volume de
  cache (`HF_HOME`) para não baixar a cada `up`.
- `infra/alloy/config.alloy` fixa os targets em `host.docker.internal:8001/9105`.
- `../frontend_UI`: Next 16.4.6, React 19.3, **sem Dockerfile**, sem `output: "standalone"`
  no `next.config.ts`. `NEXT_PUBLIC_API_URL` (padrão `http://127.0.0.1:8001`) é lida em
  `src/lib/api/client.ts` e usada só em hooks `"use client"` (React Query): as chamadas saem
  do **navegador**, nunca do servidor Next. Como é `NEXT_PUBLIC_*`, o valor é embutido no
  `next build` (build arg, não segredo).
- CORS padrão da API já inclui `http://localhost:3000` e `http://127.0.0.1:3000`.

## Proposta para `ensure_local_tracking` (menor mudança segura)
Lista explícita, não heurística. "Aceitar qualquer hostname sem ponto" foi descartado: aceitaria
nomes de intranet que ninguém escolheu.

- Nova variável **`MLFLOW_ALLOWED_HOSTS`** (vírgulas; vazia por padrão).
- `ensure_local_tracking(uri, allowed_hosts=None)`: se `None`, lê `MLFLOW_ALLOWED_HOSTS` do
  ambiente. Aceita `http`/`https` quando o hostname está no loopback (como hoje) **ou** na lista.
- Cada item da lista precisa ser **um rótulo DNS único**, `^[a-z0-9]([a-z0-9-]{0,62})$`: sem ponto,
  sem porta, sem esquema e sem IP. Assim `MLFLOW_ALLOWED_HOSTS=databricks.com` ou `10.0.0.5` é
  **erro** de configuração (`ValueError` com mensagem em português), não uma porta aberta.
- `databricks://`, `databricks-uc://` e qualquer outro esquema continuam recusados, mesmo com a
  lista preenchida. Sqlite/file/caminho continuam aceitos.
- Ler o ambiente dentro de `ensure_local_tracking` mantém API, exporter, `mlflow-check` e
  `serve_api` coerentes sem mudar as chamadas existentes.
- Teste e revisão: engenheiro de IA.

## Comportamento esperado
- `docker compose up -d` na raiz sobe `mlflow`, `api`, `mlflow-exporter` (e `alloy` com o
  profile `obs`). `--profile chat` adiciona o Streamlit; `--profile web` adiciona o front.
- O usuário abre `http://127.0.0.1:5001` (MLflow), `:8001/docs` (API), `:9105/metrics`,
  `:8501` (chat), `:3000` (front) como hoje.
- O snapshot da Gold e o SQLite da API vêm do `.cache/` do repositório (bind mount): o que o
  `rag-cognus sync-gold` gerou no host vale no container, sem sync a cada `up`.
- Se o Ollama do host não responder, um serviço de checagem imprime um aviso claro em português,
  e `/v1/health` da API mostra `"ollama": false`; o resto sobe mesmo assim.
- Sem Docker, tudo continua igual (`rag-cognus mlflow-local`, `api`, `mlflow-exporter`, Alloy
  standalone em `infra/alloy/`).

## Desenho

### Imagem Python (`Dockerfile`, multi-stage)
1. `builder`: `python:3.12-slim-bookworm`; `COPY --from=ghcr.io/astral-sh/uv:0.12.15 /uv /bin/`;
   `UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never`; copia `pyproject.toml`
   e `uv.lock`; `uv sync --frozen --no-install-project --extra api --extra ui --extra audio`
   (camada de dependências em cache); copia `src/`; `uv sync --frozen --extra api --extra ui
   --extra audio` (instala o projeto editável). `uv.lock` e `pyproject.toml` **não mudam**.
2. `runtime`: `python:3.12-slim-bookworm`, usuário `app` (UID 1000), `WORKDIR /app`, copia
   `/app` do builder (mesmo caminho, para o `.pth` editável valer), `PATH=/app/.venv/bin:$PATH`,
   `HF_HOME=/home/app/.cache/huggingface`, `USER app`. Sem `ENV`/`ARG` com segredo.
   Sem `CMD` útil: cada serviço define `command`.
- `.dockerignore`: `.env`, `.env.*` (exceto nada: o `.env.example` também fica fora, a imagem
  não precisa dele), `.venv`, `mlruns`, `.cache`, `node_modules`, `.git`, `data/`, `notebooks/`,
  `tests/`, `docs/`, `hermes/`, `.claude/`, `**/__pycache__`, `infra/`.

### `compose.yaml` (raiz)
| Serviço | `command` | Porta no host | Volumes | Profile | Healthcheck |
|---|---|---|---|---|---|
| `mlflow` | `rag-cognus mlflow-local --host 0.0.0.0 --port 5001 --data-dir /app/.cache/mlflow --allowed-hosts mlflow,mlflow:5001,localhost,localhost:5001,127.0.0.1,127.0.0.1:5001` | `127.0.0.1:5001:5001` | `./.cache/mlflow:/app/.cache/mlflow` | — | `GET /health` |
| `api` | `rag-cognus api --host 0.0.0.0 --port 8001` | `127.0.0.1:8001:8001` | `./.cache:/app/.cache`, `hf-cache:/home/app/.cache/huggingface` | — | `GET /v1/health` |
| `mlflow-exporter` | `rag-cognus mlflow-exporter --host 0.0.0.0 --port 9105` | `127.0.0.1:9105:9105` | — | — | `GET /metrics` |
| `ollama-check` | script curto: `GET host.docker.internal:11434/api/tags`; aviso se falhar; sai 0 | — | — | — | — (one-shot, `restart: "no"`) |
| `alloy` | igual ao standalone; `config.alloy` montado de `infra/alloy/` | `127.0.0.1:12346:12345` | `alloy-data` | `obs` | — (imagem sem curl) |
| `streamlit` | `streamlit run src/rag_cognus/chat_app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true` | `127.0.0.1:8501:8501` | `./.cache:/app/.cache`, `hf-cache` | `chat` | `GET /_stcore/health` |
| `frontend` | `node server.js` (standalone) | `127.0.0.1:3000:3000` | — | `web` | `GET /` |

- Healthchecks em Python (`python -c "urllib.request.urlopen(...)"`): a imagem slim não tem curl.
- `depends_on`: `api` e `mlflow-exporter` → `mlflow: service_healthy`; `alloy` → `api` e
  `mlflow-exporter: service_healthy`; `streamlit` → `mlflow: service_healthy`; `frontend` →
  `api: service_healthy`.
- `extra_hosts: ["host.docker.internal:host-gateway"]` nos serviços que falam com o Ollama
  (no Docker Desktop já existe; deixa o compose portável para Linux).
- Sem `container_name` (evita colisão com o `rag-cognus-alloy` standalone).
- `x-rag-env` (âncora YAML) com as variáveis comuns de `api`, `streamlit` e `mlflow-exporter`.
- `.cache/mlflow` é o mesmo store do modo sem Docker: o histórico continua. **Não rode os dois
  modos ao mesmo tempo** (porta 5001 e lock do SQLite).
- Alloy fica no profile `obs` (proposta, ver Pendências): com `:?` nas 3 variáveis do Grafana,
  sem profile o `docker compose up` falharia para quem não usa Grafana Cloud.

### Alloy: um só `config.alloy` para os dois modos
Os targets passam a vir de variável com padrão:
`coalesce(sys.env("RAG_API_TARGET"), "host.docker.internal:8001")` e
`coalesce(sys.env("RAG_MLFLOW_EXPORTER_TARGET"), "host.docker.internal:9105")`.
- Standalone (`infra/alloy/docker-compose.yml`): não define as variáveis → `host.docker.internal`
  (comportamento atual, sem mudar o arquivo de compose standalone).
- Compose da raiz: `RAG_API_TARGET: api:8001` e `RAG_MLFLOW_EXPORTER_TARGET: mlflow-exporter:9105`
  como **literais** no `compose.yaml` (não segredo, não vêm do `.env`).
- Segredos do Alloy continuam só as 3: `GRAFANA_PROM_REMOTE_WRITE_URL`, `GRAFANA_PROM_USER`,
  `GRAFANA_CLOUD_ACCESS_TOKEN`.
- Alternativa descartada: alias de rede `host.docker.internal` no serviço `api` (sequestraria o
  DNS do Ollama dentro da rede).

### Frontend (proposta; arquivos no repo irmão ficam para depois)
- `../frontend_UI/next.config.ts`: `output: "standalone"`.
- `../frontend_UI/Dockerfile`: `node:22-bookworm-slim` (Next 16 exige Node ≥ 20.9);
  `deps` (`npm ci`), `build` (`ARG NEXT_PUBLIC_API_URL=http://127.0.0.1:8001`,
  `NEXT_TELEMETRY_DISABLED=1`, `npm run build`), `runner` (copia `.next/standalone`,
  `.next/static`, `public`; `USER node`; `HOSTNAME=0.0.0.0 PORT=3000`; `node server.js`).
- `../frontend_UI/.dockerignore`: `node_modules`, `.next`, `.env*`, `.git`.
- No `compose.yaml`: `build: {context: ../frontend_UI, args: {NEXT_PUBLIC_API_URL:
  "http://127.0.0.1:8001"}}`. É `127.0.0.1` (e não `http://api:8001`) porque quem chama a API é
  o navegador no Mac. Com isso a origem é `http://127.0.0.1:3000`, já no CORS padrão; a API
  recebe `API_CORS_ORIGINS` explícito com `http://127.0.0.1:3000,http://localhost:3000`.

### Variáveis por serviço (só nomes; nenhum `env_file`)
- **mlflow:** `OLLAMA_BASE_URL` (fixo `http://host.docker.internal:11434`), `OLLAMA_CHAT_MODEL`,
  `OLLAMA_JUDGE_MODEL`. O `mlflow-local` deriva `OPENAI_API_BASE`, `OPENAI_API_KEY`,
  `MLFLOW_GENAI_JUDGE_DEFAULT_MODEL`.
- **api** (`x-rag-env` + extras): `OLLAMA_BASE_URL` (fixo), `OLLAMA_CHAT_MODEL`,
  `OLLAMA_EMBED_MODEL`, `OLLAMA_JUDGE_MODEL`, `OLLAMA_FAST_MODEL`, `OLLAMA_NUM_CTX`,
  `OLLAMA_KEEP_ALIVE`, as 17 de `LLM_ENV` (`OLLAMA_TEMPERATURE` … `OLLAMA_TIMEOUT`),
  `RAG_RETRIEVER`, `RAG_TOP_K`, `RAG_DENSE_MIN_SCORE`, `WHISPER_MODEL`, `GOLD_VIEW`,
  `MLFLOW_TRACKING_URI` (fixo `http://mlflow:5001`), `MLFLOW_ALLOWED_HOSTS` (fixo `mlflow`),
  `MLFLOW_EXPERIMENT_NAME`, `MLFLOW_ONLINE_EXPERIMENT`, `RAG_ONLINE_EVAL`,
  `SPEECH_PLEONASM_LLM`, `API_CORS_ORIGINS`, `HF_HOME`. **Nenhuma `DATABRICKS_*`.**
- **mlflow-exporter:** `MLFLOW_TRACKING_URI`, `MLFLOW_ALLOWED_HOSTS`, `MLFLOW_EXPERIMENT_NAME`,
  `MLFLOW_ONLINE_EXPERIMENT` (o `Settings.from_env()` dele valida o resto com os padrões).
- **streamlit:** o mesmo `x-rag-env` da API. **Sem `DATABRICKS_*`**: o botão de sync da Gold
  falha com a mensagem atual; o sync é feito no host (`rag-cognus sync-gold`), que grava no
  `.cache/` montado.
- **alloy:** `GRAFANA_PROM_REMOTE_WRITE_URL`, `GRAFANA_PROM_USER`, `GRAFANA_CLOUD_ACCESS_TOKEN`
  (`:?`), `RAG_API_TARGET`, `RAG_MLFLOW_EXPORTER_TARGET` (literais).
- **frontend:** build arg `NEXT_PUBLIC_API_URL`; runtime `HOSTNAME`, `PORT`,
  `NEXT_TELEMETRY_DISABLED`.
- **ollama-check:** `OLLAMA_BASE_URL` (fixo).
- Interpolação: valores do `.env` entram por `${VAR:-padrão}` lido pelo próprio Compose. Para as
  variáveis que o `Settings.from_env` lê com `os.getenv(nome, padrão)` sem `or`
  (`RAG_TOP_K`, `RAG_DENSE_MIN_SCORE`, `RAG_RETRIEVER`, `GOLD_VIEW`, `OLLAMA_CHAT_MODEL`,
  `OLLAMA_EMBED_MODEL`, `MLFLOW_EXPERIMENT_NAME`), o padrão no compose é o mesmo do `Settings`
  (`int("")` quebraria a API). As demais aceitam vazio.

## Critérios de aceite

### Código (pytest, TDD)
- **AC-1:** Dado `MLFLOW_ALLOWED_HOSTS=mlflow`, quando `ensure_local_tracking("http://mlflow:5001")`,
  então devolve a URI; sem a variável, a mesma URI levanta `ValueError` (comportamento atual).
- **AC-2:** Mesmo com `MLFLOW_ALLOWED_HOSTS=mlflow`, `databricks://`, `databricks-uc://`,
  `http://mlflow.exemplo.com:5001` e `http://10.0.0.5:5001` continuam recusados.
- **AC-3:** `MLFLOW_ALLOWED_HOSTS` com item inválido (com ponto, IP, porta, esquema) levanta
  `ValueError` com mensagem em português; loopback, sqlite e file continuam aceitos sem a variável.
- **AC-4:** `rag-cognus mlflow-local --host 0.0.0.0 --allowed-hosts a,b` monta o comando do
  `mlflow server` com `--host 0.0.0.0` e `--allowed-hosts a,b`; sem as flags, o comando é
  idêntico ao atual (`--host 127.0.0.1`, sem `--allowed-hosts`) — teste com `subprocess.call`
  fake, sem subir servidor.

### Estáticos do Docker (pytest, `tests/test_docker_compose.py`)
- **AC-5:** `docker compose -f compose.yaml --env-file <.env falso em tmp_path> --profile '*'
  config --format json` sai 0 (skip claro se não houver `docker` no PATH).
- **AC-6:** Toda porta publicada tem `host_ip == "127.0.0.1"`.
- **AC-7:** Nenhum serviço usa `env_file`; nenhum serviço Python recebe `DATABRICKS_TOKEN`,
  `DATABRICKS_HOST` ou `GRAFANA_*`; só `alloy` recebe as 3 do Grafana.
- **AC-8:** `api`, `streamlit` e `mlflow-exporter` têm `MLFLOW_TRACKING_URI=http://mlflow:5001`
  e `MLFLOW_ALLOWED_HOSTS=mlflow`; `api` e `mlflow` têm
  `OLLAMA_BASE_URL=http://host.docker.internal:11434`; não existe serviço `ollama`.
- **AC-9:** Todo `depends_on` de `api`, `mlflow-exporter`, `alloy`, `streamlit` e `frontend`
  usa `condition: service_healthy`, e todo serviço alvo tem `healthcheck`.
- **AC-10:** `streamlit` está só no profile `chat`, `frontend` só em `web` (com
  `build.context` `../frontend_UI` e arg `NEXT_PUBLIC_API_URL=http://127.0.0.1:8001`), `alloy`
  só em `obs`; `alloy` tem `RAG_API_TARGET=api:8001` e
  `RAG_MLFLOW_EXPORTER_TARGET=mlflow-exporter:9105`.
- **AC-11:** `.dockerignore` contém `.env`, `.venv`, `mlruns`, `.cache`, `node_modules`, `.git`.
- **AC-12:** `Dockerfile` tem `USER` não-root no estágio final, usa `uv sync --frozen`, não usa
  `--no-editable`, não tem `ARG`/`ENV` com `TOKEN`/`SECRET`/`PASSWORD`, e não copia `.env`.
- **AC-13:** `infra/alloy/config.alloy` usa `coalesce(sys.env(...), "host.docker.internal:…")`
  para os dois targets e não tem URL com credencial (os testes da spec 017 seguem verdes).
- **AC-14:** O teste do `.env` falso não grava nem lê o `.env` real (usa `tmp_path`).

### Smoke manual (registrado em `docs/estudos/docker-compose.md`, não roda no CI)
- **AC-15:** `docker compose build` termina em arm64; `docker image ls` mostra o tamanho
  (meta: < 2 GB).
- **AC-16:** `docker compose up -d` → `docker compose ps` mostra `mlflow`, `api`,
  `mlflow-exporter` como `healthy` em até 90 s.
- **AC-17:** `curl -s 127.0.0.1:5001/health`, `curl -s 127.0.0.1:8001/v1/health`
  (`"ollama": true`) e `curl -s 127.0.0.1:9105/metrics | head` respondem; `GET /v1/meta` e
  `/v1/home` respondem 200.
- **AC-18:** `POST /v1/ask` com uma pergunta real responde com citações usando o Ollama do host,
  e o trace aparece no experimento `rag-cognus-online` em `http://127.0.0.1:5001`.
- **AC-19:** Com o Ollama do host parado, `docker compose logs ollama-check` mostra o aviso em
  português e a API sobe com `"ollama": false`.
- **AC-20:** `--profile obs`: `alloy` sobe e as séries `rag-cognus-api` e `rag-cognus-mlflow`
  chegam ao Grafana Cloud (`up == 1`). O Alloy standalone (`infra/alloy/docker-compose.yml`) com
  a API no host continua com `up == 1`.
- **AC-21:** `--profile chat` abre `127.0.0.1:8501` e responde uma pergunta;
  `--profile web` abre `127.0.0.1:3000` e a home carrega dados da API sem erro de CORS.
- **AC-22:** Sem Docker: `rag-cognus mlflow-local`, `rag-cognus api`, `rag-cognus
  mlflow-exporter` e `python hermes/harness/check.py` funcionam como antes.

## Fora de escopo
- Ollama ou Hermes em container.
- Sync da Gold dentro do container (credenciais do Databricks em container, `~/.databrickscfg`).
- Criar arquivos no `../frontend_UI` nesta spec (Dockerfile, `.dockerignore`, `output:
  "standalone"`): vão em tarefa/PR do repo do front.
- Publicar imagem em registry; CI construindo a imagem (o CI só roda os estáticos).
- Mudar `uv.lock`, `pyproject.toml`, `.env` ou `.env.example` (as novas variáveis entram no
  `.env.example` só com pedido explícito; `MLFLOW_ALLOWED_HOSTS` não é necessária no host).

## Docs
- `docs/estudos/docker-compose.md` (novo): por que Ollama/Hermes ficam no host (Metal),
  mapa de serviços/portas/profiles, variáveis por serviço, volumes (`.cache/`, `hf-cache`,
  `alloy-data`), `--allowed-hosts` do MLflow, os dois modos do Alloy, fluxo "sync no host →
  `up`", roteiro do smoke (AC-15..22) com a saída real, e "não rode Docker e local juntos".
- `README.md`: seção curta "Subir tudo com Docker" (`docker compose up -d`, profiles `chat`,
  `web`, `obs`) com link para o estudo; seção atual sem Docker fica intacta.
- `infra/alloy/docker-compose.yml`: comentário apontando para o compose da raiz.

## Plano (preenchido depois da aprovação)
| Passo | Arquivo | Responsável | Verificação |
|---|---|---|---|
| 1 | `tests/test_config.py` (AC-1..3) | engenheiro-devops, revisão engenheiro-ia | vermelho |
| 2 | `src/rag_cognus/config.py` | engenheiro-devops, revisão engenheiro-ia | `python hermes/harness/check.py --changed` |
| 3 | `tests/test_cli_mlflow_check.py` (AC-4) → `cli.py` | engenheiro-devops | vermelho → verde |
| 4 | `tests/test_docker_compose.py` (AC-5..14) | engenheiro-devops | vermelho |
| 5 | `Dockerfile`, `.dockerignore`, `compose.yaml`, `infra/alloy/config.alloy` | engenheiro-devops | verde + `docker compose config` |
| 6 | Smoke AC-15..22 | engenheiro-devops (com o usuário) | saída real no estudo |
| 7 | `docs/estudos/docker-compose.md`, `README.md` | engenheiro-devops | revisão do líder |
| 8 | Frontend (Dockerfile, standalone) | tarefa no repo `frontend_UI` | AC-21 |
| 9 | Harness final | líder | `python hermes/harness/check.py` |

## Riscos
- **MLflow `--allowed-hosts`:** sem a flag a API recebe 403/"Invalid Host header" ao falar com
  `mlflow:5001`. Coberto por AC-4/AC-17.
- **arm64:** wheels `manylinux_2_28_aarch64` presentes no lock para todos os nativos; risco
  baixo com `python:3.12-slim-bookworm`. Alpine (musl) não serve.
- **Tamanho da imagem:** mlflow (pandas, pyarrow, scipy, scikit-learn, matplotlib), streamlit,
  faster-whisper (ctranslate2, onnxruntime, av). Estimativa 1,3–1,8 GB; o modelo Whisper
  (~460 MB) fica no volume `hf-cache`, fora da imagem. Uma imagem para quatro serviços é cache
  compartilhado; separar imagens só se passar de 2 GB.
- **Gold/snapshot:** sem `.cache/gold.jsonl` no host, `/v1/ask` responde "Base de conhecimento
  não carregada: rode `rag-cognus sync-gold`" (comportamento atual). O sync é no host.
- **Bind mount e UID:** no Docker Desktop (virtiofs) o UID 1000 do container grava no `.cache/`
  sem problema; em Linux precisaria `user:` igual ao UID do host.
- **Conflito com o modo local:** porta 5001/8001/9105/12346 e o SQLite de `.cache/mlflow`.
  Não rodar os dois modos juntos; o `hermes/harness/services.py` não distingue quem respondeu.
- **Frontend:** sem Dockerfile e sem `standalone` hoje; `NEXT_PUBLIC_API_URL` é embutida no
  build (mudar a porta exige rebuild); `node_modules` local (macOS) não pode entrar no contexto.
- **`coalesce` do Alloy:** confirmar no smoke (AC-20) que a v1.9.0 avalia `sys.env` vazio como
  ausente; se não, usar dois arquivos (`config.alloy` + `config.compose.alloy`).
- **Memória:** 24 GB com o Qwen 9B (~7 GB + KV) no host e a VM do Docker; limite da VM do
  Docker Desktop em ~6 GB basta (sem modelo dentro).

## Pendências para o líder
- Aprovar `alloy` no profile `obs` (desvio da lista original; motivo: `:?` das variáveis do
  Grafana bloquearia o `up` de quem não usa Grafana Cloud).
- Aprovar o desenho de `MLFLOW_ALLOWED_HOSTS` com o engenheiro de IA.
- Abrir a tarefa do `frontend_UI` (Dockerfile + `output: "standalone"`).
