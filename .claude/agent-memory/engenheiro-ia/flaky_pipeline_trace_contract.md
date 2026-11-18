---
name: flaky-pipeline-trace-contract
description: tests/test_agents.py::test_pipeline_trace_contract falhou uma vez no harness completo e passou isolado e no rerun (2026-11-18)
metadata:
  type: project
---

`test_pipeline_trace_contract` deu `assert False` em uma rodada de `hermes/harness/check.py` e passou
isolado, com o arquivo inteiro e na rodada seguinte do harness (2026-11-18, durante a revisão da spec 016).

**Why:** provável dependência de ordem/estado global do tracing MLflow (último trace ativo).
**How to apply:** se ele falhar no harness, rode de novo antes de investigar o seu diff; se ficar
recorrente, vale abrir uma tarefa para isolar o estado de tracing no teste.
