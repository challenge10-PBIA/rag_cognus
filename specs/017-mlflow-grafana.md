# 017 — MLflow e API no Grafana Cloud (exporter + Alloy + dashboard)

- **Status:** implementado
- **Módulos:** `src/rag_cognus/mlflow_exporter.py` (novo), `src/rag_cognus/cli.py`
  (`rag-cognus mlflow-exporter`), `infra/alloy/config.alloy`, `infra/alloy/docker-compose.yml`,
  `infra/grafana/rag-cognus-dashboard.json`
- **Testes:** `tests/test_mlflow_exporter.py`, `tests/test_infra_grafana.py`
- **Docs:** `docs/estudos/mlflow-grafana.md`
- **Depende de:** spec 016 (`/metrics` da API e o formato em `api/metrics.py`)

## Problema
As avaliações do RAG (lote e online) só podem ser vistas na UI do MLflow local, um run por
vez, e as métricas da API (spec 016) ficam no Mac. Não há painel único com latência,
notas do juiz e o último run de avaliação, nem histórico no Grafana Cloud.

## Comportamento esperado
- `rag-cognus mlflow-exporter [--host 127.0.0.1] [--port 9105]` serve `/metrics` (formato
  0.0.4) com o servidor HTTP da stdlib. Lê o MLflow local (`Settings.tracking_uri`, sempre
  por `ensure_local_tracking`) com `MlflowClient`; para os experimentos de lote e online,
  publica as métricas do run FINISHED mais recente como
  `rag_cognus_mlflow_run_metric{experiment,metric,backend,chat_model,judge_model}`, mais
  `rag_cognus_mlflow_runs_total{experiment,status}`,
  `rag_cognus_mlflow_last_run_timestamp_seconds{experiment}` e `rag_cognus_mlflow_up`.
- Cache de 30 s. MLflow fora do ar → 200 com `rag_cognus_mlflow_up 0`.
- Labels sem texto livre: nome de métrica normalizado para `[a-z0-9_]` (≤ 64), `backend` em
  `bm25|dense|not_used|other|unknown`, modelos sem espaço/aspas/quebra (≤ 64), no máximo 100
  métricas por run.
- Um Grafana Alloy separado (Docker Compose) faz scrape de `host.docker.internal:8001` (job
  `rag-cognus-api`) e `:9105` (job `rag-cognus-mlflow`) a cada 15 s e envia por remote write
  ao Grafana Cloud, com credenciais só em `sys.env`: só as 3 variáveis do remote write
  entram no container (`environment` interpolado de `--env-file .env`, nunca `env_file`). UI em
  `127.0.0.1:12346`.
- Dashboard importável com datasource `${DS_PROMETHEUS}`.
- API e exporter escutam em 127.0.0.1 por padrão; `--host 0.0.0.0` é opcional e documentado
  como risco (o Docker Desktop do Mac alcança o loopback via `host.docker.internal`,
  conferido em 2026-11-18).

## Critérios de aceite
- **AC-1:** Dado um experimento com runs, quando coleto, então `rag_cognus_mlflow_up 1` e
  cada métrica do run FINISHED mais recente aparece em `rag_cognus_mlflow_run_metric` com os
  labels de experimento, métrica e os params `backend`, `chat_model`, `judge_model`.
- **AC-2:** `rag_cognus_mlflow_runs_total{experiment,status}` conta os runs por status e
  `rag_cognus_mlflow_last_run_timestamp_seconds` é o `end_time` do último FINISHED em segundos.
- **AC-3:** Runs FAILED/RUNNING mais novos não substituem o último FINISHED.
- **AC-4:** Duas coletas em menos de 30 s consultam o MLflow uma vez; depois de 30 s, de novo.
- **AC-5:** Com o MLflow fora do ar (cliente levanta exceção na criação ou na busca), a
  coleta não quebra e devolve `rag_cognus_mlflow_up 0` sem séries de run.
- **AC-6:** `accuracy/mean` vira `accuracy_mean`; nomes vazios após normalizar são
  descartados; nomes longos são cortados em 64; `backend` desconhecido vira `other`, params
  ausentes viram `unknown`; modelos com texto livre ficam sem espaço, aspas ou barra
  invertida e com até 64 caracteres; no máximo `MAX_METRICS_PER_RUN` séries por run.
- **AC-7:** Um tracking URI que não é local levanta `ValueError` ("MLflow local").
- **AC-8:** O servidor HTTP responde `GET /metrics` com 200 e `Content-Type` 0.0.4, e 404
  para outros paths.
- **AC-9:** `rag-cognus mlflow-exporter` usa `127.0.0.1:9105` por padrão; `--host` e
  `--port` mudam isso.
- **AC-10:** Experimento inexistente não é erro: `up` continua 1 e não há séries dele.
- **AC-11:** `infra/alloy/config.alloy` lê URL, usuário e senha só de `sys.env` (exatamente
  `GRAFANA_PROM_REMOTE_WRITE_URL`, `GRAFANA_PROM_USER`, `GRAFANA_CLOUD_ACCESS_TOKEN`), não
  tem token literal nem domínio de stack, e faz scrape de `host.docker.internal:8001` e
  `:9105` (jobs `rag-cognus-api` e `rag-cognus-mlflow`) a cada 15 s.
- **AC-12:** `infra/alloy/docker-compose.yml` é YAML válido, **não** usa `env_file` (o
  `.env` inteiro, com Databricks etc., não entra no container) e o `environment` tem
  exatamente as 3 variáveis, cada uma interpolada como `${NOME:?mensagem}` (o compose falha
  com mensagem clara se faltar alguma); imagem do Alloy com versão fixa, a config montada
  só leitura e UI em `127.0.0.1:12346`. Comando: `docker compose --env-file .env -f
  infra/alloy/docker-compose.yml up -d`, na raiz.
- **AC-13:** `infra/grafana/rag-cognus-dashboard.json` é JSON válido, todo painel usa
  `${DS_PROMETHEUS}` e toda query cita só métricas que existem nos registros da API e do
  exporter (incluindo latência HTTP, `/v1/ask`, notas do juiz, último run e `mlflow_up`).

| AC | Teste |
|---|---|
| AC-1, AC-3 | `test_mlflow_exporter.py::test_latest_finished_run_metrics` |
| AC-2 | `test_mlflow_exporter.py::test_runs_total_and_last_timestamp` |
| AC-4 | `test_mlflow_exporter.py::test_cache_30_seconds` |
| AC-5 | `test_mlflow_exporter.py::test_mlflow_down_reports_up_zero` |
| AC-6 | `test_metric_name_normalized`, `test_params_limited_to_known_values`, `test_metric_series_are_capped` |
| AC-7 | `test_mlflow_exporter.py::test_only_local_tracking` |
| AC-8 | `test_mlflow_exporter.py::test_http_server_serves_metrics` |
| AC-9 | `test_mlflow_exporter.py::test_cli_defaults_to_loopback` |
| AC-10 | `test_mlflow_exporter.py::test_missing_experiment_is_not_an_error` |
| AC-11 | `test_infra_grafana.py::test_alloy_uses_only_sys_env_and_no_token`, `test_alloy_scrapes_api_and_exporter` |
| AC-12 | `test_infra_grafana.py::test_compose_passes_only_three_vars` |
| AC-13 | `test_infra_grafana.py::test_dashboard_queries_use_existing_metrics` |

## Decisões
- **Pull via Alloy**, não push do Python: segredo só no container do Alloy, sem dependência
  nova, falha de rede isolada da API (detalhes em `docs/estudos/mlflow-grafana.md`).
- **Alloy próprio, não o da extensão Grafana do Docker Desktop:** a extensão roda
  `grafana/alloy:v1.0.0` com `/etc/alloy/config.alloy` num volume nomeado gerado pelo
  backend dela; não aceita config do usuário. Nosso Alloy usa `grafana/alloy:v1.9.0`
  (`sys.env` exige Alloy recente; tag conferida com `docker manifest inspect` em 2026-11-18).
- **Só 3 variáveis no container:** `env_file` entregaria o `.env` inteiro (Databricks,
  tokens do MCP) ao Alloy. O compose usa `environment` com `${VAR:?msg}`, preenchido por
  `docker compose --env-file .env`.
- **Loopback por padrão:** `host.docker.internal` no Docker Desktop do Mac chega ao
  127.0.0.1 do host (teste com container descartável em 2026-11-18).
- `rag_cognus_mlflow_runs_total` é gauge (runs podem ser apagados), apesar do sufixo.

## Fora de escopo
- Subir o Alloy ou enviar dados ao Grafana Cloud nos testes/CI.
- Alertas no Grafana Cloud; logs (Loki) e traces (Tempo).
- Métricas de cada run histórico (só o último FINISHED por experimento).
- Novas chaves no `.env.example` (o guard bloqueia; o bloco vai no relatório para o usuário).
