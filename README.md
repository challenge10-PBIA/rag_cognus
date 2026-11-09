# Cognus — RAG e avaliações

Projeto pequeno para consumir **`cognus.gold.vw_rag_conhecimento`**, recuperar evidências
com LangChain e gerar respostas pelo **Qwen3.5 9B no Ollama**. O MLflow registra
perguntas, trechos recuperados, citações, respostas, latência e configuração.

A Gold já contém os trechos: o projeto não reingere documentos nem os divide novamente.

## Começar localmente

```bash
git clone https://github.com/challenge10-PBIA/rag_cognus.git
cd rag_cognus
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
```

No `.env`, preencha `DATABRICKS_WAREHOUSE_ID`. Autentique por OAuth no perfil
`projeto`, usando a CLI Databricks. Se a CLI estiver na pasta pessoal, use
`$HOME/.local/bin/databricks`. Senhas e tokens não fazem parte do repositório.

Com o Ollama ativo e os modelos `qwen3.5:9b` e `embeddinggemma:latest` instalados:

```bash
rag-cognus sync-gold
rag-cognus ask "Como organizar uma apresentação clara para meu público?"
rag-cognus evaluate --backend bm25 --k 3
rag-cognus evaluate --backend bm25 --k 5
rag-cognus evaluate --backend dense --k 5
rag-cognus evaluate --generate --limit 2
mlflow ui --backend-store-uri sqlite:///mlflow.db
```

`dense` usa `OllamaEmbeddings` + `InMemoryVectorStore`. `bm25` é a linha de base lexical.
O índice é reconstruído em memória por execução; o custo da construção é registrado
separadamente da latência por pergunta. É um protótipo para o acervo atual, não um
serviço de produção ou índice persistente.

## No Databricks

Abra [01_databricks_avaliacao.ipynb](notebooks/01_databricks_avaliacao.ipynb) no Git folder.
Ele lê a Gold com Spark e registra a comparação BM25 k=3/k=5 no MLflow do Workspace.
O notebook [02_local_qwen.ipynb](notebooks/02_local_qwen.ipynb) executa a geração local.

**O `localhost` do Databricks não aponta para o seu Mac.** Para gerar no cluster,
seria necessário um endpoint do modelo acessível ao cluster. Esta versão mantém
o Qwen no Mac e permite registrar seus resultados no mesmo MLflow do Databricks:

```bash
export MLFLOW_TRACKING_URI=databricks://projeto
export MLFLOW_EXPERIMENT_NAME=/Users/SEU_USUARIO/rag_cognus_avaliacoes
rag-cognus evaluate --generate --limit 2
```

A cópia de demonstração instalada no Workspace e o clone Git são independentes.
Para acompanhar alterações do GitHub, use o Git folder do repositório.

## Como saber se está acertando?

Não há um percentual único de “assertividade”. Avaliamos separadamente:

- **Recuperação:** Precision@k, Recall@k, Hit@k e MRR@k, apenas com referências revisadas.
- **Resposta:** integridade das citações, abstenção esperada e revisão do apoio nas fontes.
- **Operação:** erros, latência por pergunta e tempo para construir o índice.

As 14 perguntas iniciais são rascunhos. O notebook
[03_revisar_referencias.ipynb](notebooks/03_revisar_referencias.ipynb) ajuda a anotar
`relevant_chunk_ids`, fatos esperados e abstenções. Só depois marque
`label_status=human_verified`. Referências de outro snapshot são rejeitadas.

`niche_metadata_precision_proxy` verifica os rótulos da própria Gold: **não é acurácia**.
`citation_integrity` confirma que IDs citados foram recuperados: **não prova apoio factual**.
Consulte [o método de avaliação](docs/avaliacao.md) antes de interpretar os resultados.

Opcionalmente, `rag-cognus judge outputs/ID_DO_RUN.json` executa uma avaliação
exploratória de groundedness com `mlflow.genai.evaluate` e o Qwen como juiz.
O mesmo modelo gerando e julgando tem viés; não substitui avaliação independente.
A correção contra fatos esperados só é julgada quando as referências estão revisadas.

O método e os resultados iniciais também estão em
[04_metodologia_avaliacao.ipynb](notebooks/04_metodologia_avaliacao.ipynb).

## Testes e dados

```bash
pytest -q
ruff check src tests scripts
ruff format --check src tests scripts
```

Os testes usam textos sintéticos e não exigem Databricks ou Ollama. O GitHub Actions
executa os mesmos checks. O snapshot da Gold, embeddings, credenciais, banco local
MLflow e respostas ficam fora do Git. `requirements-tested.txt` registra as versões
do ambiente local testado (Python 3.14); o `pyproject.toml` permite resolução no runtime
Databricks/Python 3.12. Essa instalação remota é verificada no notebook.
