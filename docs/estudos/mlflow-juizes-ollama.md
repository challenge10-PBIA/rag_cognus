# Juízes do MLflow local rodando no Ollama (spec 012)

Material de estudo: como o MLflow 3.18 escolhe o LLM de um juiz, por que o `mlflow-local`
passou a montar um ambiente próprio, e o passo a passo para criar e rodar um juiz na UI com o
`qwen3.5:9b` local. Spec: `specs/012-mlflow-local-endpoint-llm.md` (depende da
`specs/011-mlflow-inputs-juizes.md`).

## 1. O problema em uma frase
Um juiz criado na UI do MLflow (`http://127.0.0.1:5001`) precisa de um LLM. Sem configuração,
o MLflow tenta um provedor de nuvem (OpenAI etc.), não acha chave e falha. Queremos que ele
use o Ollama da própria máquina: sem segredo, sem custo e sem dado saindo do computador.

## 2. Como o MLflow 3.18 chama o LLM de um juiz
O modelo de um juiz é um **URI** no formato `<provedor>:/<modelo>`. Três formas nos
interessam:

| URI | Quem usa | O que o servidor precisa ter |
|---|---|---|
| `gateway:/ollama-qwen` | juiz criado **na UI** e avaliação automática da UI | endpoint `ollama-qwen` criado no AI Gateway |
| `openai:/qwen3.5:9b` | juiz em código (`make_judge`), contrato da spec 011 | `OPENAI_API_BASE` + `OPENAI_API_KEY` no processo |
| `ollama:/qwen3.5:9b` | juiz em código, alternativa | nada (base fixa `http://localhost:11434/v1`) |

### `openai:/` com `OPENAI_API_BASE`
O Ollama expõe uma API compatível com a da OpenAI em `/v1`. Então dá para dizer ao MLflow
"use o provedor OpenAI", mas apontar a base para o Ollama:

- `OPENAI_API_BASE=http://127.0.0.1:11434/v1` → para onde as chamadas vão.
- `OPENAI_API_KEY=ollama` → o provedor `openai` do MLflow **exige** uma chave, mesmo que o
  Ollama a ignore. Qualquer valor serve; `ollama` deixa claro que não é chave de verdade.
- `MLFLOW_GENAI_JUDGE_DEFAULT_MODEL=openai:/qwen3.5:9b` → vira o modelo padrão dos juízes
  prontos (built-in) e dos scorers que não dizem qual modelo usar.

Efeito colateral (desejado aqui): com essas variáveis, **qualquer** `openai:/gpt-…` também vai
para o Ollama e falha com "model not found". Ou seja, nada vaza para a nuvem por engano.

### `ollama:/`
Provedor nativo do MLflow para o Ollama. A base é fixa em `http://localhost:11434/v1` e não
pede chave. Bom para um teste rápido em código; não lê `OLLAMA_BASE_URL` do nosso `.env`.

### `gateway:/`
O AI Gateway é um "cadastro de endpoints" dentro do próprio servidor MLflow. Na UI, o
formulário de juiz pergunta "Select an endpoint to use for this judge" e grava
`model: "gateway:/<endpoint>"`. A UI avisa: *"Automatic evaluation is only available for judges
that use gateway endpoints"*. Por isso o endpoint `ollama-qwen` é o caminho para a UI.

Detalhes que explicam o resto do guia:
- O Gateway guarda os endpoints no banco do servidor, então precisa de backend SQL. O
  `mlflow-local` já usa `sqlite:///.cache/mlflow/mlflow.db`.
- Credenciais de endpoint ficam cifradas no banco com `MLFLOW_CRYPTO_KEK_PASSPHRASE`. Sem ela,
  o MLflow usa uma frase padrão "development only", aceitável só em uso local. O Ollama não
  tem chave, então aqui isso quase não importa.

### Por que as variáveis precisam estar no **servidor**
A avaliação disparada pela UI e os scorers online não rodam no seu terminal nem no navegador:
rodam em **jobs** do `mlflow server`, num subprocesso que herda o `os.environ` do servidor
(`mlflow/server/jobs/utils.py`; a execução de jobs vem ligada por padrão). Exportar
`OPENAI_API_BASE` só no shell do Streamlit ou de um script não ajuda o juiz da UI. Por isso a
mudança foi no comando que **sobe** o servidor.

## 3. O que mudou no código
`src/rag_cognus/cli.py`, função `mlflow_local_env()`, usada pelo `rag-cognus mlflow-local`:

1. Lê o `Settings` do `.env`. Se o `.env` estiver inválido, avisa em uma linha e usa os
   padrões do `Settings` (o MLflow não pode deixar de subir por causa de um `RAG_TOP_K` errado).
2. Pede as variáveis a `evaluation.ui_judge_env(settings)` (spec 011, engenheiro de IA). Ela
   monta `OPENAI_API_BASE` a partir de `OLLAMA_BASE_URL`, com exatamente um `/v1` no fim,
   `OPENAI_API_KEY=ollama` e o URI do juiz a partir de `OLLAMA_JUDGE_MODEL` (vazio = modelo do
   chat).
3. **Só preenche o que falta**: se você já definiu `OPENAI_API_BASE`, `OPENAI_API_KEY` ou
   `MLFLOW_GENAI_JUDGE_DEFAULT_MODEL`, o seu valor vence. Se definiu `OPENAI_BASE_URL` (nome
   novo da mesma base), o `OPENAI_API_BASE` não é criado, para não haver duas bases.
4. Passa esse ambiente ao `subprocess.call(..., env=env)` e imprime uma linha com o juiz e a
   base. **Nunca** imprime o valor de uma chave.

O comando do servidor continua igual: `127.0.0.1`, porta 5001, SQLite, `--serve-artifacts`.
Testes: `tests/test_cli_mlflow_local.py` (subprocess falso, sem rede).

## 4. Passo a passo

### 4.1 Ollama no ar com o modelo
```bash
ollama list                     # precisa mostrar qwen3.5:9b
ollama pull qwen3.5:9b          # só se não aparecer
curl -s http://127.0.0.1:11434/v1/models   # a API compatível com OpenAI responde?
```

### 4.2 Paralelismo: `OLLAMA_NUM_PARALLEL` 1 ou 3
Cada "slot" paralelo do Ollama reserva memória de KV cache do tamanho do contexto.
- **3** no dia a dia com o Hermes (pai + 2 subagentes ao mesmo tempo).
- **1** ao avaliar com juiz: o juiz usa a GPU inteira, não disputa com o Hermes e a latência
  fica estável (as notas e os tempos ficam comparáveis entre runs).

```bash
launchctl setenv OLLAMA_NUM_PARALLEL 1   # antes da avaliação; reinicie o app do Ollama
launchctl setenv OLLAMA_NUM_PARALLEL 3   # depois; reinicie o Ollama de novo
```
No macOS, reiniciar = sair do Ollama pela barra de menus e `open -a Ollama`. No Linux,
`Environment=OLLAMA_NUM_PARALLEL=1` no serviço do systemd. O `launchctl setenv` vale até o
próximo login. Detalhes em `hermes/README.md` ("Alternar o paralelismo do Ollama").

### 4.3 Contexto: `OLLAMA_CONTEXT_LENGTH`
O nosso código envia `num_ctx` em cada chamada (`OLLAMA_NUM_CTX`, padrão 16384). O endpoint
`/v1` usado por `openai:/`, `ollama:/` e pelo Gateway **não** envia `num_ctx`: vale o padrão do
servidor Ollama, que é `OLLAMA_CONTEXT_LENGTH`. Duas consequências:
- Contexto pequeno demais → o Ollama corta o prompt **pelo começo**, que é onde está a pergunta
  do juiz (foi um dos problemas da spec 011).
- Valor diferente do `num_ctx` do chat → o Ollama recarrega o modelo a cada troca entre chat e
  juiz (lento).

Para avaliar, deixe igual ao `OLLAMA_NUM_CTX`:
```bash
launchctl setenv OLLAMA_CONTEXT_LENGTH 16384   # = OLLAMA_NUM_CTX do .env; reinicie o Ollama
```
O perfil Hermes usa 32768 (veja `hermes/install.sh`); volte para ele ao usar o Hermes.

### 4.4 Subir o MLflow
```bash
.venv/bin/rag-cognus mlflow-local
```
Saída esperada (a chave não aparece):
```
MLflow open source em http://127.0.0.1:5001
Juízes da UI: openai:/qwen3.5:9b (base http://127.0.0.1:11434/v1)
```
Opcional: `MLFLOW_CRYPTO_KEK_PASSPHRASE` no `.env` (uma frase sua; não compartilhe).
Conferência: `.venv/bin/rag-cognus mlflow-check` e `curl -s http://127.0.0.1:5001/health`.

### 4.5 Criar o endpoint `ollama-qwen` no AI Gateway
1. Abra `http://127.0.0.1:5001` → **AI Gateway** → novo endpoint.
2. Nome: `ollama-qwen`. Provedor: **Ollama**. Modelo: `qwen3.5:9b`.
3. Base: `http://127.0.0.1:11434/v1`. Se a tela pedir chave, use `ollama`.
4. Teste o endpoint pela própria tela (um "olá" basta).

Por que um nome fixo: o juiz grava `gateway:/ollama-qwen`. Se você trocar o modelo depois,
muda só o endpoint e todos os juízes que o usam acompanham.

### 4.6 Criar um juiz na UI e rodá-lo em traces
1. Gere alguns traces: uma pergunta no chat (Streamlit/API) ou
   `rag-cognus evaluate --generate --limit 3`.
2. No experimento (`rag-cognus` ou `rag-cognus-online`) → **Judges/Scorers** → novo juiz LLM.
3. Instruções em português, curtas, com saída simples (por exemplo, "responda `yes` se a
   resposta só usa o contexto recuperado, senão `no`"). Use `{{ inputs }}`, `{{ outputs }}`.
4. **Endpoint:** `ollama-qwen`. Salve.
5. Rode o juiz em alguns traces e abra um deles: o assessment deve aparecer com nota e
   justificativa.

Para comparar, faça o mesmo com um juiz em código usando `openai:/qwen3.5:9b` (vem das
variáveis do passo 4.4).

### 4.7 Conferir se os inputs chegam ao juiz
Se a justificativa do juiz disser que "não há pergunta" ou "não há contexto", o problema é o
trace, não o LLM. O que o juiz lê de cada span e como verificar está em
[mlflow-traces-juizes.md](mlflow-traces-juizes.md).

## 5. Problemas comuns
| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `A porta 5000 já está em uso` | AirPlay Receiver do macOS | use a 5001 (padrão) |
| Juiz falha com "API key" ausente | servidor subiu sem `OPENAI_API_KEY` (subiu com `mlflow server` direto) | suba com `rag-cognus mlflow-local` |
| "model not found" | `openai:/gpt-…` indo para o Ollama, ou modelo não baixado | use `qwen3.5:9b`; `ollama list` |
| Connection refused em `11434` | Ollama fora do ar | `open -a Ollama`; `curl .../v1/models` |
| Linha "Aviso: .env inválido" | valor errado no `.env` | corrija; o MLflow subiu com os padrões |
| Juiz devolve texto fora do formato | o 9B se perde em instrução longa | instrução curta, saída `yes`/`no` |
| Juiz lento ou fila parada | `OLLAMA_NUM_PARALLEL` alto, Hermes ou chat usando o slot | `OLLAMA_NUM_PARALLEL=1` ao avaliar |
| Justificativa sem a pergunta | contexto pequeno cortou o prompt | `OLLAMA_CONTEXT_LENGTH` = `OLLAMA_NUM_CTX` |
| Tela do Gateway dá erro de import | faltam extras `mlflow[gateway]` | relate ao DevOps (mudança de dependência) |
| Base com `/v1/v1` | `OPENAI_API_BASE` definido à mão errado | apague a variável; o comando monta sozinho |

## 6. Ainda a confirmar (AC-5 da spec 012)
- Se a tela do AI Gateway funciona sem os extras `mlflow[gateway]` instalados.
- Se um juiz da UI **sem** endpoint escolhido cai no `MLFLOW_GENAI_JUDGE_DEFAULT_MODEL`.
- Como desligar o raciocínio do qwen3.5 pelo `/v1` (`reasoning_effort: "none"`?).
