# /metrics da API no formato Prometheus

Spec: [016-api-metrics-prometheus.md](../../specs/016-api-metrics-prometheus.md).
Código: `src/rag_cognus/api/metrics.py` e o middleware ligado em `create_app()`.

## 1. O formato texto 0.0.4 e por que geramos na mão

O Prometheus (e o Grafana Alloy, que fala o mesmo protocolo) lê uma página de texto puro:

```
# HELP rag_cognus_http_requests_total Requisições HTTP atendidas pela API.
# TYPE rag_cognus_http_requests_total counter
rag_cognus_http_requests_total{method="GET",route="/v1/profile",status="200"} 3
```

Cada métrica tem uma linha `# HELP`, uma `# TYPE` e as amostras `nome{labels} valor`. Um
histograma vira três famílias de linhas: `_bucket{le="..."}` (contagens **cumulativas**: o
bucket `le="5"` conta tudo que levou até 5 s, inclusive o que caiu em `le="1"`), `_sum` e
`_count`. O `Content-Type` é `text/plain; version=0.0.4; charset=utf-8`.

Não usamos `prometheus_client`: ele não está no `.venv`, adicioná-lo mexeria em
`pyproject.toml` e `uv.lock`, e o registro global dele vaza entre os `create_app()` dos
testes. Precisamos só de counter, gauge e histograma com labels (cerca de 150 linhas,
cobertas pelos testes de formato). Se um dia quisermos métricas de processo ou
OpenMetrics, a troca fica restrita a `api/metrics.py`.

Cada `create_app()` cria o seu `Registry`: as métricas ficam em memória, por processo, e
zeram quando a API reinicia (o `rate()` do PromQL trata o reset de counters).

## 2. Métricas, labels e buckets

| Métrica | Tipo | Labels | O que mede |
|---|---|---|---|
| `rag_cognus_http_requests_total` | counter | `method`, `route`, `status` | requisições atendidas |
| `rag_cognus_http_request_duration_seconds` | histogram | `method`, `route`, `status` | duração HTTP total |
| `rag_cognus_ask_duration_seconds` | histogram | `outcome` (`ok`/`error`) | só o `pipeline.predict` do `/v1/ask` (recuperação + LLM) |
| `rag_cognus_judge_score` | histogram (1..5) | `metric` | notas do juiz online (chaves de `judges.METRICS` + `quality_score`) |
| `rag_cognus_online_eval_total` | counter | `outcome` (`ok`/`error`) | avaliações online concluídas |

Buckets de latência (s): `0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 20, 30, 60, 120, +Inf`,
pensados para o Qwen 9B local, que pode levar dezenas de segundos com o modelo frio.
Buckets das notas: `1, 2, 3, 4, 5, +Inf`.

**Template da rota, nunca o path cru.** `/v1/sessions/abc123` vira
`route="/v1/sessions/{session_id}"`. Dois motivos:

- *Cardinalidade*: cada combinação de labels é uma série no Grafana Cloud (e é cobrada).
  Com o path cru, cada sessão criaria uma série nova.
- *Privacidade*: ids, texto da pergunta, `niche` e nomes de arquivo não saem do Mac.

Path que não casa com rota nenhuma conta como `route="unmatched"`. O próprio `/metrics` não
é contado (o scrape a cada 15 s poluiria o painel). Exceção não tratada conta como
`status="500"` e continua subindo como antes.

**Notas do juiz.** Quando a avaliação online (spec 004) termina, `run_online_evaluation`
chama `record_judge_scores(registry, metrics)`. Nomes fora da lista e valores não numéricos
são ignorados; uma falha ao registrar não muda o resultado da avaliação.

## 3. Ver localmente

```bash
rag-cognus api
curl -s http://127.0.0.1:8001/metrics | head -30
```

`/metrics` não consulta MLflow, Ollama nem Databricks e não aparece no `/docs`.

## 4. PromQL de exemplo

```promql
# p95 por rota (5 min)
histogram_quantile(0.95, sum by (le, route) (rate(rag_cognus_http_request_duration_seconds_bucket[5m])))

# taxa de erro 5xx
sum(rate(rag_cognus_http_requests_total{status=~"5.."}[5m]))
  / sum(rate(rag_cognus_http_requests_total[5m]))

# perguntas por minuto
sum(rate(rag_cognus_ask_duration_seconds_count[5m])) * 60

# média da nota do juiz por métrica na última hora
sum by (metric) (increase(rag_cognus_judge_score_sum[1h]))
  / sum by (metric) (increase(rag_cognus_judge_score_count[1h]))
```

## 5. Próximo passo: Grafana Cloud

O envio ao Grafana Cloud (Alloy, remote write, dashboard) está em
[mlflow-grafana.md](mlflow-grafana.md). Atenção: o `GRAFANA_SERVICE_ACCOUNT_TOKEN` usado pelo
MCP do Hermes **não serve** para remote write; o Alloy precisa de um token de Access Policy
com escopo `metrics:write`.
