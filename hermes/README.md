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
launchctl setenv OLLAMA_NUM_PARALLEL 3     # pai + 2 subagentes; reinicie o Ollama
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

Dia a dia com o Hermes: `OLLAMA_NUM_PARALLEL=3` (pai + 2 subagentes). Para avaliação com juiz
(`rag-cognus evaluate`) o ideal é **1**: cada slot reserva KV cache de `num_ctx`, então com 1 o
juiz usa a GPU inteira, não disputa com o Hermes e a latência fica estável.
```bash
launchctl setenv OLLAMA_NUM_PARALLEL 1   # antes da avaliação; reinicie o Ollama
launchctl setenv OLLAMA_NUM_PARALLEL 3   # depois; reinicie o Ollama de novo
```
Reiniciar no macOS: feche o Ollama na barra de menus e abra de novo (ou `pkill ollama` e
`open -a Ollama`). Linux: `Environment=OLLAMA_NUM_PARALLEL=1` no systemd e
`sudo systemctl restart ollama`.

## Ajustes por hardware
| VRAM | `context_length` / `ollama_num_ctx` | `max_concurrent_children` | `OLLAMA_NUM_PARALLEL` |
|---|---|---|---|
| 8 GB | 16384 | 1 | 2 |
| 12–16 GB | 32768 | 2 | 3 |
| 24 GB+ | 65536 | 3 | 4 |
