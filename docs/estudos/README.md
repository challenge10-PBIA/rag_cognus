# Material de estudo

Textos que explicam o porquê de cada decisão do rag_cognus. Cada um aponta para a sua spec.

| Arquivo | Do que trata |
|---|---|
| [llm-config.md](llm-config.md) | Opções do LLM por papel (gerador, juiz, rápido) e variáveis do `.env` (spec 010). |
| [mlflow-traces-juizes.md](mlflow-traces-juizes.md) | Como os juízes do MLflow leem um trace e o que mudou nos nossos traces (spec 011). |
| [mlflow-juizes-ollama.md](mlflow-juizes-ollama.md) | Juízes da UI do MLflow no Ollama local: `gateway:/`, `openai:/`, `ollama:/` (spec 012). |
| [hermes-agentes.md](hermes-agentes.md) | Time de agentes no Hermes: papéis, delegação e harness. |
| [hermes-desempenho.md](hermes-desempenho.md) | Hermes lento no Mac: prefill, KV cache, `num_ctx`, slots e toolsets (spec 015). |
| [hermes-mcp-grafana.md](hermes-mcp-grafana.md) | Grafana Cloud no Hermes por MCP, com token só no perfil (spec 009). |
| [api-metrics-prometheus.md](api-metrics-prometheus.md) | `/metrics` da API no formato Prometheus: métricas, labels, buckets e PromQL (spec 016). |
| [mlflow-grafana.md](mlflow-grafana.md) | MLflow e API no Grafana Cloud: exporter, Alloy, remote write e dashboard (spec 017). |
| [agente-observabilidade.md](agente-observabilidade.md) | Papel `[obs]`: serviços, métricas e feedback (spec 009). |
| [agente-avatar.md](agente-avatar.md) | Papel `[avatar]`: contrato do agente de comunicação via avatar (spec 009). |
| [mascote-figura.md](mascote-figura.md) | Figura feminina do mascote: contrato `figure`, desenho, tipos gerados e testes (spec 018). |
