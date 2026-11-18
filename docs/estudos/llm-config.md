# Configuração do LLM por papel (spec 010)

Material de estudo: o que mudou na forma de chamar o Ollama, por quê, o que cada variável
faz e como conferir no MLflow. Spec: `specs/010-config-llm.md`.

## 1. O problema em uma frase
O `ChatOllama` só enviava `temperature`, `num_ctx` e `num_predict`. Todo o resto vinha do
**Modelfile** do `qwen3.5:9b`, inclusive `presence_penalty 1.5`, que pune repetir tokens.
O nosso prompt pede justamente repetição: copiar o `trecho` literal e repetir o mesmo
`chunk_id` em `fontes` e `cited_chunk_ids`. Antes não havia como mudar isso pelo `.env`.

## 2. Papéis
Toda chamada ao Ollama agora declara um papel (`role`):

| Papel | Quem usa | `num_predict` padrão |
|---|---|---|
| `generator` | RAG (`chain.py`), síntese de evidências, adaptação ao público | 900, 1200, 1500 |
| `judge` | juiz do RAG (`judges.py`) e juízes dos agentes | 700, 600, 600 |
| `fast` | decomposição do tema (`evidence.py`) e verificador de pleonasmos | 200, 300 |

O modelo de cada papel: `generator` usa `OLLAMA_CHAT_MODEL`, `judge` usa
`OLLAMA_JUDGE_MODEL` (vazio = chat) e `fast` usa `OLLAMA_FAST_MODEL` (vazio = chat).

## 3. Onde está no código
- `src/rag_cognus/config.py`: campos novos do `Settings`, leitura do `.env` (`LLM_ENV`) e
  validação com mensagens que citam o nome da variável.
- `src/rag_cognus/llm.py`:
  - `ollama_options(settings, role, *, model=None, num_predict=None)` devolve as opções
    efetivas (modelo, temperatura, think, num_ctx, keep_alive, timeout, num_predict e as
    opções de amostragem que estiverem definidas).
  - `make_ollama(settings, schema, *, role="generator", num_predict=...)` monta o
    `ChatOllama` e envia `options` **explícitas** no payload. Uma subclasse pequena
    (`OptionsChatOllama`) faz isso, porque o `ChatOllama` 1.1.0 não tem o campo
    `presence_penalty`.
  - `llm_attributes(...)` e `tag_llm_span(...)` gravam `model`, `role` e `options` nos spans
    LLM do MLflow.

## 4. Garantia principal: sem variável nova, nada muda
Com o `.env` atual, o payload enviado é exatamente o de antes:
`options = {"temperature": 0, "num_ctx": 16384, "num_predict": N}`, `think=false` e
`keep_alive="30m"`. As chaves `top_p`, `top_k`, `repeat_penalty`, `presence_penalty` e `seed`
**não são enviadas** enquanto estiverem vazias. Os testes `test_default_payload_is_unchanged`
e `test_ollama_options_defaults_match_current_payload` (em `tests/test_config.py`) protegem
essa garantia.

## 5. Variáveis
| Variável | Padrão | Recomendado (só após comparar runs) | Para quê |
|---|---|---|---|
| `OLLAMA_TEMPERATURE` | `0` | `0` | gerador: resposta factual e com citação |
| `OLLAMA_JUDGE_TEMPERATURE` | `0` | `0` | notas reprodutíveis |
| `OLLAMA_FAST_TEMPERATURE` | `0` | `0` | decomposição estável |
| `OLLAMA_SEED` | vazio | `42` | reprodutível se alguém subir a temperatura |
| `OLLAMA_TOP_P` / `OLLAMA_TOP_K` | vazio (Modelfile 0.95 / 20) | vazio | não fazem efeito com temperatura 0 |
| `OLLAMA_REPEAT_PENALTY` | vazio | `1.0` | não punir a cópia literal |
| `OLLAMA_PRESENCE_PENALTY` | vazio (Modelfile 1.5) | `0` | o JSON repete IDs e chaves |
| `OLLAMA_JUDGE_PRESENCE_PENALTY` | vazio (= global) | `0` | o juiz repete nomes de critério |
| `OLLAMA_GENERATOR_NUM_PREDICT` | vazio (padrão da chamada) | — | teto de tokens; JSON cortado vira erro |
| `OLLAMA_JUDGE_NUM_PREDICT` | vazio | — | idem |
| `OLLAMA_FAST_NUM_PREDICT` | vazio | — | idem |
| `OLLAMA_THINK` / `OLLAMA_JUDGE_THINK` | `false` | `false` | o raciocínio do Qwen triplica a latência |
| `OLLAMA_JUDGE_NUM_CTX` / `OLLAMA_FAST_NUM_CTX` | vazio (= `OLLAMA_NUM_CTX`) | — | só valem se o modelo do papel for outro |
| `OLLAMA_TIMEOUT` | `300` | `300` | segundos por chamada |

Regras e validação:
- Temperatura fora de [0, 2], `top_p` fora de (0, 1], `num_predict < 64`, `num_ctx < 2048`
  ou `timeout <= 0` levantam `ValueError` com o nome da variável.
- `seed`, `top_p`, `top_k`, `repeat_penalty` e `presence_penalty` são globais. Só a
  `presence_penalty` tem sobrescrita própria do juiz.
- **`num_ctx` é por modelo.** Se o juiz (ou o rápido) usa o mesmo modelo do chat, ele recebe
  `OLLAMA_NUM_CTX` mesmo que `OLLAMA_JUDGE_NUM_CTX` esteja preenchido. Valores diferentes de
  `num_ctx` para o mesmo modelo fazem o Ollama recarregá-lo a cada troca.
- O `top_k` de amostragem fica no campo `llm_top_k` do `Settings`, para não colidir com o
  `top_k` da recuperação (`RAG_TOP_K`).
- `OLLAMA_FAST_MODEL` deve ficar vazio enquanto o `qwen3.5:4b` não estiver instalado. Se o
  modelo não existir, a decomposição cai no fallback (segue sem dividir o tema). Agora o
  span `decompose_topic` mostra o motivo no atributo `fallback_reason` (por exemplo
  `ResponseError`).

## 6. Como verificar no MLflow local
1. Rode uma avaliação: `rag-cognus evaluate --generate --judge` (com Ollama e MLflow no ar).
2. Abra o run no experimento `rag-cognus` e veja os **Parameters**:
   - `generator_options` e `judge_options`: JSON com `model`, `temperature`, `think`,
     `seed`, `top_p`, `top_k`, `repeat_penalty`, `presence_penalty`, `num_predict` e
     `num_ctx`. Um valor `null` significa "não enviado, vale o Modelfile".
   - `judge_is_generator`: `true` quando o juiz é o mesmo modelo do gerador, ou seja, quando
     há viés de autoavaliação.
3. Em **Traces**, abra um trace e clique no span `generate_grounded_answer` (ou
   `synthesize_evidence`, `decompose_topic`, `adapt_text`). Os atributos `model`, `role` e
   `options` mostram o que foi usado naquela chamada.

## 7. Como adotar os valores recomendados
1. Rode `rag-cognus evaluate --generate --judge` com o `.env` atual e anote o `gold_fingerprint`.
2. Preencha `OLLAMA_PRESENCE_PENALTY=0` e `OLLAMA_REPEAT_PENALTY=1.0` (e, se quiser,
   `OLLAMA_SEED=42`).
3. Rode de novo e compare os dois runs no MLflow (mesmo `gold_fingerprint`):
   `citation_integrity/mean`, `groundedness/mean`, `error/mean` e a latência.
4. Adote os valores só se o run novo for igual ou melhor.

Expectativa: `citation_integrity` e `groundedness` iguais ou maiores e menos erros do tipo
"Modelo citou um ID ausente" ou de trecho não literal. Isso é uma hipótese, e só a
comparação confirma.
