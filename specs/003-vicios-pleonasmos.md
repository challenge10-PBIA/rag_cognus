# 003 — Vícios detectados pela própria fala e pleonasmos

- **Status:** implementada (AC-1…AC-16; `SPEECH_PLEONASM_LLM` ligado na API, padrão off)
- **Módulos:** `src/rag_cognus/speech_analysis.py`, `src/rag_cognus/api/app.py`,
  `src/rag_cognus/api/schemas.py`
- **Testes:** `tests/test_speech_analysis.py`, `tests/test_api.py`
- **Depende de:** spec 002 (pilares, `analyze_words`, `/v1/sessions`)

## Problema
`speech_analysis.py` só reconhece vícios de uma lista fixa (`FILLER_WORDS` + "é" alongado).
Marcadores discursivos usados em excesso ("então", "basicamente", "tipo assim", "na verdade",
"entendeu") passam despercebidos, e pleonasmos ("subir pra cima", "há anos atrás") não são
apontados. O usuário vê "Zero “éé” ou “tipo”" numa fala com 12 "então" em um minuto.

Exemplo: 60 s de fala com "então" 6× (5 deles logo após uma pausa) e "elo de ligação" 1× →
hoje `fillers.counts == {}`; esperado: um `vicio_detectado` "então" (6×) e um `pleonasmo`
"elo de ligação" com sugestão "elo".

## Comportamento esperado
- A análise da sessão devolve uma lista de **ocorrências**, cada uma com termo, tipo
  (`vicio_fixo` | `vicio_detectado` | `pleonasmo`), trecho, `start`/`end` (das `words` do
  faster-whisper) e sugestão de correção em português.
- **Vício fixo**: o que `is_filler` já reconhece (inalterado).
- **Vício detectado**: n-grama (1 a 3 palavras) de baixo conteúdo que se repete acima de um
  limiar por minuto na própria fala. Uso moderado de "então" não é vício.
- **Pleonasmo**: léxico determinístico em constante; opcionalmente um LLM injetável confirma
  candidatos ou sugere novos, sempre com o trecho literal da transcrição.
- O pilar `fillers` continua existindo, com a mesma fórmula quando não há detecções novas.
  Os campos novos do payload são opcionais: sessões antigas continuam válidas.

## Definições (constantes em `speech_analysis.py`, calibráveis)
| Constante | Valor inicial | Papel |
|---|---|---|
| `VICE_MIN_PER_MIN` | `2.0` | taxa mínima (ocorrências/min de fala) para virar vício |
| `VICE_MIN_COUNT` | `3` | contagem absoluta mínima (evita falso positivo em fala curta) |
| `VICE_MAX_NGRAM` | `3` | maior n-grama considerado |
| `VICE_BOUNDARY_GAP` | `0.25` | s de silêncio que marca fronteira de enunciado |
| `VICE_BOUNDARY_RATIO` | `0.6` | fração mínima de ocorrências em fronteira |
| `DISCOURSE_MARKERS` | conjunto | sementes de marcadores discursivos (abaixo) |
| `VICE_STOPWORDS` | conjunto | palavras funcionais que nunca formam vício sozinhas |
| `PLEONASMS` | lista | entradas `{padrao, termo, sugestao}`; ver AC-6 |

- `DISCOURSE_MARKERS`: "então", "basicamente", "tipo assim", "na verdade", "entendeu",
  "sabe", "tá", "beleza", "enfim", "aí", "literalmente", "meio que", "vamos dizer assim".
- `VICE_STOPWORDS`: `retrieval.STOP_WORDS` + pronomes, artigos, preposições, conjunções e
  verbos de ligação ("eu", "ele", "é", "foi", "tem", "mas", "não", "já", "mais", "muito",
  "também", "quando", "onde", "porque", "aqui", "lá", "este", "esta", "pelo", "pela").

- **Normalização:** minúsculas, NFC, sem pontuação (mesma `_normalize` atual); a
  comparação de n-gramas e de pleonasmos ignora acentos.
- **Fronteira:** a ocorrência começa na primeira palavra da fala ou após silêncio
  ≥ `VICE_BOUNDARY_GAP`, ou termina na última palavra ou antes de silêncio ≥ esse valor.
- **Anti falso positivo (stopwords):** um n-grama é descartado se **todas** as suas palavras
  estão em `VICE_STOPWORDS`, se for unigrama com ≤ 2 letras, ou se contiver um número.
  Fora das sementes, só vira vício se também passar no critério de fronteira, o que exclui
  palavras de conteúdo do tema (ex.: "projeto" repetido no meio das frases).

## Critérios de aceite
- **AC-1:** Dado `analyze_words(words)`, então o resultado contém `occurrences: list[dict]`
  ordenada por `start`; cada item tem `term`, `kind`, `excerpt`, `start`, `end`,
  `suggestion` (str não vazia) e `source` (`lexico` | `estatistica` | `llm`). `start` é o
  `start` da primeira palavra e `end` o `end` da última palavra da ocorrência.
- **AC-2:** Toda palavra em que `is_filler` é verdadeiro gera uma ocorrência
  `kind="vicio_fixo"`, `source="lexico"`, sugestão "Troque por um silêncio curto e
  respire." O conjunto `FILLER_WORDS` e `is_filler` não mudam.
- **AC-3:** Dado um n-grama de `DISCOURSE_MARKERS` com contagem ≥ `VICE_MIN_COUNT` e taxa
  ≥ `VICE_MIN_PER_MIN`, então cada ocorrência vira `vicio_detectado` com
  `source="estatistica"`; com taxa abaixo do limiar (ex.: "então" 2× em 2 min), nenhuma.
- **AC-4:** Dado um n-grama fora das sementes (ex.: "de fato") com contagem e taxa acima dos
  limiares e ≥ `VICE_BOUNDARY_RATIO` das ocorrências em fronteira, então vira
  `vicio_detectado`; dado "projeto" 8× sempre no meio de frases (sem silêncio antes/depois),
  então **não** vira; dado "de que" 8× (só stopwords), então **não** vira.
- **AC-5:** Sobreposição: o maior n-grama vence. Dado "tipo assim" detectado, as palavras
  dentro dele não geram outra ocorrência de "tipo" (fixo) nem de "assim"; cada palavra da
  transcrição pertence a no máximo uma ocorrência de vício.
- **AC-6:** `PLEONASMS` contém pelo menos: "subir pra/para cima" → "subir", "descer pra/para
  baixo" → "descer", "elo de ligação" → "elo", "surpresa inesperada" → "surpresa",
  "há … anos atrás" → "há … anos" ou "… anos atrás", "encarar de frente" → "encarar",
  "entrar pra dentro" → "entrar", "sair pra fora" → "sair", "repetir de novo" → "repetir",
  "planejar antecipadamente" → "planejar", "fato real" → "fato", "consenso geral" →
  "consenso". O
  padrão aceita flexão do verbo por radical (ex.: "subiu pra cima", "subimos para cima") e,
  em "há … atrás", até 2 palavras entre "há" e "atrás".
- **AC-7:** Dado um pleonasmo do léxico na fala, então há uma ocorrência `kind="pleonasmo"`,
  `source="lexico"`, `term` = palavras literais da fala, `suggestion` = forma corrigida, e
  tempos das palavras casadas. Pleonasmo não conta como vício (pode coexistir com AC-5).
- **AC-8:** `excerpt` = até 4 palavras antes + o termo + até 4 depois, unidas por espaço,
  copiadas da transcrição (nunca geradas).
- **AC-9:** Verificação por LLM é opcional: `analyze_words(..., pleonasm_checker=None)`. Sem
  checker (padrão) nenhuma chamada externa é feita. O checker é um callable
  `(text: str, candidates: list[dict]) -> {"confirmed": [int], "suggested":
  [{"trecho": str, "sugestao": str}]}`; a API só o liga se `SPEECH_PLEONASM_LLM=true`.
- **AC-10:** Candidato confirmado pelo checker ganha `confirmed_by_llm=True`; os não
  confirmados permanecem (o léxico é determinístico) com `confirmed_by_llm=False`. Sem
  checker o campo é `None`.
- **AC-11:** Sugestão do checker vira ocorrência `source="llm"` somente se o `trecho`
  normalizado existir como sequência contígua de palavras da transcrição; senão é
  descartada. Sugestões que coincidem com um pleonasmo já achado não duplicam.
- **AC-12:** Se o checker levantar exceção ou devolver formato inválido, a análise segue
  só com o léxico (mesmo resultado de AC-7) e nada é propagado.
- **AC-13:** Pilar `fillers`: `rate = 100 × palavras em vícios (fixo + detectado) / total de
  palavras`; `score = clamp(100 − 5 × rate − 3 × pleonasmos)`, com a parcela de pleonasmos
  limitada a 15 pontos. `counts` passa a incluir os termos detectados (termo → contagem);
  novo campo `pleonasms: int`. Sem detecções novas, `value`, `score`, `label` e `counts`
  são idênticos aos de hoje (testes da spec 002 seguem verdes).
- **AC-14:** `pace` continua usando só `is_filler` para excluir palavras (vícios detectados
  não mudam o ritmo); o índice geral continua sendo a média dos 4 pilares.
- **AC-15:** API: `SessionResult` ganha `occurrences: list[Occurrence] | None = None`;
  `Word` ganha `kind: Literal["vicio_fixo", "vicio_detectado", "pleonasmo"] | None = None`;
  `Pillar` ganha `pleonasms: int | None = None`. `filler` em `Word` passa a ser verdadeiro
  para vício fixo **ou** detectado. Uma sessão salva antes desta spec (sem os campos) é
  devolvida por `GET /v1/sessions/{id}` sem erro.
- **AC-16:** O detalhe e o "próximo passo" do pilar `fillers` citam o termo mais frequente
  entre fixos e detectados; se só houver pleonasmos, o próximo passo cita o primeiro com a
  sugestão (ex.: "Troque “subir pra cima” por “subir”.").

## Fora de escopo
- Lista de pleonasmos editável pelo usuário; outros vícios gramaticais (gerundismo,
  concordância); detecção em tempo real; cálculo de vícios no front.

## Impacto esperado
- Score de `fillers` (e o índice geral) cai em falas com marcadores repetidos; o histórico
  antigo não é recalculado. Calibrar `VICE_*` com gravações reais antes de aprovar.

## Plano (preenchido depois da aprovação)
| Passo | Arquivo | Subagente | Verificação |
|---|---|---|---|
| 1 | `tests/test_speech_analysis.py` | engenheiro-ia | vermelhos por AC-1…AC-14 |
| 2 | `src/rag_cognus/speech_analysis.py` | engenheiro-ia | `check.py --changed` |
| 3 | `tests/test_api.py`, `api/schemas.py`, `api/app.py` | engenheiro-ia | AC-15, AC-16 |
