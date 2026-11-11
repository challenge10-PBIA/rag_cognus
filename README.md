# Cognus — RAG e avaliações

Projeto pequeno para consumir **`cognus.gold.vw_rag_conhecimento`**, recuperar evidências
com LangChain e gerar respostas pelo **Qwen3.5 9B no Ollama**. Os resultados ficam no
**MLflow open source local**: traces, notas por pergunta e médias por avaliação.

O Databricks é usado só para ler a Gold (`sync-gold`). O tracking nunca vai para o
MLflow do Databricks: URIs `databricks://` são recusadas.

## Começar localmente

```bash
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -e '.[dev,ui]'
cp .env.example .env
```

No `.env`, preencha `DATABRICKS_WAREHOUSE_ID` e escolha como conectar ao Databricks:

- **Token:** `DATABRICKS_HOST` + `DATABRICKS_TOKEN`. Se os dois estiverem preenchidos,
  o perfil é ignorado.
- **Perfil OAuth:** deixe host/token vazios, defina `DATABRICKS_CONFIG_PROFILE` e rode
  `databricks auth login --profile <nome>`.

O `.env` está no `.gitignore`; nunca coloque o token no `.env.example`.

**1. MLflow local** (deixe aberto em um terminal):

```bash
rag-cognus mlflow-local          # http://127.0.0.1:5001
```

> No macOS a porta 5000 é ocupada pelo AirPlay Receiver, por isso usamos a 5001.
> Se o seu `.env` antigo tiver `MLFLOW_TRACKING_URI=http://127.0.0.1:5000` ou
> `databricks://...`, troque para `http://127.0.0.1:5001`.

**2. Base e perguntas** (com o Ollama ativo e `qwen3.5:9b` / `embeddinggemma:latest`):

```bash
rag-cognus sync-gold
rag-cognus ask "Como organizar uma apresentação clara?" --judge
rag-cognus evaluate --generate --judge --limit 5
```

**3. Chat com métricas:**

```bash
streamlit run src/rag_cognus/chat_app.py --server.address 127.0.0.1 --server.port 8501
```

## Métricas

| Tipo | Métricas | Quando |
|---|---|---|
| Qualidade da resposta (juiz, 1–5) | `context_relevance`, `groundedness`, `answer_relevance`, `accuracy`, `professionalism`, `quality_score` | `--generate --judge` ou **Avaliar respostas** no chat |
| Recuperação | `precision_at_k`, `recall_at_k`, `hit_at_k`, `mrr_at_k` | Só com referências `human_verified` |
| Citações | `citation_integrity`, `abstention_agreement`, `niche_metadata_precision_proxy` | Sempre que aplicável |
| Operação | `latency_seconds`, `error`, `index_build_seconds` | Sempre |

No MLflow, abra o experimento `rag-cognus`: cada run mostra as médias (`accuracy/mean`…)
e, na aba de traces/avaliações, cada pergunta com a nota e o motivo dado pelo juiz.
Use **Chart view** para comparar runs. Detalhes em [docs/avaliacao.md](docs/avaliacao.md).

O juiz padrão é o próprio Qwen (viés de autoavaliação). Para um juiz independente,
defina `OLLAMA_JUDGE_MODEL` no `.env`.

## Chat no navegador

- **Conversa:** chat em largura total, com filtro por nicho, BM25 ou embeddings e
  quantidade de trechos. Com **Avaliar respostas**, cada resposta mostra as cinco notas
  e os motivos; as notas também vão para o trace no MLflow.
- **Evidências:** escolha uma pergunta da conversa (a mais recente aparece primeiro) e veja
  a resposta, os trechos recuperados (citados marcados), público, nichos e link da fonte.
  **Só os citados** filtra os trechos usados na resposta.
- **Métricas:** médias e gráfico das respostas da conversa atual; para avaliações
  registradas no MLflow, médias com variação em relação à anterior, evolução entre
  avaliações e mapa de calor das notas por pergunta.
- A barra lateral mostra se Ollama e MLflow estão no ar.

Cada pergunta é independente; o histórico da tela não é usado como evidência.
Para revisar referências humanas use [03_revisar_referencias.ipynb](notebooks/03_revisar_referencias.ipynb).

## Testes e dados

```bash
pytest -q
ruff check src tests
ruff format --check src tests
```

Os testes usam textos sintéticos e não exigem Databricks, Ollama ou servidor MLflow. O GitHub Actions
executa os mesmos checks. O snapshot da Gold, embeddings, credenciais, banco local
MLflow e respostas ficam fora do Git. `requirements-tested.txt` registra as versões
do ambiente local testado (Python 3.14).
