---
name: grafana-alerting-import
description: Grafana Cloud não lê provisioning por arquivo; alertas vão em YAML Prometheus via UI/API /api/convert; progresso do genai.evaluate = traces do run
metadata:
  type: reference
---

- Grafana Cloud: "Provisioning with configuration files is not available" (docs set-up/provision-alerting-resources).
  Caminho usado (spec 021): `infra/grafana/alerts.yaml` em formato de regras do Prometheus, importado
  em Alerting → Alert rules → "Import to Grafana-managed rules" → Prometheus YAML file, ou
  `POST <grafana>/api/convert/prometheus/config/v1/rules/<pasta>` (um grupo; header
  `X-Grafana-Alerting-Datasource-UID`; 202). Recusa `limit` no grupo; `query` em template não funciona.
- MLflow 3.18 `genai.evaluate`: durante o run RUNNING só há `index_build_seconds`, os params
  (incl. `cases`) e um trace por caso concluído (`search_traces(run_id=...)`); `*/mean` só no fim.
- Guard: escrever `$NOME_TOKEN` em heredoc de Bash é bloqueado; gerar docs via script no scratchpad
  com placeholder `<token>`. Ver [[guard-quirks]].
