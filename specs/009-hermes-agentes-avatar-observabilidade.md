# 009 — Hermes pronto para os agentes de avatar e de observabilidade

- **Status:** implementado (2026-11-18)
- **Dono:** engenheiro-devops (Hermes, `.claude/`); consulta engenheiro-ia (contrato dos agentes)
- **Módulos:** `hermes/config.yaml`, `hermes/install.sh`, `hermes/README.md`,
  `hermes/skills/rag-orchestrator/SKILL.md`, novas `hermes/skills/rag-avatar-agent/SKILL.md` e
  `hermes/skills/rag-observability-agent/SKILL.md`, `hermes/hooks/guard.py`,
  `hermes/hooks/inject_context.py`, novo `hermes/harness/services.py`,
  `.claude/agents/engenheiro-ia.md`, `.claude/agents/engenheiro-devops.md`,
  `.claude/agents/lider-tecnico.md`; documentação de estudo em `docs/estudos/`
- **Testes:** novos `tests/test_hermes_config.py`, `tests/test_hermes_guard.py`,
  `tests/test_hermes_services.py` (estáticos/fakes, sem rede, sem Hermes instalado)
- **Não muda:** `src/`, `cli.py`, `.env`, `.env.example`, `uv.lock`, `pyproject.toml`,
  `mlruns/`, `data/`, CI (`.github/workflows/`)

## Decisões do usuário (aprovação em 2026-11-18)
1. **Grafana Cloud, plano free, stack `https://estevaomaia.grafana.net`** (não self-hosted).
   Para não cair na cobrança do MCP gerenciado (`https://mcp.grafana.com/mcp`, que conta cada
   usuário conectado como usuário ativo do Grafana Assistant), o Hermes usa o **`mcp-grafana`
   OSS em stdio** apontado para a stack Cloud, autenticado por **token de service account**.
   `GRAFANA_URL` e `GRAFANA_SERVICE_ACCOUNT_TOKEN` vêm do **`.env` da raiz do repo**
   (ignorado pelo git), lidos pelo wrapper `hermes/mcp/grafana.sh` (ajuste de 2026-11-18; ver
   "Ajuste: .env do repo como fonte"). A variante gerenciada fica comentada como
   alternativa. A URL da stack não é segredo (pode estar em docs e comentários); o token nunca
   aparece no repo. `enabled: false` até o usuário criar o token. O guard bloqueia tokens de
   Cloud com prefixo `glsa_` (service account) e `glc_` (Cloud Access Policy).
2. **`OLLAMA_NUM_PARALLEL=3`** no dia a dia (pai + 2 subagentes). Para avaliação com juiz o
   ideal é **1** (cada slot reserva KV cache de `num_ctx`; com 1 o juiz tem a GPU inteira e
   não disputa com o Hermes). Alternar está documentado no `install.sh` e no `hermes/README.md`.
3. **Os agentes de avatar/comunicação e de observabilidade/feedback já existem fora deste repo
   e entram depois.** O Hermes já é configurado para eles: skills `rag-avatar-agent` e
   `rag-observability-agent` com contrato esperado, destino do código (marcado **a criar**) e
   pontos de integração que já existem (`mascot.py`, `agents/communication.py`, `api/`,
   `feedback.py`, MLflow local, Grafana); papéis `avatar` e `obs` no `rag-orchestrator`.

## Problema
O usuário tem dois agentes do produto: (A) **agente de comunicação via avatar**, que fala com
a pessoa por meio do mascote (`src/rag_cognus/mascot.py`, spec 008,
`src/rag_cognus/agents/communication.py`, rotas `/v1/profile/mascot/options`,
`/v1/agents/communication`, `/v1/feedback`); e (B) **agente de observabilidade/feedback**, que
avalia a aplicação, a API e o MLflow e publica no Grafana. O perfil Hermes `ragdev` (Qwen3.5 9B)
não conhece esses agentes: não há skill com contrato/arquivos/testes, o `rag-orchestrator` só
tem os papéis `dados`/`ia`/`devops`, e o Hermes não tem acesso ao Grafana nem ao estado dos
serviços locais (MLflow 5001, Ollama 11434, API 8001).

## Diagnóstico (2026-11-18, somente leitura)
- Hermes Agent **v0.23.1** (2026.9.24), instalado por git em `~/.hermes/hermes-agent`;
  `hermes` e `ragdev` em `~/.local/bin`. Referência local: `~/.hermes/hermes-agent/cli-config.yaml.example`,
  `website/docs/reference/mcp-config-reference.md`, `website/docs/user-guide/features/{mcp,delegation}.md`.
- **Chaves confirmadas** na versão instalada:
  - `mcp_servers.<nome>` com `command`/`args`/`env` (stdio) ou `url`/`headers` (HTTP),
    `enabled`, `timeout`, `connect_timeout`, `lazy`, `tools.include`/`tools.exclude` (aceita glob).
  - Interpolação `${VAR}` / `${env:VAR}` em `env`, `headers`, `args`, `url`, resolvida do `.env`
    do perfil (`~/.hermes/profiles/ragdev/.env`) ou do ambiente. Variável ausente em `url`/`headers`
    de servidor HTTP **falha fechado** só naquele servidor; em `env` de stdio a entrada é omitida.
  - `skills.external_dirs` (já usado), `agent.personalities` (mapa; seleção em `display.personality`).
  - `delegation.inherit_mcp_toolsets` (padrão `true`): filhos herdam as ferramentas MCP do pai.
  - `delegate_task` aceita por tarefa só `goal`, `context`, `role` (`leaf`/`orchestrator`);
    **não há argumento de toolsets nem de skills para o modelo** — o filho herda os toolsets do pai
    e embute `AGENTS.md`. Logo, "papel" = texto no `context` + skill indicada pelo nome.
  - Catálogo `optional-mcps/grafana`: só a entrada **Grafana Cloud hospedada**
    (`https://mcp.grafana.com/mcp`, OAuth, `hermes mcp login grafana`), com aviso de cobrança
    por usuário do Assistant. O OSS `mcp-grafana` é configurado à mão.
  - `hermes config set <chave> <valor>` existe.
- **A confirmar no primeiro connect** (não verificado localmente, sem rede): imagem
  `mcp/grafana` (`docker run --rm -i ... mcp/grafana -t stdio`) ou binário `mcp-grafana`; nomes
  exatos das ferramentas para `tools.include` — conferir com `ragdev mcp list`/`ragdev tools`.
- No repo **não há Grafana, Prometheus nem OTel em uso**. Porta 3000 é do front (`node`).
  `docker`, `uvx` e `npx` existem; `mcp-grafana` não está no PATH.
- MLflow 3.18.0 tem `--expose-prometheus` e `mlflow mcp` — insumos para spec futura.
- Painel `hermes/monitor/app.py` já agrupa por qualquer `[papel]` no início do `goal`.

## Comportamento esperado
- `ragdev` carrega duas skills novas, `rag-avatar-agent` e `rag-observability-agent`, cada uma
  com: objetivo do agente, contrato de entrada/saída, onde o código vai morar (**a criar**),
  pontos de integração existentes, specs/testes a criar quando o código chegar, como testar
  sem rede e comandos de verificação.
- O `rag-orchestrator` passa a ter os papéis `avatar` e `obs`, com o texto de PAPEL para colar
  no `context` e a instrução "carregue a skill X"; `[avatar]` e `[obs]` aparecem no painel.
- O Hermes alcança o Grafana Cloud por MCP (`mcp_servers.grafana`, OSS em stdio), **desligado
  por padrão**, com URL e token lidos do `.env` do repo pelo wrapper `hermes/mcp/grafana.sh`
  (nenhuma URL nem token no config); só ferramentas de leitura habilitadas por `tools.include`.
- `python hermes/harness/services.py` mostra em uma linha por serviço se MLflow, Ollama, API e
  Grafana respondem (GET com timeout de 2 s, sem enviar nem imprimir tokens); o
  `inject_context` repassa o último resultado em cache (sem rede a cada chamada do modelo).
- No Claude Code, os mesmos papéis existem como extensão de domínio dos engenheiros atuais (sem
  agente novo): avatar → `engenheiro-ia`; observabilidade → `engenheiro-devops` (Grafana,
  serviços, exporters) + `engenheiro-ia` (juízes/feedback).

## Critérios de aceite
- **AC-1:** Dado `hermes/config.yaml` com `__REPO__` trocado por um caminho (mesma substituição
  `sed "s#__REPO__#$REPO#g"` do `install.sh`), quando carregado com `yaml.safe_load`, então é um
  mapa válido, não sobra `__REPO__`, e `mcp_servers.grafana` existe com `enabled: false`.
- **AC-2:** Dado o `config.yaml`, quando se varrem os valores de `mcp_servers.grafana`
  (`url`, `headers`, `env`, `args`), então nenhum carrega URL, `${...}` nem token
  `glsa_…`/`glc_…` (`command` = `__REPO__/hermes/mcp/grafana.sh`, `env` vazio; ajuste de
  2026-11-18), e `tools.include` não contém ferramentas de escrita
  (`update_*`, `create_*`, `delete_*`, `add_*`, `patch_*`) nem `ask_assistant`.
- **AC-3:** Dado `hermes/skills/*/SKILL.md`, quando lido o frontmatter, então toda skill tem
  `name` igual ao nome da pasta e `description` não vazia; existem `rag-avatar-agent` e
  `rag-observability-agent`; cada uma cita ao menos um arquivo real do repo e um comando de
  teste; todo caminho do repo citado entre crases existe, **exceto** na linha marcada
  "a criar" (código que chega depois), e cada skill tem ao menos um caminho "a criar".
- **AC-4:** Dado `hermes/skills/rag-orchestrator/SKILL.md`, quando lido, então a tabela de time
  e a seção de papéis incluem `avatar` e `obs`, cada um nomeando a skill a carregar; e
  `bash -n hermes/install.sh` passa e o `install.sh` imprime o passo opcional do Grafana
  (variáveis no `.env` do perfil + `config set mcp_servers.grafana.enabled true`) e como
  alternar `OLLAMA_NUM_PARALLEL` para 1 na avaliação com juiz.
- **AC-5:** Dado o `guard.py`, quando o comando é `echo $GRAFANA_SERVICE_ACCOUNT_TOKEN`,
  `printenv GRAFANA_SERVICE_ACCOUNT_TOKEN`, ou um comando/`write_file`/`patch` cujo conteúdo traz
  um token `glsa_…` ou `glc_…`, então o hook bloqueia com mensagem em português;
  `curl -s http://127.0.0.1:5001/health` e um texto que só cita o prefixo `glsa_` continuam
  liberados.
- **AC-6:** Dado `hermes/harness/services.py` com um `http_get` falso, quando executado, então
  imprime uma linha `[UP]/[DOWN] serviço url` para MLflow (`/health`), Ollama (`/api/tags`),
  API (`127.0.0.1:8001/v1/health`) e Grafana (`/api/health`, só se `GRAFANA_URL` definido), grava
  `services.json`, nunca imprime nem envia cabeçalhos/tokens, e o `inject_context` inclui uma
  linha `Serviços: …` só quando o cache tem menos de 5 min.

## Ajuste: .env do repo como fonte (2026-11-18, decisão do usuário)
"Use o .env do repo como principal": o token não é copiado para outro arquivo.
- `hermes/mcp/grafana.sh` (novo, executável) é o `command` do `mcp_servers.grafana`. Lê do
  `.env` da raiz **só** `GRAFANA_URL` e `GRAFANA_SERVICE_ACCOUNT_TOKEN`, linha a linha (sem
  `source` nem `eval`; aceita `export` e aspas), dá precedência ao que já estiver exportado e faz
  `exec docker run --rm -i -e GRAFANA_URL -e GRAFANA_SERVICE_ACCOUNT_TOKEN mcp/grafana -t stdio`.
  Faltando uma das duas, sai com erro em stderr que cita só o nome da chave.
- `hermes/harness/services.py` lê `GRAFANA_URL` do `.env` do repo (`REPO_ENV`) quando ela não
  está no ambiente; o token nunca é lido.
- **AC-2b:** Dado um `.env` temporário com as duas chaves e outras (ex. `DATABRICKS_TOKEN`) e um
  `docker` falso no PATH, quando o wrapper roda, então o `docker` recebe exatamente os args
  acima, o ambiente dele tem as duas chaves e nenhuma outra do arquivo, stdout/stderr ficam
  vazios; variável exportada vence o arquivo; sem token, sai ≠ 0 sem chamar o `docker` e sem
  imprimir a URL. Testes: `tests/test_hermes_config.py::test_wrapper_*` e
  `tests/test_hermes_services.py::test_services_le_so_a_url_do_env_do_repo`.
- Riscos: o Hermes pode subir o MCP com PATH curto (o wrapper acrescenta `/usr/local/bin` e
  `/opt/homebrew/bin`); o `.env` precisa estar na raiz do repo apontado por `__REPO__`.
- O passo "b" do `hermes/install.sh` e as mensagens do `hermes/hooks/guard.py` também apontam
  para o `.env` da raiz do repo.

## Fora de escopo
- Código dos agentes em `src/rag_cognus/` (avatar e observabilidade): chega de fora do repo,
  com specs próprias (sugestão nas skills).
- Subir Grafana/Prometheus/Alloy, exportar métricas da API ou do MLflow, dashboards e alertas:
  spec futura de devops, com dependências justificadas.
- MCP do MLflow (`mlflow mcp`): avaliar depois. Spec 012 (`cli.py`): outra rodada.
- Mudar CI: os testes novos rodam no `pytest` do CI sem nada a instalar (PyYAML vem do MLflow).
- Criar agentes novos em `.claude/agents/`.

## Riscos e dúvidas
- Ferramentas MCP aumentam o prompt do 9B; `tools.include` curto e `lazy: true` reduzem isso.
- Filhos herdam MCP (`inherit_mcp_toolsets: true`): um `[ia]` também veria o Grafana. Aceitável
  (só leitura); alternativa é `false` e perder o Grafana nos `[obs]`.
- `ragdev config set mcp_servers.grafana.enabled true` é sobrescrito na próxima execução do
  `install.sh`; para ficar permanente, mude `enabled` em `hermes/config.yaml` localmente.
- Service account com papel **Viewer** limita o estrago se o token vazar; plano free tem cota.
- `services.py` faz rede real só quando chamado pelo agente/usuário; nunca nos testes.

## Plano
| Passo | Arquivo | Subagente | Verificação |
|---|---|---|---|
| 1 | `tests/test_hermes_config.py` (AC-1…AC-4) | engenheiro-devops | falha: skills/grafana ausentes |
| 2 | `hermes/config.yaml` (`mcp_servers.grafana`, `enabled: false`, `lazy: true`, `tools.include`) | engenheiro-devops | AC-1, AC-2 |
| 3 | `hermes/skills/rag-avatar-agent/SKILL.md` | engenheiro-devops | AC-3 |
| 4 | `hermes/skills/rag-observability-agent/SKILL.md` | engenheiro-devops | AC-3 |
| 5 | `hermes/skills/rag-orchestrator/SKILL.md`, `hermes/install.sh`, `hermes/README.md` | engenheiro-devops | AC-4 |
| 6 | `tests/test_hermes_guard.py` → `hermes/hooks/guard.py` | engenheiro-devops | AC-5 |
| 7 | `tests/test_hermes_services.py` → `hermes/harness/services.py`, `hermes/hooks/inject_context.py` | engenheiro-devops | AC-6 |
| 8 | `.claude/agents/engenheiro-{ia,devops}.md`, `lider-tecnico.md` (domínios) | engenheiro-devops | revisão do líder |
| 9 | `docs/estudos/{hermes-agentes,hermes-mcp-grafana,agente-avatar,agente-observabilidade}.md` | engenheiro-devops | revisão do líder |
| 10 | tudo | líder técnico | `python hermes/harness/check.py` → `HARNESS OK`; manual: `bash hermes/install.sh`, `ragdev doctor`, `ragdev mcp list` |

## Documentação para estudo (`docs/estudos/`)
- `hermes-agentes.md` — como o `ragdev` delega (`delegate_task`: goal/context/role), skills
  externas, papéis `[avatar]`/`[obs]`, hooks, `services.py` e painel.
- `hermes-mcp-grafana.md` — passo a passo: service account e token na stack
  `estevaomaia.grafana.net`, `.env` do perfil, ligar `enabled`, testar; stdio x HTTP, `lazy`,
  `tools.include`, por que OSS e não o MCP gerenciado.
- `agente-avatar.md` — contrato do mascote (spec 008) e do agente de comunicação via avatar.
- `agente-observabilidade.md` — sinais (MLflow, API, Ollama), feedback e Grafana.
- `mlflow-juizes-ollama.md` — ver spec 012.
