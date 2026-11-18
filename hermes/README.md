# Hermes Agent no rag_cognus

Ambiente parecido com o Claude Code usando o Hermes Agent + Qwen3.5 9B local.

| Peça | Arquivo | Equivalente no Claude Code |
|---|---|---|
| Contexto do projeto | `AGENTS.md` (raiz) | `CLAUDE.md` |
| Perfil/config | `hermes/config.yaml` → `~/.hermes/profiles/ragdev/` | `settings.json` |
| Skills SDD/TDD/harness/orquestrador | `hermes/skills/*/SKILL.md` | skills / subagentes |
| Hooks | `hermes/hooks/*.py` | hooks |
| Harness de verificação | `hermes/harness/check.py` | — |
| Status dos serviços | `hermes/harness/services.py` → `.hermes-runs/services.json` | — |
| Papéis `[avatar]` / `[obs]` | `hermes/skills/rag-avatar-agent`, `rag-observability-agent` | `engenheiro-ia` / `engenheiro-devops` |
| Grafana Cloud (MCP, só leitura) | `mcp_servers.grafana` no `config.yaml` (desligado) | — |
| Specs | `specs/NNN-slug.md` | — |
| Painel de subagentes | `hermes/monitor/app.py` | visão de agentes |

## Instalar (no computador com o Hermes)
```bash
bash hermes/install.sh
# Ollama (spec 015): veja "Ajustes por hardware"; reinicie o Ollama depois
launchctl setenv OLLAMA_NUM_PARALLEL 1
launchctl setenv OLLAMA_CONTEXT_LENGTH 32768
ragdev doctor
```

## Usar
```bash
# terminal 1 — painel
.venv/bin/streamlit run hermes/monitor/app.py --server.port 8502
# terminal 2 — agente (na raiz do repo)
ragdev                         # ou HERMES_TDD_STRICT=1 ragdev
```
Exemplo de pedido: *"Use a skill rag-orchestrator: quero que o chat mostre o tempo de
resposta de cada pergunta."*

Dentro do Hermes: **Ctrl+T / F6** abre o roster ao vivo dos subagentes; `/agents` lista,
pausa ou encerra. Logs crus: `tail -f ~/.hermes/profiles/ragdev/cache/delegation/live/*/task-*.log`.

## Serviços e Grafana
```bash
python hermes/harness/services.py      # [UP]/[DOWN] MLflow, Ollama, API (e Grafana)
```
O resultado fica em cache por 5 min e o hook `inject_context` mostra `Serviços: …` ao modelo.

Grafana Cloud (`https://estevaomaia.grafana.net`) entra por MCP com o `mcp-grafana` OSS em
stdio (token de service account), **desligado** até você criar o token. O
`mcp_servers.grafana.command` é o wrapper `hermes/mcp/grafana.sh`, que lê do `.env` da raiz do
repo **só** as duas chaves abaixo (sem `source`; o ambiente exportado vence) e chama o
`docker run ... mcp/grafana -t stdio`. Passo a passo em `docs/estudos/hermes-mcp-grafana.md`;
resumo:
```bash
# no .env da raiz do repo (ignorado pelo git; nunca no .env.example):
#   GRAFANA_URL=https://estevaomaia.grafana.net
#   GRAFANA_SERVICE_ACCOUNT_TOKEN=<token>
ragdev config set mcp_servers.grafana.enabled true
ragdev mcp list
```

## Alternar o paralelismo do Ollama
Juízes da UI do MLflow no Ollama (`rag-cognus mlflow-local`, endpoint `ollama-qwen`,
`OLLAMA_CONTEXT_LENGTH`): `docs/estudos/mlflow-juizes-ollama.md`.

Desde a spec 015 o padrão é **1 slot** no dia a dia e na avaliação com juiz
(`rag-cognus evaluate`): o pai espera o filho (`max_concurrent_children: 1`), então não há
pedidos simultâneos, e com 1 slot o juiz usa a GPU inteira. Só suba para 2 se for rodar o
Hermes e o app ao mesmo tempo e conferir com `ollama ps` que a memória cabe.

## Ajustes por hardware
O que trava o 9B num Mac não é a memória, é o **prefill**: o M4 lê ~110–150 tokens/s, e o
prompt fixo do Hermes tem ~15 mil tokens (~20 mil antes da spec 015). Cache frio = 1,5–2,5 min
antes do 1º token. Por isso: prompt enxuto, um só `num_ctx` para todos (sem recarregar o
modelo), modelo sempre carregado e raciocínio desligado. Medidas e contas em
[docs/estudos/hermes-desempenho.md](../docs/estudos/hermes-desempenho.md).

Memória do KV cache do `qwen3.5:9b` (só 8 das 32 camadas têm atenção; 32 KB/token em f16,
16 KB/token em `q8_0`), multiplicada por `OLLAMA_NUM_PARALLEL`:

| Memória unificada / VRAM | `context_length` = `ollama_num_ctx` = `OLLAMA_NUM_CTX` | `max_concurrent_children` | `OLLAMA_NUM_PARALLEL` | KV por slot (f16 / q8_0) |
|---|---|---|---|---|
| 8 GB | 16384 (o prompt do Hermes mal cabe: desligue mais toolsets) | 1 | 1 | 0,5 / 0,25 GB |
| 16 GB | 32768 | 1 | 1 | 1 / 0,5 GB |
| **24 GB (Mac M4, padrão)** | **32768** | **1** | **1** | **1 / 0,5 GB** |
| 32 GB+ ou GPU dedicada | 65536 | 1–2 | 2 | 2 / 1 GB |

Total aproximado = pesos (6,6 GB com o projetor de visão) + KV × slots. Medido com
`ollama ps`: 6,6 GB em 32768 e 7,6 GB em 64000 (1 slot). Num Mac lembre que a mesma memória
atende o sistema, o Docker (a VM reserva até o limite configurado no Docker Desktop) e o app.

Variáveis do Ollama (valem para todo pedido que não manda `num_ctx`, inclusive o `/v1` que o
Hermes usa: o `/v1` do Ollama 0.32 ignora o `options.num_ctx`, então o contexto efetivo do
Hermes é o `OLLAMA_CONTEXT_LENGTH`):

| Variável | Valor | Por quê |
|---|---|---|
| `OLLAMA_NUM_PARALLEL=1` | 1 | um slot com o prompt em cache; sem disputa de GPU |
| `OLLAMA_CONTEXT_LENGTH=32768` | igual ao perfil | o mesmo `num_ctx` em tudo = o modelo não recarrega |
| `OLLAMA_FLASH_ATTENTION=1` | 1 | atenção sem matriz N×N; exigido para quantizar o KV |
| `OLLAMA_KV_CACHE_TYPE=q8_0` | `q8_0` | KV com metade da memória, perda de qualidade desprezível |
| `OLLAMA_KEEP_ALIVE=30m` | 30m | o padrão 5m descarrega o modelo entre pedidos e a próxima chamada volta fria |

```bash
launchctl setenv OLLAMA_NUM_PARALLEL 1
launchctl setenv OLLAMA_CONTEXT_LENGTH 32768
launchctl setenv OLLAMA_FLASH_ATTENTION 1
launchctl setenv OLLAMA_KV_CACHE_TYPE q8_0
launchctl setenv OLLAMA_KEEP_ALIVE 30m
osascript -e 'quit app "Ollama"' && sleep 3 && open -a Ollama   # reinicia o Ollama
grep "server config" ~/.ollama/logs/server.log | tail -1        # confere os valores lidos
```
No app do Ollama, em **Settings**, deixe **Context length** em 32k. Em 2026-11-18 o servidor
rodava com `OLLAMA_CONTEXT_LENGTH:131072` e `OLLAMA_NUM_PARALLEL:1` sem nenhum dos dois no
`launchctl` com esses valores: confira sempre a linha `server config` depois de reiniciar.
O `launchctl setenv` vale até o
próximo login; para fixar, repita os comandos num LaunchAgent ou no seu `~/.zprofile`.
Linux: as mesmas variáveis como `Environment=` no systemd do ollama e
`sudo systemctl restart ollama`. No `.env` do app use `OLLAMA_NUM_CTX=32768` (o mesmo valor).
