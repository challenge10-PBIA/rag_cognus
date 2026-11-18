---
name: mlflow-juizes-ollama
description: como os juízes do MLflow 3.18 leem traces e chegam ao Ollama (URIs openai:/ e ollama:/, litellm ausente)
metadata:
  type: project
---
Verificado em 2026-11-18 (mlflow 3.18.0, Ollama 0.32.0). Specs 010, 011 e 012 em `specs/`.
- O URI `openai:/<modelo>` usa o GatewayAdapter, sem litellm (que não está instalado). Exige
  `OPENAI_API_KEY` (qualquer valor) e `OPENAI_API_BASE=http://127.0.0.1:11434/v1`.
- O URI `ollama:/<modelo>` fica fixo em `localhost:11434/v1`.
- O modelo padrão dos juízes da UI vem de `MLFLOW_GENAI_JUDGE_DEFAULT_MODEL`.
- Os juízes leem `inputs` e `outputs` do span raiz e o contexto só de spans RETRIEVER de topo
  (`page_content`, `content` ou `text`, mais `metadata.doc_uri`). `{{ expectations }}`
  exige assessments HUMAN.
- O Modelfile do `qwen3.5:9b` traz `presence_penalty 1.5`, que o ChatOllama não expõe.
- `parse_outputs_to_str` faz `json.dumps` do dict de saída com escape ASCII (`ó` vira
  `ó`). Nos testes, decodifique o JSON antes de comparar o `response`.
- `mlflow.genai.evaluate` envolve o `predict_fn` com `mlflow.trace` só quando ele não abre
  nenhum span. Um pipeline fake sem trace ganha um span raiz `predict`.
- A coluna `tags` do dataset vira tag do trace, mas só depois dos scorers, que não a veem.

**Why:** levou bastante leitura de código para confirmar; a memória do modelo divergia.
**How to apply:** antes de mexer em trace ou juiz, confira se a versão do MLflow mudou
(`mlflow.__version__`) e releia `genai/utils/trace_utils.py` se mudou.
