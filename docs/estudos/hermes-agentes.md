# Como o Hermes (`ragdev`) organiza os agentes

Guia de estudo do time multiagente no Hermes Agent com o Qwen3.5 9B local (spec 009).

## 1. Peças
| Peça | Onde | Para que serve |
|---|---|---|
| Perfil | `hermes/config.yaml` → `~/.hermes/profiles/ragdev/config.yaml` | Modelo, limites, hooks, MCP |
| Contexto do projeto | `AGENTS.md` | Regras que todo agente (e subagente) lê |
| Skills | `hermes/skills/*/SKILL.md` | Instruções carregadas sob demanda |
| Hooks | `hermes/hooks/*.py` | Barram comandos perigosos, formatam, injetam estado |
| Harness | `hermes/harness/check.py`, `hermes/harness/services.py` | Verificação igual ao CI; status dos serviços |
| Painel | `hermes/monitor/app.py` | Mostra subagentes agrupados por `[papel]` |

O `install.sh` copia o `config.yaml` trocando `__REPO__` pelo caminho do repositório. Por
isso mudanças no `config.yaml` só valem depois de `bash hermes/install.sh`.

## 2. Delegação: o que o `delegate_task` aceita
Na versão instalada (v0.23.1), cada tarefa tem só três campos: `goal`, `context` e `role`
(`leaf` ou `orchestrator`). **Não há** campo para escolher skills ou ferramentas do filho: ele
herda os toolsets do pai (inclusive MCP) e lê `AGENTS.md`.

Consequência de projeto: "papel" é **texto**. O líder cola no `context` o bloco do papel
(da skill `rag-orchestrator`) e a frase "carregue a skill X". O `goal` começa com
`[papel]` porque o painel agrupa por esse prefixo.

## 3. Papéis
| Papel | Skill a carregar | Dono no Claude Code |
|---|---|---|
| `dados` | — (texto do papel) | `engenheiro-dados` |
| `ia` | — (texto do papel; usa `rag-tdd`) | `engenheiro-ia` |
| `devops` | — (texto do papel; usa `rag-harness`) | `engenheiro-devops` |
| `avatar` | `rag-avatar-agent` | `engenheiro-ia` |
| `obs` | `rag-observability-agent` | `engenheiro-devops` + `engenheiro-ia` |

Por que `avatar` e `obs` não viraram agentes novos no Claude Code: os dois agentes do produto
ainda vão chegar de fora do repo. Criar subagentes agora seria duplicar regras; basta estender
o domínio dos engenheiros e manter o contrato nas skills (uma só fonte, lida pelos dois
ambientes).

Por que as skills têm caminhos "a criar": o teste `tests/test_hermes_config.py` confere que
todo caminho citado existe, para o modelo não procurar arquivos fantasmas. O código que ainda
vai chegar fica marcado "a criar" na mesma linha; o teste aceita isso e exige ao menos um
arquivo real como ponto de integração.

## 4. Hooks e o que eles garantem
- `guard.py` (antes de cada ferramenta): bloqueia `git push`, `rm -r` amplo, `databricks://`,
  leitura do `.env`, referências a `$…TOKEN`/`$…SECRET` no terminal e tokens do Grafana Cloud
  (`glsa_…`, `glc_…`) em comandos ou arquivos. O mesmo script roda no Claude Code.
- `post_edit.py`: `ruff --fix` e `ruff format` no `.py` editado.
- `inject_context.py` (antes de cada chamada ao modelo): arquivos alterados, último harness,
  lint pendente e, se houver cache com menos de 5 min, `Serviços: mlflow UP, ollama UP, …`.
  Ele **não faz rede**: roda a cada chamada, inclusive nos subagentes, e precisa ser rápido.

## 5. `services.py`: por que um cache
`python hermes/harness/services.py` faz um GET de 2 s em MLflow (`/health`), Ollama
(`/api/tags`), API (`/v1/health`) e Grafana (`/api/health`, se `GRAFANA_URL` existir) e grava
`.hermes-runs/services.json`. O agente roda quando precisa; o hook só lê o arquivo. Nenhuma
requisição leva token: os endpoints de saúde são públicos.

## 6. Paralelismo do Ollama
`max_concurrent_children: 2` + pai = 3 requisições simultâneas, daí `OLLAMA_NUM_PARALLEL=3`
no dia a dia. Cada slot reserva KV cache do tamanho de `num_ctx`; para avaliação com juiz
(`rag-cognus evaluate`) use 1 slot, para o juiz ter a GPU inteira e não disputar com o
Hermes. Comandos em `hermes/README.md` ("Alternar o paralelismo do Ollama").

## 7. Passo a passo de uma tarefa
1. `python hermes/harness/services.py` (opcional, para saber o que está no ar).
2. `ragdev` na raiz do repo: *"Use a skill rag-orchestrator: …"*.
3. O líder escreve/atualiza a spec, mostra os AC e espera seu ok.
4. Delegação com `goal: "[obs] …"`, `context: "<PAPEL obs> … carregue a skill
   rag-observability-agent"`.
5. Cada filho: teste vermelho → implementação → `python hermes/harness/check.py --changed`.
6. O líder roda `python hermes/harness/check.py` e só diz "pronto" com `HARNESS OK`.
