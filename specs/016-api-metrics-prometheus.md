# 016 — Métricas Prometheus da API (/metrics com latência)

- **Status:** implementado
- **Módulos:** `src/rag_cognus/api/metrics.py` (novo), `src/rag_cognus/api/app.py`
- **Testes:** `tests/test_api_metrics.py` (novo; usa o `FakeServices` de `tests/test_api.py`)
- **Docs:** `docs/estudos/api-metrics-prometheus.md` (novo)

> Numeração: escrita como 014 e renomeada para 016 na aprovação, porque
> `specs/014-onboarding-guiado.md` já existe.

## Problema
A API FastAPI (`rag-cognus api`, porta 8001, spec 002) não expõe nenhuma métrica. Hoje só dá
para saber a latência de uma pergunta pelo trace do MLflow, uma por vez; não há como ver
p50/p95 por rota, taxa de erro ou volume de chamadas, nem como o Grafana Cloud coletar isso.
A app tem só o `CORSMiddleware`; não há middleware de medição.

## Comportamento esperado
- `GET /metrics` devolve as métricas no formato texto de exposição do Prometheus 0.0.4, com
  `Content-Type: text/plain; version=0.0.4; charset=utf-8`.
- Toda requisição HTTP para a API (menos o próprio `/metrics`) conta em:
  - `rag_cognus_http_requests_total{method, route, status}` (counter);
  - `rag_cognus_http_request_duration_seconds{method, route, status}` (histogram).
- `rag_cognus_ask_duration_seconds{outcome}` (histogram): tempo só do `pipeline.predict` do
  `POST /v1/ask` (recuperação + LLM), o mesmo `latency` que a rota já calcula.
  `outcome` é `ok` ou `error` (exceção no predict, incluindo o 422). Justificativa: o
  histograma HTTP de `/v1/ask` mistura respostas rápidas que não chegam ao LLM (503 da Gold,
  422 de validação do corpo) com perguntas reais; este isola o custo do RAG e é o número que
  vai para o painel e para alertas.
- Labels:
  - `method`: verbo HTTP em maiúsculas (`GET`, `POST`, `PUT`...); fora da lista padrão vira `OTHER`.
  - `route`: o **template** da rota casada (`/v1/sessions/{session_id}`), nunca o path cru.
    Requisição que não casa com rota (404 de path inexistente) usa `route="unmatched"`.
  - `status`: código HTTP como texto (`"200"`, `"201"`, `"422"`, `"503"`, `"500"`).
    O conjunto de códigos usado pela API é pequeno; não há risco de cardinalidade.
  - Nenhum label recebe query string, corpo, texto da pergunta, `niche`, ids de sessão,
    nome de arquivo ou qualquer dado do usuário.
- Buckets (segundos), iguais nos dois histogramas, pensados para LLM local (Qwen 9B no Ollama,
  com carga a frio do modelo):
  `0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 20, 30, 60, 120, +Inf`.
- Exceção não tratada dentro de uma rota é contada com `status="500"` e a exceção continua
  subindo como antes (o comportamento da API não muda).
- As métricas ficam em memória, por processo; reiniciar a API zera os contadores (normal
  para counters do Prometheus; o `rate()` trata o reset).
- `/metrics` não depende de MLflow, Ollama nem Databricks: responde 200 com a API subida
  sem nenhum deles.
- `/metrics` fica fora do OpenAPI (`include_in_schema=False`) para não poluir o `/docs` do
  front.

### Decisão: dependência `prometheus_client` ou formato na mão
Investigado em 2026-11-18: `prometheus_client` **não** está no `.venv`
(`ModuleNotFoundError`) e não aparece no `uv.lock`; não é transitiva de nada que usamos.

| | (a) adicionar `prometheus_client` | (b) gerar o texto na mão |
|---|---|---|
| Arquivos tocados | `pyproject.toml`, `uv.lock`, `requirements-tested.txt` | nenhum de dependência |
| Código | ~30 linhas (Counter/Histogram prontos) | ~80 linhas (counter, histograma cumulativo, escape de label, lock) |
| Correção do formato | garantida pela lib | coberta por testes (AC-2, AC-3, AC-9) |
| Registro global | `REGISTRY` global vaza entre `create_app()` nos testes; exige `CollectorRegistry` por app | registro é um objeto nosso por app |
| Multiprocesso | modo multiprocess com diretório e env var | não suportado (igual a (a) sem config extra) |
| Evolução (OpenMetrics, exemplars, gauges de processo) | grátis | teria de escrever |

**Recomendação: (b), formato na mão**, num módulo `api/metrics.py` sem dependência nova.
Motivos: só precisamos de 1 counter e 2 histogramas com 3 labels; o formato 0.0.4 é texto
simples e estável; evitamos mexer em `pyproject.toml`/`uv.lock` (que exigem pedido explícito
e reinstalação na máquina do usuário e no CI); e cada `create_app()` ganha um registro novo,
o que deixa os testes isolados sem truque de `REGISTRY`. Se depois quisermos métricas de
processo (CPU, memória, GC) ou OpenMetrics, a troca para `prometheus_client` fica restrita a
`api/metrics.py` e os testes desta spec continuam valendo (testam a saída, não a classe).

## Critérios de aceite
Todos com `fastapi.testclient.TestClient(create_app(FakeServices(...)))`, sem rede, sem
Ollama, sem MLflow servidor e sem Databricks.

- **AC-1:** Dado a API criada, quando faço `GET /metrics`, então recebo 200 e o
  `Content-Type` começa com `text/plain; version=0.0.4`.
- **AC-2:** Dado um `GET /v1/profile` com 200, quando leio `/metrics`, então há
  `rag_cognus_http_requests_total{method="GET",route="/v1/profile",status="200"} 1` e o
  histograma `rag_cognus_http_request_duration_seconds` com os mesmos labels tem `_count 1`,
  `_sum` ≥ 0 e linhas `_bucket` para todos os 13 `le` da lista (incluindo `+Inf`).
- **AC-3:** Dado dois `GET /v1/sessions/{id}` com ids diferentes que não existem, quando leio
  `/metrics`, então existe uma única série `route="/v1/sessions/{session_id}"` com
  `status="404"` e valor 2, e nenhum dos ids aparece no texto de `/metrics`.
- **AC-4:** Dado um `GET /nao-existe`, quando leio `/metrics`, então a série tem
  `route="unmatched"` e `status="404"`, e o path `/nao-existe` não aparece no texto.
- **AC-5:** Dado três `GET /metrics` seguidos, quando leio `/metrics`, então nenhuma série tem
  `route="/metrics"`.
- **AC-6:** Dado um `POST /v1/ask` com uma pergunta contendo um marcador único
  (ex.: `"pergunta-sigilosa-xyz"`) e um `niche`, quando leio `/metrics`, então nem o marcador
  nem o `niche` aparecem no texto, e há série com `route="/v1/ask"`, `method="POST"`.
- **AC-7:** Dado um `POST /v1/ask` que responde 200 com o chat fake, quando leio `/metrics`,
  então `rag_cognus_ask_duration_seconds_count{outcome="ok"} 1`; dado um predict que levanta
  `ValueError` (422), então `outcome="error"` conta 1.
- **AC-8:** Dado uma rota que levanta exceção não tratada (simulada com monkeypatch e
  `TestClient(..., raise_server_exceptions=False)`), quando leio `/metrics`, então a série
  daquela rota tem `status="500"` com valor 1.
- **AC-9:** Dado uma requisição cuja duração é controlada (monkeypatch do relógio usado pelo
  middleware para dar 3,0 s), quando leio `/metrics`, então os buckets `le="2.5"` e menores
  valem 0 e `le="5"` em diante valem 1 (buckets cumulativos), e `_sum` é 3.0.
- **AC-10:** Dado `Services` com `MLFLOW_TRACKING_URI` apontando para uma porta sem servidor e
  Ollama ausente, quando faço `GET /metrics`, então recebo 200 em menos de 1 s (não consulta
  nenhum serviço externo).
- **AC-11:** Dado dois `create_app()` no mesmo processo, quando uso só o primeiro, então o
  `/metrics` do segundo não tem séries `rag_cognus_http_requests_total` (registro por app).
- **AC-12:** Dado o texto de `/metrics`, então cada métrica tem exatamente uma linha
  `# HELP` e uma `# TYPE` (`counter` ou `histogram`) antes das amostras, e o texto termina
  com `\n`.
- **AC-13 (acréscimo aprovado):** Dado um `POST /v1/ask` com avaliação online (spec 004)
  que termina com notas do juiz, quando leio `/metrics`, então:
  - o histograma `rag_cognus_judge_score{metric}` (buckets `1, 2, 3, 4, 5, +Inf`) tem uma
    observação por chave de `rag_cognus.judges.METRICS` e por `quality_score`;
    outras chaves (`citation_integrity`, `latency_seconds`, nomes desconhecidos) e valores
    `None` ou não numéricos são ignorados;
  - `rag_cognus_online_eval_total{outcome="ok"}` vale 1; se o juiz falha, `outcome="error"`
    vale 1 e nenhuma nota é observada;
  - se o registro das notas levantar exceção, a avaliação termina `done` mesmo assim
    (falha de métrica não derruba a avaliação online).
  A função pública é `record_judge_scores(registry, metrics: dict)` em `api/metrics.py`,
  chamada em `run_online_evaluation` logo após `score_online(...)`. A lógica do juiz,
  `evaluation.py` e `judges.py` não mudam.
- **AC-14 (revisão):** Dado um método HTTP fora de `GET, POST, PUT, PATCH, DELETE, HEAD,
  OPTIONS` (ex.: `PROPFIND`), quando leio `/metrics`, então a série usa `method="OTHER"` e o
  nome enviado pelo cliente não aparece no texto (cardinalidade fechada).

| AC | Teste (`tests/test_api_metrics.py`) |
|---|---|
| AC-1 | `test_metrics_endpoint_content_type` |
| AC-2 | `test_request_counter_and_histogram` |
| AC-3 | `test_route_template_not_raw_path` |
| AC-4 | `test_unmatched_route` |
| AC-5 | `test_metrics_route_is_not_counted` |
| AC-6 | `test_no_user_data_in_labels` |
| AC-7 | `test_ask_duration_outcome` |
| AC-8 | `test_unhandled_exception_counts_500` |
| AC-9 | `test_buckets_are_cumulative` |
| AC-10 | `test_metrics_without_external_services` |
| AC-11 | `test_registry_per_app` |
| AC-12 | `test_help_and_type_once_per_metric` |
| AC-14 | `test_unknown_method_becomes_other` |
| AC-13 | `test_judge_scores_histogram`, `test_record_judge_scores_ignores_unknown_and_none`, `test_judge_failure_counts_error`, `test_metrics_failure_does_not_break_evaluation` |

## Fora de escopo
- Instalar/configurar o Grafana Alloy, remote write para o Grafana Cloud, dashboards e
  alertas (próximo passo, abaixo).
- Métricas de processo (CPU, memória, GC), métricas do Streamlit, do MLflow ou do Ollama.
- Separar o tempo de recuperação e de geração dentro do `RagPipeline` (exigiria mexer em
  `chain.py`, domínio do engenheiro de IA; spec própria se o painel pedir).
- Modo multiprocesso / vários workers do uvicorn (`rag-cognus api` sobe um processo só).
- Autenticação no `/metrics` (a API escuta em `127.0.0.1` por padrão).
- Formato OpenMetrics e exemplars com `trace_id`.

## Próximo passo (outra spec): Alloy → Grafana Cloud
- Alloy em Docker no Mac, com `prometheus.scrape` apontando para
  `http://host.docker.internal:8001/metrics` (intervalo 15 s) e `prometheus.remote_write`
  para o endpoint Prometheus da stack `estevaomaia.grafana.net`.
- Credenciais vêm do `.env` por variável de ambiente no `docker run`/compose, nunca no
  arquivo de config versionado. Atenção: o `GRAFANA_SERVICE_ACCOUNT_TOKEN` atual (usado pelo
  MCP do Hermes) é um token da instância Grafana e **não serve para remote write**; o Alloy
  precisa de URL de push, ID de usuário do Prometheus e um token de Access Policy com escopo
  `metrics:write`. Novas chaves irão para o `.env.example` (só nomes) nessa spec.
- Conferir que o Docker Desktop alcança a API ligada em `127.0.0.1:8001` via
  `host.docker.internal`; se não, documentar `rag-cognus api --host 0.0.0.0` com o risco de
  expor a porta na rede local.
- Painel no Grafana Cloud: p50/p95 por rota com `histogram_quantile`, taxa de 5xx e
  `rag_cognus_ask_duration_seconds`; consultável depois pelo agente de observabilidade
  (`query_prometheus`, ver `docs/estudos/hermes-mcp-grafana.md`).

## Plano de documentação
`docs/estudos/api-metrics-prometheus.md` (novo) e uma linha no índice
`docs/estudos/README.md`:
1. O que é o formato de exposição 0.0.4 e por que geramos na mão (resumo da decisão acima).
2. Tabela das métricas, labels e buckets; por que template de rota e não path cru
   (cardinalidade e privacidade).
3. Como ver localmente: `rag-cognus api` e `curl -s http://127.0.0.1:8001/metrics`.
4. Consultas PromQL de exemplo (p95 por rota, taxa de erro, perguntas por minuto).
5. Próximo passo Alloy → Grafana Cloud (seção acima), com o aviso sobre o tipo de token.
O README raiz só ganha uma linha apontando para o estudo, feita quando ninguém estiver
editando o README.

## Plano (preenchido depois da aprovação)
| Passo | Arquivo | Subagente | Verificação |
|---|---|---|---|
| 1 | `tests/test_api_metrics.py` (AC-1…AC-12) | engenheiro-devops | testes falham por falta de `/metrics` |
| 2 | `src/rag_cognus/api/metrics.py` (registro, counter, histograma, render) | engenheiro-devops | `.venv/bin/python -m pytest -q tests/test_api_metrics.py` |
| 3 | `src/rag_cognus/api/app.py` (middleware ASGI, rota `/metrics`, observar `latency` no `/v1/ask`) | engenheiro-devops (rota `/v1/ask` revisada pelo engenheiro-ia) | `python hermes/harness/check.py --changed` |
| 4 | `docs/estudos/api-metrics-prometheus.md` + índice | engenheiro-devops | revisão do líder |
| 5 | harness completo | líder técnico | `python hermes/harness/check.py` |

Notas de implementação para o passo 3:
- O template sai de `request.scope["route"].path` depois de a rota casar (FastAPI 0.162 /
  Starlette 1.10 do `.venv`); sem rota → `"unmatched"`.
- Rotas síncronas rodam no threadpool: o registro precisa de `threading.Lock`.
- Medir com `time.perf_counter()` atrás de uma função monkeypatchável (AC-9).
- O middleware precisa capturar exceção para contar o 500 e relançá-la (AC-8).
