# Agente de observabilidade e feedback

Guia de estudo do papel `[obs]` (skill `hermes/skills/rag-observability-agent/SKILL.md`).

## 1. Situação
O agente já existe fora deste repositório e vai ser integrado depois. O Hermes já tem o que
ele precisa para diagnosticar: status dos serviços, acesso de leitura ao MLflow local e, quando
o token existir, ao Grafana Cloud (`https://estevaomaia.grafana.net`).

## 2. Sinais que o agente lê
| Sinal | Onde | Para quê |
|---|---|---|
| Serviços no ar | `python hermes/harness/services.py` | Antes de culpar o modelo, ver se MLflow/Ollama/API respondem |
| Saúde da API | `GET /v1/health` | Ollama, MLflow e nº de chunks da Gold do ponto de vista da API |
| Avaliação online | `GET /v1/ask/{ask_id}/evaluation`, experimento `rag-cognus-online` | Juízes e métricas por pergunta real |
| Avaliação em lote | experimento `rag-cognus` (`rag-cognus evaluate`) | Comparar versões do RAG com o mesmo dataset |
| Feedback humano | `user_feedback` nos traces (`POST /v1/feedback`) | O que a pessoa achou, não só o juiz |
| Mascote coach | traces `flow=mascot`, tag `mascot_source` | Taxa de explicações por regras (LLM fora ou guarda rejeitando) |
| Grafana | MCP `grafana` (só leitura) | Dashboards, métricas e alertas consolidados |

Por que juiz **e** feedback humano: o juiz LLM é barato e roda em toda resposta, mas erra de
forma sistemática; o feedback humano é raro e caro, mas é a verdade. O agente compara os dois
para achar onde o juiz diverge das pessoas.

## 3. Por que MLflow local e Grafana Cloud juntos
- **MLflow local** (`http://127.0.0.1:5001`) guarda traces, juízes e feedback com detalhe por
  pergunta. É a fonte da verdade da qualidade. `databricks://` é proibido no projeto.
- **Grafana Cloud** guarda séries no tempo e alertas, acessível de qualquer lugar. Hoje ninguém
  publica métricas lá; publicar (Prometheus remote write, OTLP ou Grafana Alloy) é uma spec
  futura de devops, com dependência justificada. Por enquanto o agente só **lê**.

O papel (fontes, restrições e o formato do relatório `SEVERIDADE … CORRECAO_ESTRUTURAL`) já
está em `hermes/agents/diagnoser-agent.md`.

## 4. Contrato proposto
Entrada: janela (`since`, `until`), experimentos e URL da API.
Saída: `services`, `quality`, `feedback`, `alerts`, `published` (detalhes na skill).

Regras e porquês:
- **Só leitura** no MLflow (`MlflowClient`) e no Grafana (service account Viewer): observar
  não pode mudar o que é observado.
- **Nunca imprimir tokens**: o guard bloqueia `glsa_…`/`glc_…` e `$…TOKEN` no terminal.
- **Achados objetivos** em `alerts` (números antes/depois), não opinião do modelo.

## 5. Quando o código chegar
1. Spec `specs/015-agente-observabilidade.md` (número sugerido; 013/014 são do mascote).
2. Testes em `tests/test_observability.py` com `MlflowClient` e HTTP falsos (o padrão de
   `http_get` falso está em `tests/test_hermes_services.py`).
3. Código em `src/rag_cognus/agents/observability.py`.
4. `python hermes/harness/check.py` até `HARNESS OK`.

No Hermes: `goal: "[obs] …"`, com "carregue a skill rag-observability-agent" no `context`.
No Claude Code: `engenheiro-devops` (serviços, Grafana, exporters) e `engenheiro-ia` (juízes,
feedback).
