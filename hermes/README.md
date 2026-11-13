# Hermes Agent no rag_cognus

Ambiente parecido com o Claude Code usando o Hermes Agent + Qwen3.5 9B local.

| Peça | Arquivo | Equivalente no Claude Code |
|---|---|---|
| Contexto do projeto | `AGENTS.md` (raiz) | `CLAUDE.md` |
| Perfil/config | `hermes/config.yaml` → `~/.hermes/profiles/ragdev/` | `settings.json` |
| Skills SDD/TDD/harness/orquestrador | `hermes/skills/*/SKILL.md` | skills / subagentes |
| Hooks | `hermes/hooks/*.py` | hooks |
| Harness de verificação | `hermes/harness/check.py` | — |
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

## Ajustes por hardware
| VRAM | `context_length` / `ollama_num_ctx` | `max_concurrent_children` | `OLLAMA_NUM_PARALLEL` |
|---|---|---|---|
| 8 GB | 16384 | 1 | 2 |
| 12–16 GB | 32768 | 2 | 3 |
| 24 GB+ | 65536 | 3 | 4 |
