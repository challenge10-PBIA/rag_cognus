# 021 — Monitorar a avaliação em lote no Grafana Cloud

- **Status:** implementado
- **Módulos:** `src/rag_cognus/mlflow_exporter.py`, `infra/grafana/rag-cognus-dashboard.json`,
  `infra/grafana/alerts.yaml` (novo)
- **Testes:** `tests/test_mlflow_exporter.py`, `tests/test_infra_grafana.py`
- **Docs:** `docs/estudos/mlflow-grafana.md`, `README.md`
- **Depende de:** spec 017 (exporter, Alloy e dashboard)

## Problema
O exporter da spec 017 só publica o último run FINISHED e a contagem por status. Durante um
`rag-cognus evaluate` (dezenas de minutos com o Qwen local) o Grafana mostra apenas
`runs_total{status="RUNNING"} 1`: não dá para ver qual run está rodando, há quanto tempo,
quanto já andou, nem ser avisado se travar, falhar ou sair com qualidade baixa.

## O que o MLflow registra durante um run RUNNING
Conferido no MLflow local 3.18 em 2026-11-18 com o run `rag-bm25-k5` em andamento:
- **Métricas intermediárias:** só `index_build_seconds` (logada antes do
  `mlflow.genai.evaluate`). As métricas `*/mean` só aparecem no fim do run.
- **Params:** `cases` (total de casos) é logado no início.
- **Traces:** o `genai.evaluate` grava um trace por caso, ligado ao `run_id`, à medida que
  cada caso termina (9 traces de 14 casos no momento da conferência, um a cada ~80 s).

O exporter publica exatamente isso; não estima progresso que o MLflow não registrou.

## Comportamento esperado
Para cada experimento (lote e online), além do que a spec 017 publica:
- `rag_cognus_mlflow_run_running{experiment,run_name}` = 1 e
  `rag_cognus_mlflow_run_elapsed_seconds{experiment,run_name}` = agora − `start_time`, para
  os runs RUNNING (no máximo 5 por experimento, os mais recentes).
- `rag_cognus_mlflow_running_run_metric{experiment,run_name,metric}`: métricas já logadas
  num run RUNNING (hoje, `index_build_seconds`), com o mesmo teto de 100 por run.
- `rag_cognus_mlflow_run_traces{experiment,run_name}`: traces ligados ao run RUNNING (até
  1000); `rag_cognus_mlflow_run_cases{experiment,run_name}`: param `cases`, só se numérico.
  Falha ao buscar traces não derruba a coleta (só omite a série).
- `rag_cognus_mlflow_last_run_info{experiment,run_name,status}` = 1 para o run mais recente
  (por `start_time`), qualquer status.
- `rag_cognus_mlflow_last_ended_timestamp_seconds{experiment,run_name,status}`: `end_time`
  (s) do último run encerrado (FINISHED, FAILED ou KILLED).
- `rag_cognus_mlflow_last_finished_timestamp_seconds{experiment}`: `end_time` (s) do último
  FINISHED (mesmo valor de `last_run_timestamp_seconds`, mantido por compatibilidade).
- `rag_cognus_mlflow_runs_total{experiment,status}` publica 0 para os status conhecidos sem
  runs, para que a série de FAILED exista antes da primeira falha (alerta com `delta`).
- `run_name` normalizado: `[A-Za-z0-9_.:-]`, até 64 caracteres; vazio vira `unknown`.

Dashboard: linha "Avaliação em lote" com variável `experiment`. Alertas em
`infra/grafana/alerts.yaml`, formato de regras do Prometheus (o Grafana Cloud não aceita
provisionamento por arquivo; importa esse YAML pela UI "Import to Grafana-managed rules" ou
pela API `/api/convert/prometheus/config/v1/rules`).

## Critérios de aceite
- **AC-1:** Com um run RUNNING, a coleta publica `run_running` = 1 e `run_elapsed_seconds`
  = relógio − `start_time` (em s) com os labels `experiment` e `run_name`.
- **AC-2:** No máximo `MAX_RUNNING_RUNS` (5) runs RUNNING por experimento, os de
  `start_time` mais recente; `run_name` normalizado (sem espaço/aspas, ≤ 64, vazio →
  `unknown`).
- **AC-3:** Métricas já logadas num run RUNNING aparecem em `running_run_metric`; sem
  métricas, não há série (nada inventado). Runs FINISHED não entram em `running_run_metric`.
- **AC-4:** `run_traces` conta os traces do run RUNNING e `run_cases` vem do param `cases`;
  param ausente/não numérico → sem série; erro no `search_traces` → sem série e `up` 1.
- **AC-5:** `last_run_info` aponta o run mais recente com seu status;
  `last_ended_timestamp_seconds` o último encerrado; `last_finished_timestamp_seconds` o
  último FINISHED.
- **AC-6:** `runs_total` publica 0 para os status conhecidos sem runs.
- **AC-7:** O dashboard tem a linha "Avaliação em lote" com os painéis: em andamento,
  último run concluído, métricas ao longo do tempo, tabela do último run (experimento,
  backend, judge_model) e runs por status; toda query cita só métricas existentes.
- **AC-8:** `infra/grafana/alerts.yaml` é YAML válido no formato de regras do Prometheus,
  sem `limit`, com as regras: MLflow fora, avaliação travada, qualidade baixa, citação
  baixa, run FAILED novo (com `delta`, não `increase`) e API sem dados; toda expressão
  cita só métricas existentes ou `up` de jobs do Alloy.

| AC | Teste |
|---|---|
| AC-1 | `test_mlflow_exporter.py::test_running_run_elapsed` |
| AC-2 | `test_mlflow_exporter.py::test_running_runs_capped_and_named` |
| AC-3 | `test_mlflow_exporter.py::test_running_partial_metrics_only_if_logged` |
| AC-4 | `test_mlflow_exporter.py::test_running_traces_and_cases`, `test_traces_error_keeps_up` |
| AC-5 | `test_mlflow_exporter.py::test_last_run_info_and_timestamps` |
| AC-6 | `test_mlflow_exporter.py::test_runs_total_zero_for_known_statuses` |
| AC-7 | `test_infra_grafana.py::test_dashboard_queries_use_existing_metrics`, `test_dashboard_batch_row` |
| AC-8 | `test_infra_grafana.py::test_alerts_yaml_rules` |

## Decisões
- **Elapsed calculado no exporter** (relógio de parede, cache de 30 s) em vez de só o
  `start_time`: o alerta fica `elapsed > 3600` direto.
- **Traces como progresso:** é o único registro incremental que o `genai.evaluate` faz; o
  painel mostra traces / casos. Se um scorer passar a gravar traces próprios, a razão pode
  passar de 100% (o painel limita em 100%).
- **Run FAILED novo com `delta`:** `runs_total` é gauge (runs podem ser apagados), então
  `increase` trataria uma exclusão como reset e geraria falso positivo. Os zeros da AC-6
  garantem que a série exista antes da primeira falha.
- **Formato dos alertas:** regras do Prometheus, porque o Grafana Cloud não lê arquivos de
  provisionamento e o formato de provisionamento do Grafana exige o UID do datasource da
  stack. O YAML do Prometheus é importado como regras Grafana-managed escolhendo o
  datasource na importação.

## Fora de escopo
- Criar regras, contact points ou dashboards no Grafana Cloud (o usuário importa).
- Métricas por caso e histórico de runs antigos (o histórico vem do próprio Prometheus a
  partir do momento em que o exporter passa a publicar).
