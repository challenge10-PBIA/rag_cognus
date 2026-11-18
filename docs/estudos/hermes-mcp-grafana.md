# Hermes + Grafana Cloud por MCP

Guia de estudo e passo a passo para ligar o Grafana Cloud da stack
**https://estevaomaia.grafana.net** ao perfil Hermes `ragdev` (spec 009).

## 1. O que é MCP e por que usar aqui
MCP (Model Context Protocol) é um jeito padronizado de um agente ganhar "ferramentas" vindas
de outro programa. O Hermes conversa com um **servidor MCP**; o servidor expõe ferramentas
como `search_dashboards` ou `query_prometheus`, e o modelo pode chamá-las como chama
`terminal` ou `write_file`.

No rag_cognus isso serve ao papel `[obs]` (agente de observabilidade): ele precisa ler
dashboards, métricas e alertas do Grafana para dizer como a aplicação está.

## 2. Duas formas de ligar o Grafana, e qual escolhemos

| | MCP gerenciado (Cloud) | `mcp-grafana` OSS (escolhido) |
|---|---|---|
| Onde roda | Servidor da Grafana, `https://mcp.grafana.com/mcp` | Na sua máquina (Docker ou binário) |
| Transporte | HTTP | stdio (o Hermes abre o processo e fala por stdin/stdout) |
| Autenticação | OAuth no navegador (`hermes mcp login`) | Token de **service account** |
| Custo | Cada usuário conectado conta como usuário ativo do **Grafana Assistant** (cobrado) | Só usa a API normal da stack; cabe no plano free |
| Permissões | As do seu usuário (pode ser Editor/Admin) | As do service account (escolhemos **Viewer**) |

**Por quê o OSS:** a stack está no plano free e o MCP gerenciado contaria o uso como Grafana
Assistant. O OSS fala direto com a API da stack, com um token que só pode ler. A variante
gerenciada ficou **comentada** no `hermes/config.yaml` (`grafana_cloud`) para quem quiser.

## 3. Como está no `hermes/config.yaml`
```yaml
mcp_servers:
  grafana:
    enabled: false        # desligado até existir o token
    lazy: true            # só abre o processo quando uma ferramenta é usada
    command: "__REPO__/hermes/mcp/grafana.sh"   # o install.sh troca __REPO__ pelo caminho
    args: []
    tools:
      include: [search_dashboards, get_dashboard_by_uid, list_datasources,
                query_prometheus, query_loki_logs, list_alert_rules]
```
O porquê de cada linha:
- **Wrapper `hermes/mcp/grafana.sh`**: a fonte da URL e do token é o **`.env` da raiz do
  repo** (decisão do usuário: um só `.env`, sem copiar o token para outro arquivo). O wrapper:
  1. lê do `.env` **só** `GRAFANA_URL` e `GRAFANA_SERVICE_ACCOUNT_TOKEN`, linha a linha. Não
     faz `source` do arquivo inteiro nem `eval`: assim nenhuma outra variável (ex. o token do
     Databricks) chega ao contêiner, e nada escrito no `.env` é executado;
  2. se a variável já estiver exportada no ambiente, ela vence o arquivo;
  3. faltando uma das duas, sai com uma mensagem em stderr que cita só o **nome** da chave;
  4. faz `exec docker run --rm -i -e GRAFANA_URL -e GRAFANA_SERVICE_ACCOUNT_TOKEN mcp/grafana
     -t stdio`. O `exec` troca o shell pelo `docker`, então o stdin/stdout do MCP passam direto.
- **Nada de `${VAR}` no config**: o config não carrega URL nem token; um teste
  (`tests/test_hermes_config.py`) garante isso e testa o wrapper com um `.env` temporário e um
  `docker` falso.
- **`-e GRAFANA_URL` sem valor**: o Docker copia a variável do processo pai para o contêiner.
  O valor nunca aparece na linha de comando (que fica visível em `ps`).
- **`enabled: false`**: sem token o servidor só daria erro a cada sessão.
- **`lazy: true`**: o modelo local (Qwen3.5 9B) tem contexto curto; não vale abrir o
  processo nem carregar as ferramentas se ninguém usar.
- **`tools.include`**: lista curta e **só de leitura**. Cada ferramenta ocupa espaço no
  prompt e ferramentas de escrita (`update_dashboard`, `create_*`…) não fazem sentido para um
  agente que só observa. Um teste (`tests/test_hermes_config.py`) garante isso.
- **`connect_timeout: 60`**: na primeira vez o Docker baixa a imagem `mcp/grafana`.

## 4. Passo a passo para ligar

### 4.1 Criar o service account e o token (no navegador)
1. Abra https://estevaomaia.grafana.net e entre como administrador da stack.
2. Menu **Administration → Users and access → Service accounts**
   (atalho: https://estevaomaia.grafana.net/org/serviceaccounts).
3. **Add service account** → nome `hermes-ragdev`, papel **Viewer** → **Create**.
   Viewer basta para ler dashboards, datasources, métricas e alertas; se o token vazar,
   ninguém altera nada.
4. Na página do service account: **Add service account token** → nome `ragdev-local`,
   escolha uma expiração (ex.: 90 dias) → **Generate token**.
5. **Copie o token agora** (começa com `glsa_`); o Grafana não mostra de novo.

### 4.2 Guardar no `.env` do repo (nunca no `.env.example`)
Abra o `.env` da raiz do repo num editor (não use `echo` com o token: ele fica no histórico
do shell) e preencha:
```
GRAFANA_URL=https://estevaomaia.grafana.net
GRAFANA_SERVICE_ACCOUNT_TOKEN=<cole o token aqui>
```
Depois: `chmod 600 .env`.

Por que o `.env` do repo: é o único arquivo de configuração local que você já mantém, e ele é
**ignorado pelo git** (`.gitignore`). O `.env.example` tem as duas chaves **vazias**, só como
modelo, e vai para o git: o token nunca vai lá. A aplicação (`config.py`) não lê essas chaves;
quem lê é só o wrapper (as duas chaves) e o `hermes/harness/services.py` (só a URL, para o
GET de saúde sem credencial). O guard (`hermes/hooks/guard.py`) bloqueia comandos e edições
que tragam um token `glsa_…`/`glc_…` em texto puro e comandos que ecoam a variável do token.

### 4.3 Ligar
```bash
ragdev config set mcp_servers.grafana.enabled true
```
Atenção: `bash hermes/install.sh` copia o `config.yaml` do repo de novo e volta para
`false`. Para deixar permanente na sua máquina, mude `enabled: true` no `hermes/config.yaml`
local e reinstale (não faça commit dessa mudança se outras pessoas usam o repo sem token).

### 4.4 Testar
1. Docker Desktop aberto (`docker info` responde).
2. `python hermes/harness/services.py` → deve aparecer `[UP] grafana https://estevaomaia.grafana.net/api/health`
   (esse GET não usa token; só prova que a stack responde).
3. `ragdev mcp list` → o servidor `grafana` conecta e lista as ferramentas. **Confira os nomes**:
   se algum de `tools.include` não existir na versão da imagem, ajuste a lista.
4. Dentro do `ragdev`: *"Use a skill rag-observability-agent e liste os datasources do Grafana."*

Se falhar:
- `401/403`: token errado, expirado ou service account sem papel; gere outro.
- Não conecta: Docker fechado ou imagem não baixou (`docker pull mcp/grafana`).
- `grafana.sh: falta GRAFANA_…`: a chave está vazia no `.env` da raiz do repo (ou o arquivo
  não está na pasta apontada pelo `__REPO__` do `install.sh`).
- Sem Docker: instale o binário `mcp-grafana` (releases do projeto `grafana/mcp-grafana`) e
  troque a última linha do wrapper por `exec mcp-grafana -t stdio`.

## 5. Riscos conhecidos
- Os subagentes herdam as ferramentas MCP do pai (`delegation.inherit_mcp_toolsets: true`).
  Um `[ia]` também veria o Grafana; aceitável porque é só leitura.
- O plano free tem cota de métricas/logs; consultas grandes (`query_prometheus` com intervalo
  longo) podem ser lentas. Peça janelas curtas.
- Variáveis antigas: versões velhas do `mcp-grafana` usavam `GRAFANA_API_KEY`. Se o servidor
  reclamar de credencial, confira a versão da imagem.
