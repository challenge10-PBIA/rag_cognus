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

Em um terminal, inicie o servidor local e mantenha-o aberto:

```bash
rag-cognus mlflow-local
```

Abra `http://127.0.0.1:5000`. Em outro terminal, com o Ollama ativo e os modelos `qwen3.5:9b` e `embeddinggemma:latest` instalados:

```bash
rag-cognus sync-gold
rag-cognus ask "Como organizar uma apresentação clara para meu público?"
rag-cognus evaluate --backend bm25 --k 3
rag-cognus evaluate --backend bm25 --k 5
rag-cognus evaluate --backend dense --k 5
rag-cognus evaluate --generate --limit 2
python scripts/eval_local.py --generate-limit 2 --judge
```

`dense` usa `OllamaEmbeddings` + `InMemoryVectorStore`. `bm25` é a linha de base lexical.
O índice é reconstruído em memória por execução; o custo da construção é registrado
separadamente da latência por pergunta. É um protótipo para o acervo atual, não um
serviço de produção ou índice persistente.

## Suite de avaliações no MLflow local

`python scripts/eval_local.py` executa recuperação k=3/k=5 e duas perguntas com
Qwen; `--judge` adiciona o juiz exploratório. Para somente recuperação, use
`--generate-limit 0`. Para comparar embeddings locais, use `--backend dense`.

O servidor usa `127.0.0.1:5000`; banco e artefatos ficam em `.cache/mlflow/`,
fora do Git. O arquivo `outputs/local_eval_summary.json` guarda os IDs dos runs
locais. O chat e os comandos de avaliação usam esse servidor por padrão.
Para retomar após reiniciar o computador, execute novamente `rag-cognus mlflow-local`.

## Evaluation de contexto e fontes

No MLflow local, a avaliação `local-contexto-fontes-evaluation` mostra indicadores
por pergunta. O comando `rag-cognus context-eval` acrescenta relevância por trecho,
precisão por posição estimada pelo juiz, suficiência, diversidade de fontes,
redundância e uso das fontes na resposta. Precisão e recall humanos só são
calculados com referências revisadas.

```bash
rag-cognus context-eval outputs/ID_RECUPERACAO.json \
  --answers outputs/ID_RESPOSTAS.json --judge --limit 6 --k 5
```

A suite também pode executar essa etapa automaticamente:

```bash
python scripts/eval_local.py --context-eval --judge --context-limit 6
```

Consulte [a metodologia e interpretação](docs/contexto_metricas.md) ou o
[relatório IPYNB](notebooks/05_contexto_fontes_e_correlacao.ipynb).
As tabelas de fontes e correlações ficam nos artefatos locais do run. Correlações
com poucos pares ou sem variação não recebem um número; associações não são causais.

## Chat no navegador

```bash
python -m pip install -e '.[ui]'
streamlit run src/rag_cognus/chat_app.py --server.address 127.0.0.1 --server.port 8501
```

Abra `http://127.0.0.1:8501`. O chat mostra resposta e evidências lado a lado,
com filtro por nicho, escolha de busca e quantidade de trechos. Para testar só a
recuperação, desative **Gerar resposta com Qwen**. O botão **Atualizar Gold**
refaz o snapshot diretamente do Databricks. Cada pergunta é independente;
o histórico visual não é usado como evidência pelo modelo.

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
