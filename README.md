# Cognus — RAG e avaliações

Projeto pequeno para consumir **`cognus.gold.vw_rag_conhecimento`**, recuperar evidências
com LangChain e gerar respostas pelo **Qwen3.5 9B no Ollama**. Os resultados ficam no
**MLflow open source local**: traces, notas por pergunta e médias por avaliação.

O Databricks é usado só para ler a Gold (`sync-gold`). O tracking nunca vai para o
MLflow do Databricks: URIs `databricks://` são recusadas.

## Começar localmente

```bash
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -e '.[dev,ui,audio]'
cp .env.example .env
```

> Importante: o comando de instalação deve ser executado com o venv do projeto ativo. Se o
> `streamlit` ou o `faster-whisper` estiverem em outro ambiente, a feature de áudio não aparece.

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

## API do front web

O app web (repo [`frontend_UI`](https://github.com/challenge10-PBIA/frontend_UI)) usa a API
local deste repositório. Ela analisa sessões de fala gravadas, guarda o progresso em SQLite
(`.cache/app/`) e expõe RAG e agentes. Especificação em
[specs/002-api-sessoes-progresso.md](specs/002-api-sessoes-progresso.md); plano de produto em
[docs/plano-frontend.md](docs/plano-frontend.md).

```bash
python -m pip install -e '.[api,audio]'
rag-cognus api                    # http://127.0.0.1:8000 · OpenAPI em /docs
```

| Pilar da sessão | Medida | Nota 100 quando |
|---|---|---|
| Ritmo & Cadência | palavras/min (sem vícios), timestamps do Whisper | 120–160 ppm |
| Pausas Conscientes | intervalos de 0,4–2 s; silêncios > 3 s penalizam | 3–8 pausas/min |
| Vícios Vocais | éé/eh, hã, hum, "tipo", "né" | nenhum vício |
| Clareza da Mensagem | legibilidade (Flesch PT) da transcrição | texto fácil de seguir |

O índice da sessão é a média dos quatro pilares; números nunca vêm do LLM. Ansiedade é
autoavaliação do usuário (1–5), não medida. O Whisper tende a apagar hesitações: a
transcrição usa um prompt com vícios para registrá-las, mas valide com gravações reais.

## Agentes especializados

Dois agentes locais (Qwen no Ollama) apoiam o treino de apresentação. Cada execução vira um
trace `AGENT` no MLflow (tag `agent=evidence|communication|pipeline`); com **Avaliar
respostas** ligado, as notas do juiz entram no trace. Especificação em
[specs/001-agentes-especializados.md](specs/001-agentes-especializados.md).

| Agente | Entrada | Saída |
|---|---|---|
| **Evidências** | Tema (pode ser composto) | Subperguntas, afirmações com `chunk_id`, conflitos, lacunas e confiança |
| **Comunicação** | Texto digitado, fala gravada ou síntese + público, contexto, minutos e tom | Texto adaptado, mudanças, dicas de ensaio, tempo estimado e legibilidade |

No app, use a aba **🧠 Agentes** (o botão *Adaptar esta síntese* leva o resultado de um
agente ao outro). Na CLI:

```bash
rag-cognus synthesize "Como reduzir a ansiedade e aquecer a voz antes de um pitch?" --judge
rag-cognus adapt --file roteiro.txt --audience executivo --context pitch --minutes 2
rag-cognus adapt --topic "Escuta ativa em reuniões" --audience estudante --context aula
```

Temas compostos são divididos pelo modelo leve (`OLLAMA_FAST_MODEL`, ex.: `qwen3.5:4b`);
a síntese e a adaptação usam `OLLAMA_CHAT_MODEL`. Mantenha o mesmo `OLLAMA_NUM_CTX` para todos
os usos do modelo: valores diferentes fazem o Ollama recarregá-lo a cada troca.

**Pergunta por voz:** na aba Conversa, grave a pergunta pelo microfone do navegador.
O áudio é transcrito localmente pelo Whisper (`faster-whisper`, modelo em `WHISPER_MODEL`)
e segue o mesmo caminho da pergunta digitada; no MLflow o trace recebe `input_mode=voice`.
Nada de áudio sai da máquina. Sem o extra `audio` instalado, o app funciona só com texto.

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
