# MLflow e API no Grafana Cloud (exporter + Alloy)

Specs: [017-mlflow-grafana.md](../../specs/017-mlflow-grafana.md) e
[021-monitorar-avaliacao-lote.md](../../specs/021-monitorar-avaliacao-lote.md). Base:
[api-metrics-prometheus.md](api-metrics-prometheus.md) (spec 016).

## Arquitetura

```
Mac (127.0.0.1)                                   Docker Desktop            Grafana Cloud
┌──────────────────────────────┐
│ rag-cognus api      :8001    │◀── scrape 15 s ──┐
│   GET /metrics (spec 016)    │                  │
├──────────────────────────────┤                  │  ┌─────────────────┐   remote write
│ rag-cognus mlflow-exporter   │◀── scrape 15 s ──┼──│ rag-cognus-alloy │ ───────────────▶ Prometheus
│   :9105/metrics (spec 017)   │                  │  │ UI 127.0.0.1:12346│   (basic auth)    (Mimir)
│      │ MlflowClient, cache 30 s                 │  └─────────────────┘                     │
│      ▼                       │   host.docker.internal → loopback do Mac                    ▼
│ rag-cognus mlflow-local :5001│                                                          Dashboard
└──────────────────────────────┘
```

- **API** (`/metrics`): latência por rota, latência do RAG no `/v1/ask`, notas do juiz online.
- **Exporter** (`rag-cognus mlflow-exporter`): para os experimentos `MLFLOW_EXPERIMENT_NAME`
  (lote) e `MLFLOW_ONLINE_EXPERIMENT` (online), publica as métricas do último run FINISHED.
- **Alloy**: o único processo que fala com a nuvem.

### Métricas do exporter

| Métrica | Labels | O que é |
|---|---|---|
| `rag_cognus_mlflow_up` | — | 1 se o MLflow respondeu na última coleta, 0 se não |
| `rag_cognus_mlflow_run_metric` | `experiment`, `metric`, `backend`, `chat_model`, `judge_model` | valor de cada métrica do último run FINISHED |
| `rag_cognus_mlflow_runs_total` | `experiment`, `status` | runs por status (até 10 mil mais recentes); é gauge, apesar do `_total` |
| `rag_cognus_mlflow_last_run_timestamp_seconds` | `experiment` | fim do último run FINISHED (epoch, s) |
| `rag_cognus_mlflow_last_finished_timestamp_seconds` | `experiment` | o mesmo valor, nome explícito (spec 021) |
| `rag_cognus_mlflow_last_run_info` | `experiment`, `run_name`, `status` | 1 para o run mais recente, qualquer status |
| `rag_cognus_mlflow_last_ended_timestamp_seconds` | `experiment`, `run_name`, `status` | fim do último run FINISHED/FAILED/KILLED |
| `rag_cognus_mlflow_run_running` | `experiment`, `run_name` | 1 por run RUNNING (até 5 por experimento) |
| `rag_cognus_mlflow_run_elapsed_seconds` | `experiment`, `run_name` | segundos desde o início do run RUNNING |
| `rag_cognus_mlflow_running_run_metric` | `experiment`, `run_name`, `metric` | métricas já logadas no run RUNNING |
| `rag_cognus_mlflow_run_traces` | `experiment`, `run_name` | traces do run RUNNING (um por caso concluído) |
| `rag_cognus_mlflow_run_cases` | `experiment`, `run_name` | param `cases` do run RUNNING |

Labels sem texto livre: o nome da métrica do MLflow vira `[a-z0-9_]` (`accuracy/mean` →
`accuracy_mean`), até 64 caracteres; `backend` só aceita `bm25`, `dense`, `not_used` (resto
vira `other`); modelos perdem espaço, aspas e quebra de linha; parâmetro ausente vira
`unknown`. No máximo 100 métricas por run. `run_name` vira `[A-Za-z0-9_.:-]` (até 64) e só
aparece para runs RUNNING (até 5) e para o último run/último encerrado de cada experimento.
`runs_total` publica 0 para os status sem runs.

## Por que pull via Alloy (e não push do Python)

- **Segredo num lugar só.** O token de escrita fica no `.env` e só o container do Alloy o
  lê. A API e o exporter não conhecem nenhuma credencial nem fazem chamada de rede.
- **Sem dependência nova.** Push direto exigiria cliente de remote write (protobuf +
  snappy) ou OTLP no Python; o formato texto do Prometheus é stdlib.
- **Falha isolada.** Internet fora ou token errado não afetam a API: o Alloy guarda a fila
  (WAL em `/var/lib/alloy/data`) e reenvia; a API só serve texto.
- **Padrão do Grafana Cloud.** O mesmo Alloy pode depois coletar logs ou o Ollama.
- O MLflow não tem endpoint Prometheus para métricas de run; por isso o exporter lê pela
  API do MLflow (`MlflowClient`) com cache de 30 s, para o scrape de 15 s não martelar o
  servidor.

### Por que não a extensão Grafana do Docker Desktop

Investigado em 2026-11-18 (só leitura, `docker inspect` de Mounts/Cmd e o
`vm/docker-compose.yaml` da extensão): o container `grafana-docker-desktop-extension-alloy`
usa `grafana/alloy:v1.0.0` e roda `/etc/alloy/config.alloy` de um **volume nomeado**
(`..._alloy-volume`) compartilhado com o backend da extensão, que gera esse arquivo pela UI
dela. Não há bind mount de arquivo do usuário nem opção documentada de config própria;
editar o volume seria sobrescrito. Por isso usamos um Alloy separado (`rag-cognus-alloy`),
com a UI em `12346` (a `12345` fica para a extensão).

### host.docker.internal alcança o 127.0.0.1 do Mac?

Sim, no Docker Desktop do Mac. A documentação do Docker
(<https://docs.docker.com/desktop/features/networking/networking-how-tos/>) diz que
`host.docker.internal` "resolves to the internal IP address of your host", mas não fala da
interface de escuta. Conferimos na prática em 2026-11-18: com `rag-cognus api` e
`rag-cognus mlflow-exporter` escutando **só em 127.0.0.1**, um container descartável
conectou em `host.docker.internal:8001` e `:9105` e recebeu `200 OK`. O Docker Desktop
encaminha a conexão pelo processo do backend no Mac, que chega ao loopback.

Portanto **não** é preciso `--host 0.0.0.0`. Se em outra máquina (Linux, Docker sem
Desktop) o scrape falhar, a saída é `rag-cognus api --host 0.0.0.0` e
`rag-cognus mlflow-exporter --host 0.0.0.0`, com o risco de expor `/metrics` (e, no caso
da API, todas as rotas, sem autenticação) para quem estiver na mesma rede. Use só em rede
confiável ou com firewall; nunca é o padrão. No Linux, descomente também o `extra_hosts` do
compose.

## Passo a passo

### 1. Credenciais no `.env`

No Grafana Cloud: **My Account → stack → Prometheus → Details**. Anote a **URL do remote
write** (termina em `/api/prom/push`) e o **Username / Instance ID** (número). Crie um token
em **Access Policies** com escopo `metrics:write`. O `GRAFANA_SERVICE_ACCOUNT_TOKEN` do MCP
não serve aqui.

```dotenv
GRAFANA_PROM_REMOTE_WRITE_URL=https://prometheus-prod-XX-....grafana.net/api/prom/push
GRAFANA_PROM_USER=123456
GRAFANA_CLOUD_ACCESS_TOKEN=<token de Access Policy com metrics:write>
```

O compose **não** usa `env_file`: isso entregaria o `.env` inteiro (Databricks, token do
MCP) ao container. Ele declara em `environment` só as três variáveis acima, como
`${GRAFANA_PROM_USER:?...}`, e o `docker compose --env-file .env` lê os valores do `.env` da
raiz para essa interpolação. Se alguma faltar, o compose para com
`required variable ... is missing a value` antes de criar o container.

### 2. Subir os processos locais

```bash
rag-cognus mlflow-local       # terminal 1: MLflow em 127.0.0.1:5001
rag-cognus api                # terminal 2: API em 127.0.0.1:8001
rag-cognus mlflow-exporter    # terminal 3: exporter em 127.0.0.1:9105
curl -s http://127.0.0.1:8001/metrics | head
curl -s http://127.0.0.1:9105/metrics | grep rag_cognus_mlflow_up
```

### 3. Subir o Alloy

```bash
docker compose --env-file .env -f infra/alloy/docker-compose.yml up -d
docker compose --env-file .env -f infra/alloy/docker-compose.yml logs -f alloy   # Ctrl+C para sair
```

Abra <http://127.0.0.1:12346>: os componentes `prometheus.scrape.rag_cognus_api`,
`prometheus.scrape.rag_cognus_mlflow` e `prometheus.remote_write.grafana_cloud` devem estar
verdes. Para parar: `docker compose --env-file .env -f infra/alloy/docker-compose.yml down`.

### 4. Importar o dashboard

Grafana Cloud → **Dashboards → New → Import** → envie
`infra/grafana/rag-cognus-dashboard.json` → escolha o datasource Prometheus da stack
(`grafanacloud-<stack>-prom`) no campo `DS_PROMETHEUS`.

Painéis: MLflow no ar, avaliações online por resultado, requisições por status, p50/p95 por
rota, latência do `/v1/ask`, média das notas do juiz online, tabela do último run por
experimento e tempo desde o último run; e a linha **Avaliação em lote** (spec 021, abaixo).

**Reimportar depois de mudar o JSON:** Dashboards → New → Import → envie o arquivo de novo →
mesmo datasource → **Import (Overwrite)**. O `uid` (`rag-cognus-api-mlflow`) é o mesmo, então
o link do dashboard não muda; edições feitas na UI do Cloud são sobrescritas.

### 5. Conferir no Explore

```promql
up{job=~"rag-cognus-.*"}
rag_cognus_mlflow_up
sum by (route) (rate(rag_cognus_http_requests_total[5m]))
rag_cognus_mlflow_run_metric{experiment="rag-cognus"}
```

`up` é criado pelo próprio Alloy: 1 = o scrape funcionou.

## Monitorar a avaliação em lote (spec 021)

Com `rag-cognus evaluate` rodando, o run fica RUNNING no MLflow. Escolha o experimento no
seletor **Experimento (lote)** (padrão `rag-cognus`) e veja a linha **Avaliação em lote**:

| Painel | Query | O que mostra |
|---|---|---|
| Em andamento | `rag_cognus_mlflow_run_elapsed_seconds` | nome do run e tempo decorrido (laranja > 30 min, vermelho > 1 h) |
| Progresso do run | `run_traces / run_cases` | traces gravados / casos do param `cases` |
| Último run concluído | `time() - last_ended_timestamp_seconds` | nome, status (FINISHED/FAILED/KILLED) e há quanto tempo |
| Métricas ao longo do tempo | `max by (metric) (run_metric{metric=~".*_mean"})` | cada degrau é um run novo (histórico entre runs) |
| Runs por status | `sum by (status) (runs_total)` | RUNNING, FINISHED, FAILED… |
| Tabela do último run | `rag_cognus_mlflow_run_metric` | experimento, backend, judge_model, métrica e valor |

**O que o MLflow registra enquanto o run está RUNNING** (conferido no MLflow 3.18): só a
métrica `index_build_seconds` (logada antes do `genai.evaluate`; vira
`rag_cognus_mlflow_running_run_metric`), os params (entre eles `cases`) e **um trace por
caso concluído**. As notas `*/mean` só aparecem no fim. O painel de progresso usa esses
traces; o exporter não estima nada além disso. Se um scorer passar a gravar traces próprios,
a razão pode passar de 1 (o painel corta em 100%).

O histórico do painel "ao longo do tempo" começa quando o exporter passa a publicar; runs
anteriores não são reconstituídos.

### Importar os alertas

`infra/grafana/alerts.yaml` está no **formato de regras do Prometheus** (`groups` → `rules`
com `alert`, `expr`, `for`). O Grafana Cloud **não aceita** provisionamento por arquivo
(<https://grafana.com/docs/grafana-cloud/alerting-and-irm/alerting/set-up/provision-alerting-resources/>),
e o YAML de provisionamento do Grafana exige o UID do datasource da stack; o formato do
Prometheus é importado como regras Grafana-managed escolhendo o datasource na hora
(<https://grafana.com/docs/grafana-cloud/alerting-and-irm/alerting/alerting-rules/alerting-migration/>).

**Pela UI:** Alerting → Alert rules → seção *Data source-managed alert rules* → **Import to
Grafana-managed rules** → *Import source*: **Prometheus YAML file** → envie
`infra/grafana/alerts.yaml` → datasource `grafanacloud-<stack>-prom` → pasta (ex.:
`rag-cognus`) → **Import** → *Yes, import*. Depois ligue as regras a um contact point
(Alerting → Notification policies).

**Pela API** (token de service account com permissão de escrita em alertas; o UID do
datasource aparece na URL de Connections → Data sources → Prometheus). Na raiz do repo:

```bash
python -c "import yaml;print(yaml.safe_dump(yaml.safe_load(open('infra/grafana/alerts.yaml'))['groups'][0]))" > /tmp/rag-cognus-grupo.yaml
curl -sS -X POST "https://<stack>.grafana.net/api/convert/prometheus/config/v1/rules/rag-cognus" \
  -H "Authorization: Bearer <token de service account>" \
  -H "X-Grafana-Alerting-Datasource-UID: <uid do grafanacloud-*-prom>" \
  -H "Content-Type: application/yaml" \
  --data-binary @/tmp/rag-cognus-grupo.yaml
```

O endpoint por pasta recebe **um grupo** (por isso o `python` extrai `groups[0]`) e responde
`202`; reenviar substitui o grupo. A importação recusa `limit` no grupo e não suporta a
função `query` em templates (o arquivo não usa nenhum dos dois).

| Regra | Expressão | `for` |
|---|---|---|
| `RagCognusMlflowFora` | `max(rag_cognus_mlflow_up) == 0` | 5m |
| `RagCognusAvaliacaoTravada` | `max by (experiment, run_name) (rag_cognus_mlflow_run_elapsed_seconds) > 3600` | 1m |
| `RagCognusQualidadeBaixa` | `max by (experiment) (run_metric{metric="quality_score_mean"}) < 3.5` | 0m |
| `RagCognusCitacaoBaixa` | `max by (experiment) (run_metric{metric="citation_integrity_mean"}) < 0.9` | 0m |
| `RagCognusRunFalhou` | `delta(rag_cognus_mlflow_runs_total{status="FAILED"}[10m]) > 0` | 0m |
| `RagCognusApiSemDados` | `up{job="rag-cognus-api"} == 0` | 5m |

**Por que `delta` e não `increase` no run FAILED:** `runs_total` é gauge (apagar um run no
MLflow faz o valor cair). `increase` trata queda como reset de contador e soma o valor
inteiro de novo, gerando alerta falso; `delta` é a função para gauges. Como o exporter
publica `FAILED 0` antes da primeira falha, a série já existe e o `delta` vê a subida.

Limites: se o exporter ou o Alloy pararem, as séries somem e as regras ficam em *No data*
(ajuste o *No data state* na UI se quiser alerta nesse caso); qualidade e citação olham o
último run FINISHED (o experimento online usa nomes sem `_mean` e não dispara essas duas).

## Problemas comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `up{job="rag-cognus-api"} 0` | API parada | `rag-cognus api`; `curl 127.0.0.1:8001/metrics` |
| `rag_cognus_mlflow_up 0` | MLflow parado | `rag-cognus mlflow-local`; o exporter tenta de novo a cada 30 s |
| Nada chega no Grafana Cloud; log do Alloy com `401`/`403` | token sem `metrics:write`, usuário errado, ou token do MCP | gere token de Access Policy; confira `GRAFANA_PROM_USER` |
| Log com `404` no push | URL sem `/api/prom/push` | copie a URL completa da página do Prometheus |
| `required variable ... is missing a value` | faltou `--env-file .env` ou a variável no `.env` | rode da raiz com `--env-file .env`; preencha as 3 variáveis |
| `connection refused` em `host.docker.internal` | processo em outra porta ou Docker sem Desktop | confira as portas; no Linux, `extra_hosts` + `--host 0.0.0.0` (ver acima) |
| Porta 12346 ocupada | outro serviço | troque o lado esquerdo de `127.0.0.1:12346:12345` |
| Notas do juiz vazias | nenhuma pergunta no `/v1/ask` ou `RAG_ONLINE_EVAL=false` | faça uma pergunta e aguarde o juiz |
| Painel "último run" vazio | sem run FINISHED nos experimentos | rode uma avaliação em lote ou faça perguntas no `/v1/ask` |
| "Em andamento" vazio com `evaluate` rodando | exporter antigo (antes da spec 021) | reinicie só o exporter: Ctrl+C no terminal dele e `rag-cognus mlflow-exporter` |
| Progresso sem valor | run sem param `cases` ou traces indisponíveis | confira o run na UI do MLflow; o tempo decorrido continua valendo |

Contadores da API zeram a cada reinício; o `rate()`/`increase()` trata o reset. As notas do
juiz por pergunta continuam também no MLflow (`rag-cognus-online`).
