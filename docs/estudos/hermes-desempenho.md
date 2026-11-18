# Desempenho do Hermes com o Qwen3.5 9B num Mac (spec 015)

Material de estudo: por que o perfil `ragdev` não terminava nem "leia AGENTS.md e diga quais
módulos existem", o que foi medido, como funciona a memória do KV cache e por que cada ajuste
ajuda. Spec: `specs/015-hermes-desempenho.md`. Máquina: Mac M4, 24 GB de memória unificada,
Ollama 0.32, `qwen3.5:9b` (Q4_K_M).

## 1. O sintoma
O `~/.hermes/profiles/ragdev/logs/errors.log` mostrava:

```
Interrupted provider wait counted as stale after 119s with no output
model.context_length pins qwen3.5:9b at 64,000 tokens but the provider advertises 262,144
```

O primeiro aviso quer dizer: o usuário interrompeu depois de ~2 min **sem nenhum token** de
volta. O segundo só avisa que a config fixou a janela em 64000.

## 2. Duas fases de uma chamada ao LLM
1. **Prefill**: o modelo lê o prompt inteiro (system prompt + schemas das ferramentas +
   conversa) e grava o KV cache. Custo proporcional ao número de tokens do prompt. Nada
   aparece na tela durante essa fase.
2. **Decode**: gera a resposta, um token por vez, reaproveitando o KV cache.

No M4 o prefill do 9B rodou a **~110–150 tokens/s** e o decode a **~11–13 tokens/s**.

## 3. O que foi medido (2026-11-18)

`ragdev prompt-size` (diagnóstico offline do hermes-agent) mostra o que vai em toda chamada:

| Parte | Antes | Depois (config da spec 015) |
|---|---|---|
| System prompt (identidade, skills, AGENTS.md, memória) | 23,8 KB | 23,8 KB |
| Schemas das ferramentas | 40,4 KB (21 ferramentas) | 24,7 KB (14 ferramentas) |
| MCP `grafana` ligado (`lazy`) no perfil instalado | +6,1 KB (5 ferramentas) | 0 (`enabled: false`) |
| **Total** | **~70 KB ≈ 21,5 mil tokens** | **~48,6 KB ≈ 14,9 mil tokens** |

Tokens: o Ollama contou 19.663 tokens para um prompt de 64,2 KB (`prompt_eval_count`), ou
~3,26 bytes por token; o resto da tabela usa essa razão.

`/api/chat` com prompt do mesmo tamanho (19.663 tokens), `num_predict` 160:

| `num_ctx` | Situação | 1º token | Prefill | Decode | `ollama ps` |
|---|---|---|---|---|---|
| 64000 | cache frio (modelo recém-carregado) | **136 s** | 150 tok/s | 12,9 tok/s | 7,6 GB, 100% GPU |
| 64000 | prefixo em cache (só a pergunta mudou) | **5,7 s** | — | 11,6 tok/s | |
| 64000 | idem com `think: true` | 5,9 s | — | 10,9 tok/s | |
| 32768 | cache frio | **186 s** | 109 tok/s | 10,4 tok/s | 6,6 GB, 100% GPU |
| 32768 | **depois**: prompt de 14.979 tokens, cache frio | **143 s** | 105 tok/s | 10,7 tok/s | 6,6 GB, 100% GPU |
| 32768 | **depois**: prefixo em cache | **6,0 s** | — | 10,8 tok/s | |
| 131072 | `/v1` com `options.num_ctx: 8192` (o Hermes) | recarregou com `-c 131072` | — | — | **9,9 GB** |

O `num_ctx` quase não muda a velocidade: o que muda é **ter ou não o prompt em cache**. A
variação 150 → 105 tok/s veio da máquina ocupada (outros processos), não do contexto. A
última linha confirma que o `/v1` do Ollama 0.32 ignora `options.num_ctx`: o modelo
recarregou com o `OLLAMA_CONTEXT_LENGTH` do servidor (131072) e passou a ocupar 9,9 GB.

O log do Ollama (`~/.ollama/logs/server.log`) explicou o resto:
- As três sessões do Hermes do dia começaram com o modelo **recarregando**
  (`llama-server ... -c 131072`) e levaram 1m51s, 1m51s e 1m58s (a última interrompida).
- O servidor rodava com `OLLAMA_CONTEXT_LENGTH:131072`, `OLLAMA_NUM_PARALLEL:1` e
  `OLLAMA_KEEP_ALIVE:5m0s`. Entre duas sessões com mais de 5 min o modelo saiu da memória.
- O Hermes fala com o Ollama pelo `/v1` (OpenAI-compatível) e manda `options.num_ctx`, mas o
  modelo carregou com 131072, não 64000: o contexto efetivo do Hermes é o
  `OLLAMA_CONTEXT_LENGTH` do servidor. O app (`/api/chat`, `OLLAMA_NUM_CTX=16384`) carrega
  com outro valor, e a cada troca app ↔ Hermes o modelo recarrega e perde o cache.

**Conclusão:** cache frio de ~20 mil tokens a ~150 tok/s = ~130 s antes do 1º token, acima
dos ~120 s que o usuário espera. E o cache ficava frio quase sempre.

## 4. Memória do KV cache
Para cada token do contexto, cada camada de atenção guarda um vetor **K** (chave) e um **V**
(valor) por cabeça KV. Fórmula:

```
bytes/token = camadas_de_atenção × 2 (K e V) × cabeças_KV × dimensão_da_cabeça × bytes/elemento
KV total    = bytes/token × num_ctx × OLLAMA_NUM_PARALLEL
```

O `qwen3.5:9b` é **híbrido** (`ollama show qwen3.5:9b --verbose`): 32 blocos, mas só 1 a cada
4 (`full_attention_interval 4`) é de atenção; os outros 24 são recorrentes (Gated DeltaNet),
com estado de tamanho fixo que não cresce com o contexto.

```
8 camadas × 2 × 4 cabeças KV × 256 dim × 2 bytes (f16) = 32.768 B = 32 KB por token
```

| `num_ctx` | KV f16 | KV `q8_0` |
|---|---|---|
| 16384 | 0,5 GB | 0,25 GB |
| 32768 | 1 GB | 0,5 GB |
| 64000 | 2 GB | 1 GB |
| 131072 | 4 GB | 2 GB |

Bate com o `ollama ps`: 6,6 GB em 32768 e 7,6 GB em 64000 (31 mil tokens a mais ≈ 1 GB).
Um modelo denso do mesmo porte (32 camadas de atenção, 8 cabeças KV × 128) gastaria 128 KB
por token, quatro vezes mais. Por isso, **neste modelo, memória não é o gargalo**: o perfil
cabe folgado em 24 GB mesmo com o Docker e o app abertos. O gargalo é o prefill.

Cada slot de `OLLAMA_NUM_PARALLEL` tem o próprio KV: 3 slots × 64000 = 6 GB só de KV.

## 5. Por que cada ajuste ajuda

| Ajuste | Efeito | Por quê |
|---|---|---|
| `disabled_toolsets` (web, browser, code_execution, vision, image_gen, tts, connections, cronjob, computer_use) | −15,7 KB por chamada (~4,8 mil tokens, ~32 s de prefill frio) | o schema de cada ferramenta vai em toda chamada; o projeto usa terminal, arquivos, skills, todo, memória e delegação. O 9B ainda errava `execute_code` em loop |
| MCP `grafana` `enabled: false` | −6,1 KB (~1,9 mil tokens) | `lazy: true` só adia o `docker run`: o Hermes registra as ferramentas do cache de schema na largada, então elas pesam no prompt mesmo sem uso |
| `reasoning_effort: "none"` | sem centenas de tokens de raciocínio por passo | no Ollama, qualquer nível diferente de `none` liga o mesmo `think` do Qwen (não há níveis); a ~12 tok/s, 500 tokens de raciocínio = ~40 s por ação. Aceitos: none, minimal, low, medium, high, xhigh, max. Para uma tarefa difícil, `/reasoning low` na sessão |
| `context_length` = `ollama_num_ctx` = `OLLAMA_CONTEXT_LENGTH` = `OLLAMA_NUM_CTX` = 32768 | o modelo não recarrega ao alternar app ↔ Hermes | `num_ctx` diferente obriga o Ollama a recarregar e o cache do prompt se perde. 32768 cabe o prompt (~15 mil) e a conversa; 16384 não caberia |
| `OLLAMA_KEEP_ALIVE=30m` | o modelo continua carregado entre pedidos | com 5m, uma pausa curta descarrega o modelo e a próxima chamada paga carga + prefill frio |
| `OLLAMA_NUM_PARALLEL=1` + `max_concurrent_children: 1` | um pedido por vez com a GPU inteira | dois pedidos ao mesmo tempo dividem o prefill (cada um fica 2× mais lento) e cada slot extra começa sem cache. O pai espera o filho, então 1 slot basta |
| `compression.threshold: 0.75` | valor honesto | o hermes-agent aplica piso de 0.75 em modelos com menos de 512K; o 0.60 de antes era ignorado. Com 32768, a compressão começa em ~24,5 mil tokens |
| `OLLAMA_FLASH_ATTENTION=1` | atenção sem materializar a matriz N×N | menos memória e banda no prefill longo; é pré-requisito para quantizar o KV. O runner já usa `--flash-attn auto`, então o ganho aqui é pequeno, mas fixa o comportamento |
| `OLLAMA_KV_CACHE_TYPE=q8_0` | KV com metade da memória | 8 bits por elemento em vez de 16, perda de qualidade desprezível. Neste modelo economiza ~0,5 GB em 32768; ajuda mais se você subir o contexto ou os slots |
| skill `rag-harness` + hook `inject_context` | o agente roda `check.py --changed` durante a iteração | o harness completo leva ~40 s e despeja mais saída; fica só para o fim |

### Projeção (1º token na tarefa simples)

| Situação | Antes | Depois |
|---|---|---|
| Cache frio (1ª chamada, modelo já na memória) | ~21,5 mil tokens: 145 s (150 tok/s) a 205 s (105 tok/s) | ~15 mil tokens: **100 s a 143 s medido** |
| Modelo descarregado (keep-alive 5m) ou `num_ctx` trocado | acontecia em toda sessão (log) | evitado (`KEEP_ALIVE=30m`, um `num_ctx` só) |
| Chamadas seguintes (prefixo em cache) | ~6 s + raciocínio (~40 s) | **~6 s medido**, sem raciocínio |

A primeira chamada de cada sessão continua lenta (até ~2,5 min com a máquina ocupada): ~15 mil
tokens de prompt fixo não somem. A diferença é que agora ela é a **única** fria: as seguintes
reaproveitam o cache, em vez de recarregar o modelo a cada sessão ou troca com o app.
Dica: abra o `ragdev` e espere a 1ª resposta antes de mandar a tarefa, ou mande a tarefa e não
interrompa nos primeiros 2–3 min.
Para cortar mais: tirar `delegation` (−4,7 KB) quando não for orquestrar, ou desligar as skills
embutidas do Hermes que o projeto não usa (`skills.disabled`, −3,9 KB do índice).

### Cache de prefixo em modelo híbrido
No 64000 a segunda chamada (mesmo system prompt, outra pergunta) leu o prompt em 5,5 s em vez
de 131 s: o Ollama reaproveitou o prefixo. Em modelos híbridos o estado recorrente não pode ser
"cortado" no meio, então o llama.cpp só retoma a partir de checkpoints (o log mostra
`context checkpoints enabled, max = 32, min spacing = 8192` e um checkpoint perto do fim do
prompt). Quando o prompt muda antes do checkpoint, ele relê tudo
(`forcing full prompt re-processing due to lack of cache data (... hybrid/recurrent memory)`):
foi o que aconteceu numa rodada de teste em que o texto do prompt mudou no começo.
O Ollama 0.32 também guarda prompts inteiros na RAM (`prompt cache is enabled, size limit:
8192 MiB`; ~720 MB por prompt de 20 mil tokens em f16), outro motivo para o `q8_0`. O hook `inject_context` do projeto entra no fim da mensagem do usuário,
não no system prompt, e por isso não quebra o prefixo.

## 6. Como conferir
```bash
ragdev prompt-size                                   # tamanho do prompt e das ferramentas
ollama ps                                            # tamanho carregado, PROCESSOR e CONTEXT
grep "server config" ~/.ollama/logs/server.log | tail -1     # variáveis que o servidor leu
grep -E "starting llama-server|POST" ~/.ollama/logs/server.log | tail   # recargas e latências
```
Sinal de problema: `starting llama-server` no meio de uma sessão (recarga) ou o `CONTEXT` do
`ollama ps` diferente de 32768.
