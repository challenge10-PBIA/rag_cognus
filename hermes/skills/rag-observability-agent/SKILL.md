---
name: rag-observability-agent
description: Papel [obs] no rag_cognus. Use para checar a saúde de MLflow, Ollama e API, ler juízes e feedback no MLflow local, consultar o Grafana Cloud (MCP, só leitura) ou integrar o agente de observabilidade/feedback que chega de fora do repo.
---

# Agente de observabilidade e feedback

O agente já existe **fora deste repo** e vai entrar depois. Até lá: não invente o código.
Use este contrato para diagnosticar o ambiente, preparar a integração e escrever spec/testes.

## Objetivo
Avaliar a aplicação (qualidade do RAG, juízes, feedback da pessoa), a API e o MLflow, e
publicar/consultar sinais no Grafana Cloud (`https://estevaomaia.grafana.net`).

## Primeiro passo: estado dos serviços
`python hermes/harness/services.py` — uma linha `[UP]/[DOWN] serviço url` para MLflow
(`/health`), Ollama (`/api/tags`), API (`/v1/health`) e Grafana (se `GRAFANA_URL` estiver no
`.env` do perfil). O resultado fica em cache 5 min e aparece no contexto como `Serviços: …`.

## Pontos de integração que já existem
- Saúde da API: `GET /v1/health` em `src/rag_cognus/api/app.py` (ollama, mlflow, gold_chunks).
- Avaliação online por pergunta: `POST /v1/ask` grava `ask_id`; `GET /v1/ask/{ask_id}/evaluation`
  devolve métricas e juízes (esquema `AskEvaluation` em `src/rag_cognus/api/schemas.py`).
- Feedback humano: `POST /v1/feedback` grava `user_feedback` no trace via `mlflow.log_feedback`.
- Juízes e métricas: `src/rag_cognus/judges.py`, `src/rag_cognus/metrics.py`,
  `src/rag_cognus/evaluation.py`; juízes dos agentes em `src/rag_cognus/agents/agents_judges.py`.
- MLflow **local** em `http://127.0.0.1:5001` (experimentos `rag-cognus` e `rag-cognus-online`,
  ver `src/rag_cognus/config.py`). URIs `databricks://` são proibidas.
- Grafana Cloud por MCP (`mcp_servers.grafana` em `hermes/config.yaml`): só ferramentas de
  leitura (`search_dashboards`, `get_dashboard_by_uid`, `list_datasources`,
  `query_prometheus`, `query_loki_logs`, `list_alert_rules`). Desligado até o usuário criar o
  token: veja `docs/estudos/hermes-mcp-grafana.md`.

## Contrato esperado
Entrada: janela de tempo (`since`, `until`), experimentos do MLflow, URL da API.
Saída (dict serializável, em português):
- `services`: `[{name, url, up}]` (mesmo formato de `.hermes-runs/services.json`);
- `quality`: médias dos juízes e métricas online por janela, nº de avaliações com erro;
- `feedback`: positivos/negativos de `user_feedback` e comentários mais frequentes;
- `alerts`: lista de achados objetivos (ex.: "fundamentação caiu de 4,2 para 3,1");
- `published`: o que foi enviado ao Grafana (nome da métrica, quantidade), ou vazio.

Regras: leitura do MLflow pelo cliente (`MlflowClient`), nunca escrita em `mlruns/`; nunca
imprime nem registra tokens; publicar no Grafana exige spec própria com dependência
justificada (Prometheus remote write, OTLP ou Alloy).

## Onde o código vai morar (a criar quando o agente chegar)
- Agente: `src/rag_cognus/agents/observability.py` (a criar), classe `ObservabilityAgent`.
- Testes: `tests/test_observability.py` (a criar) — MLflow e HTTP falsos (monkeypatch).
- Spec: `specs/014-agente-observabilidade.md` (a criar; número sugerido).
- Exportação para o Grafana (métricas da API/MLflow): spec futura de devops.

## Como testar sem rede
- `MlflowClient` falso com `search_traces`/`search_runs` devolvendo objetos fixos.
- `http_get` falso como em `tests/test_hermes_services.py`.
- Nada de chamar o Grafana, o Ollama ou o MLflow reais nos testes.

## Verificação
- `.venv/bin/python -m pytest -q tests/test_hermes_services.py tests/test_evaluation.py`
- `python hermes/harness/check.py` → precisa terminar em `HARNESS OK`.

## Retorno
`STATUS | ARQUIVOS | TESTES | HARNESS (última linha) | CONTRATO/IMPACTO | PENDÊNCIAS`.
Estudo: `docs/estudos/agente-observabilidade.md`.
