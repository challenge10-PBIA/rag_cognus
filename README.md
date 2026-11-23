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

**Juízes do MLflow no Ollama.** O `mlflow-local` já sobe o servidor com os juízes apontados
para o Ollama local (`OPENAI_API_BASE=<OLLAMA_BASE_URL>/v1`, `OPENAI_API_KEY=ollama` e
`MLFLOW_GENAI_JUDGE_DEFAULT_MODEL=openai:/<OLLAMA_JUDGE_MODEL ou modelo do chat>`); valores que você já exportou vencem e
nenhuma chave é impressa. Para um juiz criado na UI:

1. Em `http://127.0.0.1:5001` → **AI Gateway**, crie o endpoint `ollama-qwen`: provedor
   **Ollama**, modelo `qwen3.5:9b`, base `http://127.0.0.1:11434/v1` (se pedir chave, `ollama`).
2. No experimento → **Judges/Scorers** → novo juiz LLM com instrução curta (ex.: saída
   `yes`/`no`) e endpoint `ollama-qwen`; rode-o em alguns traces.
3. Durante a avaliação deixe o Ollama com um slot, para o juiz ter a GPU inteira:

```bash
launchctl setenv OLLAMA_NUM_PARALLEL 1   # já é o padrão com o Hermes (spec 015)
```

Passo a passo, `OLLAMA_CONTEXT_LENGTH` e problemas comuns em
[docs/estudos/mlflow-juizes-ollama.md](docs/estudos/mlflow-juizes-ollama.md); o que o juiz lê de
cada trace em [docs/estudos/mlflow-traces-juizes.md](docs/estudos/mlflow-traces-juizes.md).

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
rag-cognus api                    # http://127.0.0.1:8001 · OpenAPI em /docs
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

### Avaliação online

Cada `POST /v1/ask` responde assim que o RAG termina; o juiz avalia a resposta em segundo
plano no Ollama local e o resultado sai em `GET /v1/ask/{ask_id}/evaluation`
([specs/004-avaliacao-rag-local.md](specs/004-avaliacao-rag-local.md)).

```bash
rag-cognus mlflow-local   # terminal 1: MLflow em http://127.0.0.1:5001
rag-cognus mlflow-check   # confere o servidor e cria o experimento online se faltar
rag-cognus api            # terminal 2
```

- No MLflow, abra o experimento `rag-cognus-online` (`MLFLOW_ONLINE_EXPERIMENT`): um run
  `ask-<id>` por pergunta, com as notas do juiz, `quality_score` e `latency_seconds`.
- Custo: o juiz ocupa o Ollama por dezenas de segundos depois de cada resposta, e a
  próxima pergunta espera na fila. Juiz diferente do chat (`OLLAMA_JUDGE_MODEL`, menos viés
  de autoavaliação) recarrega o modelo e soma latência.
- `RAG_ONLINE_EVAL=false` desliga a avaliação. Sem MLflow no ar a API segue funcionando; a
  avaliação só não é registrada (`mlflow_logged=false`).

### Voz do mascote

O avatar fala com voz híbrida ([specs/027-voz-do-avatar.md](specs/027-voz-do-avatar.md)):

- **Piper (padrão, local, offline):** pacote [`piper-tts`](https://github.com/OHF-Voice/piper1-gpl)
  (licença **GPL-3.0-or-later**), instalado pelo extra opcional `voice`. Voz padrão
  `pt_BR-faber-medium`; `pt_BR-cadu-medium` e `pt_BR-jeff-medium` também servem. As vozes
  pt_BR foram treinadas com dados CC0 ([OHF-Voice/voice-datasets](https://github.com/OHF-Voice/voice-datasets)).
- **ElevenLabs (opcional, só na apresentação):** usado quando há `ELEVENLABS_API_KEY`. O
  plano gratuito é para uso não comercial e exige atribuição à ElevenLabs.

```bash
python -m pip install -e '.[voice]'   # ~33 MB + onnxruntime
rag-cognus voice-download             # baixa PIPER_VOICE para PIPER_DATA_DIR (~63 MB)
rag-cognus voice-download --list      # vozes pt_BR disponíveis
rag-cognus voice-download --voice pt_BR-cadu-medium --voice pt_BR-jeff-medium
```

Se a voz já estiver baixada, o comando não baixa de novo (`--force` força) e, no fim, mostra
qual provedor está ativo. Sem o extra instalado, sai com código 1 e o comando para instalar.

O modo apresentação ([specs/028-modo-apresentacao-narrado.md](specs/028-modo-apresentacao-narrado.md))
toca áudios pré-gerados, sem rede no dia. Revise o roteiro antes: com ElevenLabs, cada
caractere gasta crédito.

```bash
rag-cognus voice-pregen               # lê ../frontend_UI/public/presentation/roteiro.json
rag-cognus voice-pregen --only abertura --only encerramento   # só alguns passos
rag-cognus voice-pregen --force --yes # refaz tudo sem perguntar
```

O comando mostra os passos, o total de caracteres e o provedor e pede `Gerar? [s/N]`. Grava
`<id>.mp3` (ElevenLabs) ou `<id>.wav` (Piper) e um `manifest.json` com o `sha256` de
provedor + voz + texto. Na próxima vez, pula os passos que não mudaram. Se algum passo
falhar, lista os que faltaram, mantém os já gerados e sai com código ≠ 0.

Variáveis (`TTS_PROVIDER`, `PIPER_VOICE`, `PIPER_DATA_DIR`, `PIPER_LENGTH_SCALE`,
`ELEVENLABS_*`, `TTS_TIMEOUT`, `VOICE_CACHE_DIR`) em `.env.example`. O CI não instala o
extra `voice`: os testes usam fakes e o Piper é importado só quando a voz é gerada.

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

## Configuração do LLM por papel

Cada chamada ao Ollama tem um papel: `generator` (RAG, síntese, adaptação), `judge` (juízes) e
`fast` (decomposição do tema, pleonasmos). Sem variável nova no `.env`, o payload é o de antes;
opções vazias não são enviadas e vale o Modelfile. As principais
([specs/010-config-llm.md](specs/010-config-llm.md)):

| Variável | Padrão | Para quê |
|---|---|---|
| `OLLAMA_TEMPERATURE` (`_JUDGE_`, `_FAST_`) | `0` | respostas factuais e notas reprodutíveis |
| `OLLAMA_SEED` | vazio | reprodutível se alguém subir a temperatura (ex.: `42`) |
| `OLLAMA_PRESENCE_PENALTY` (`OLLAMA_JUDGE_PRESENCE_PENALTY`) | vazio (Modelfile 1.5) | `0` não pune o JSON que repete IDs |
| `OLLAMA_REPEAT_PENALTY` | vazio | `1.0` não pune a cópia literal do trecho |
| `OLLAMA_THINK` / `OLLAMA_JUDGE_THINK` | `false` | o raciocínio do Qwen triplica a latência |
| `OLLAMA_GENERATOR_NUM_PREDICT`, `OLLAMA_JUDGE_NUM_PREDICT`, `OLLAMA_FAST_NUM_PREDICT` | vazio (padrão da chamada) | teto de tokens; JSON cortado vira erro |

Adote os valores sugeridos só depois de comparar dois runs no MLflow (parâmetros
`generator_options` e `judge_options`). Detalhes em
[docs/estudos/llm-config.md](docs/estudos/llm-config.md).

## Hermes (time de agentes local)

O perfil Hermes `ragdev` roda um time de agentes com o Qwen3.5 9B local, com os mesmos hooks e
harness do Claude Code ([specs/009-hermes-agentes-avatar-observabilidade.md](specs/009-hermes-agentes-avatar-observabilidade.md),
[hermes/README.md](hermes/README.md)).

Pré-requisitos: Hermes Agent instalado, Ollama com `qwen3.5:9b` e Docker (só para o Grafana).

```bash
bash hermes/install.sh                     # copia hermes/config.yaml para o perfil ragdev
launchctl setenv OLLAMA_NUM_PARALLEL 1     # veja "Ajustes por hardware"; reinicie o Ollama
ragdev doctor
python hermes/harness/services.py          # [UP]/[DOWN] MLflow, Ollama, API e Grafana
```

```bash
# terminal 1 — painel dos subagentes
.venv/bin/streamlit run hermes/monitor/app.py --server.port 8502
# terminal 2 — na raiz do repo
ragdev
```

Exemplo de pedido: *"Use a skill rag-orchestrator: quero que o chat mostre o tempo de resposta
de cada pergunta."*

| Papel | Skill | Função |
|---|---|---|
| `dados` | — | Gold, documentos e datasets |
| `ia` | `rag-tdd` | recuperação, geração, juízes, métricas |
| `devops` | `rag-harness` | CI, dependências, CLI, harness |
| `avatar` | `rag-avatar-agent` | agente de comunicação via avatar |
| `obs` | `rag-observability-agent` | serviços, métricas e Grafana |

As skills de `avatar` e `obs` já estão prontas; o código dos agentes ainda vai entrar em
`src/rag_cognus/agents/avatar.py` e `src/rag_cognus/agents/observability.py`.

| Arquivo | Papel |
|---|---|
| `hermes/harness/check.py` | lint + format + testes, igual ao CI |
| `hermes/harness/services.py` | status dos serviços, cache em `.hermes-runs/services.json` |
| `hermes/mcp/grafana.sh` | wrapper do `mcp-grafana`: lê só as chaves do Grafana do `.env` |

### Ajustes por hardware

No Mac o gargalo do 9B é o **prefill** (~110–150 tokens/s no M4): o prompt fixo do Hermes tem
~15 mil tokens, e cada cache frio custa 1,5–2,5 min antes do 1º token. O perfil usa 32768 de
contexto, raciocínio desligado, um subagente por vez e só os toolsets do projeto
([specs/015-hermes-desempenho.md](specs/015-hermes-desempenho.md)). KV cache do
`qwen3.5:9b`: 32 KB/token em f16 (16 KB em `q8_0`) por slot, ou seja, `num_ctx` ×
`OLLAMA_NUM_PARALLEL` × 32 KB.

| Memória | `num_ctx` (Hermes = app = Ollama) | `max_concurrent_children` | `OLLAMA_NUM_PARALLEL` | KV total (f16 / q8_0) |
|---|---|---|---|---|
| 8 GB | 16384 | 1 | 1 | 0,5 / 0,25 GB |
| 16–24 GB (Mac M4 24 GB) | **32768** | **1** | **1** | 1 / 0,5 GB |
| 32 GB+ | 65536 | 1–2 | 2 | 4 / 2 GB |

```bash
launchctl setenv OLLAMA_NUM_PARALLEL 1
launchctl setenv OLLAMA_CONTEXT_LENGTH 32768     # mesmo valor do perfil e do OLLAMA_NUM_CTX
launchctl setenv OLLAMA_FLASH_ATTENTION 1
launchctl setenv OLLAMA_KV_CACHE_TYPE q8_0
launchctl setenv OLLAMA_KEEP_ALIVE 30m           # o padrão 5m descarrega o modelo
osascript -e 'quit app "Ollama"' && sleep 3 && open -a Ollama
grep "server config" ~/.ollama/logs/server.log | tail -1
```

Equivalentes no ambiente: `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`. No app do
Ollama (Settings) deixe Context length em 32k e, no `.env`, `OLLAMA_NUM_CTX=32768`. O porquê
de cada ajuste: [docs/estudos/hermes-desempenho.md](docs/estudos/hermes-desempenho.md).

### Grafana Cloud via MCP

A stack é **https://estevaomaia.grafana.net**, acessada pelo `mcp-grafana` OSS (stdio, Docker)
com token de service account com papel **Viewer** (começa com `glsa_`). O token vai no `.env`
da raiz, que é a fonte principal e é ignorado pelo git; **nunca** no `.env.example`. Edite o
`.env` num editor (não use `echo`) e rode `chmod 600 .env`:

```
GRAFANA_URL=https://estevaomaia.grafana.net
GRAFANA_SERVICE_ACCOUNT_TOKEN=<cole o token aqui>
```

```bash
ragdev config set mcp_servers.grafana.enabled true
ragdev mcp list                            # o servidor grafana conecta e lista as ferramentas
```

Rodar `bash hermes/install.sh` de novo volta `enabled` para `false`. Passo a passo em
[docs/estudos/hermes-mcp-grafana.md](docs/estudos/hermes-mcp-grafana.md).

### Métricas no Grafana Cloud (Prometheus + Alloy)

A API expõe `GET /metrics` (latência por rota, `/v1/ask`, notas do juiz online; spec 016) e
`rag-cognus mlflow-exporter` publica o último run de cada experimento do MLflow em
`127.0.0.1:9105/metrics` (spec 017). Um Grafana Alloy em Docker faz o scrape e envia ao
Grafana Cloud por remote write.

```bash
# .env: GRAFANA_PROM_REMOTE_WRITE_URL, GRAFANA_PROM_USER, GRAFANA_CLOUD_ACCESS_TOKEN
rag-cognus mlflow-local                                # terminal 1
rag-cognus api                                         # terminal 2
rag-cognus mlflow-exporter                             # terminal 3
docker compose --env-file .env -f infra/alloy/docker-compose.yml up -d  # Alloy, UI :12346
```

Depois importe `infra/grafana/rag-cognus-dashboard.json` no Grafana Cloud. A linha
"Avaliação em lote" acompanha o `rag-cognus evaluate` em andamento (tempo, progresso, último
run) e `infra/grafana/alerts.yaml` traz os alertas (MLflow fora, avaliação travada, qualidade
e citação baixas, run FAILED, API sem dados; spec 021). Passo a passo e problemas comuns em
[docs/estudos/mlflow-grafana.md](docs/estudos/mlflow-grafana.md).

## Documentação de estudo

O porquê de cada decisão (LLM por papel, juízes do MLflow, Hermes, Grafana, agentes de avatar
e observabilidade) está em [docs/estudos/README.md](docs/estudos/README.md).

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
