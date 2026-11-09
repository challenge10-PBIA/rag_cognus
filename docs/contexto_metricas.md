# Como interpretar contexto, precisão e fontes no MLflow local

A avaliação é registrada exclusivamente no servidor local (`127.0.0.1:5000`).
A Gold continua sendo a origem dos documentos. Rótulos, textos, URLs das fontes,
respostas e resultados completos ficam nos artefatos locais, fora do Git público.

## Onde olhar

No experimento `rag-cognus`, abra **Evaluation** e o run
`local-contexto-fontes-evaluation`. Cada linha representa uma pergunta; as colunas
mostram indicadores e avaliações. No mesmo run, em **Artifacts**:

- `fontes_por_pergunta.json`: pergunta, posição do trecho, ID, título, URL, público,
  texto literal, uso na resposta e julgamento de relevância com justificativa.
- `metricas_por_pergunta.json`: indicadores numéricos por pergunta.
- `correlacoes_exploratorias.json`: associação descritiva entre indicadores.
- `correlacoes_exploratorias.png`: mapa visual com amostra e células sem dados sinalizadas.
- `metric_sample_counts.json`: quantidade de perguntas que receberam cada indicador.
- `context_evidence.json`: evidências completas para auditar a avaliação.
- `metodologia/contexto_metricas.md`: esta explicação junto do resultado.

A tabela de fontes diferencia **recuperado** de **citado na resposta**. Um título
com vários chunks continua sendo uma única fonte quando tem o mesmo `doc_id`.
URL e ID permitem conferir a origem; o projeto não deduz páginas de PDF ausentes.

## Métricas

| Métrica | Cálculo / significado | Tipo de evidência |
|---|---|---|
| `context_relevance_judge` | Trechos julgados pertinentes / trechos retornados | Estimativa Qwen, 0–1 |
| `context_precision_ranked_judge` | Average Precision: média de Precision@i nas posições relevantes, dividida pelo número de relevantes retornados | Estimativa Qwen sensível à ordem, 0–1 |
| `context_sufficiency_judge` | Juiz considera que o conjunto permite responder sem completar lacunas | Estimativa sem referência humana, 0 ou 1 |
| `answer_groundedness_judge` | Afirmações da resposta apoiadas no contexto | Estimativa Qwen; somente quando existe resposta pareada |
| `context_precision_human` | Trechos relevantes recuperados / k solicitado | Exige referências humanas e k conhecido |
| `context_recall_human` | Trechos relevantes recuperados / todos os trechos relevantes anotados | Exige referências humanas; é recall de chunks, não de fatos |
| `unique_sources` | Documentos distintos recuperados | Contagem verificável |
| `source_diversity` | Documentos distintos / trechos retornados | Indicador de distribuição de fontes |
| `context_redundancy_5gram` | 1 − união dos conjuntos de sequências de 5 palavras / soma do tamanho desses conjuntos por trecho | Repetição lexical entre trechos; não detecta toda duplicação semântica |
| `context_characters` | Soma dos caracteres dos trechos | Volume de contexto, não tokens |
| `cited_sources` | Fontes distintas citadas por IDs válidos | Contagem verificável; somente com resposta não abstida |
| `citation_source_coverage` | Fontes citadas / fontes recuperadas | Cobertura, não prova de atribuição factual |
| `citation_integrity` | IDs citados existem no contexto; resposta não abstida tem citação | Estrutura de citações, não correção das afirmações |
| `invalid_citations` | IDs citados ausentes dos trechos | Erro verificável |

Precisão por posição e fração relevante respondem perguntas diferentes. Por exemplo,
relevâncias `[sim, não, não]` produzem AP=1 e fração relevante=1/3. A AP mostra que
um trecho útil veio primeiro; não diz que todo o contexto era limpo. Um contexto
com todos os trechos irrelevantes recebe zero nesses dois indicadores do juiz.

O Qwen julga cada trecho em relação à pergunta, sem receber o nicho esperado como
resposta correta. O julgamento usa referências curtas C1, C2 etc., vinculadas aos IDs reais sem
alterar a Gold. O schema restringe os IDs permitidos e a quantidade de avaliações;
IDs omitidos, duplicados ou inventados geram erro. Há no máximo duas tentativas
para uma falha de identificação. Julgamentos validados ficam em cache local por
conteúdo, pergunta, resposta, versão do protocolo e digest do modelo, permitindo
retomada sem repetir chamadas já válidas.
A suficiência sem referências é apenas uma estimativa: não é o scorer de suficiência
com fatos esperados da biblioteca MLflow, nem uma validação clínica.

## Por que algumas colunas ficam sem pontuação?

As perguntas iniciais têm `label_status=draft`. Nesses casos, precisão e recall
humanos aparecem como `not_scored`. Isso não é zero, nem aprovação. Para calculá-los,
revise as fontes e registre `relevant_chunk_ids` com `label_status=human_verified`.
O conjunto de referência precisa ser suficientemente completo; rótulos incompletos
prejudicam a leitura de precisão e recall. Para execuções antigas sem k salvo,
informe `--k` explicitamente. As novas execuções já registram esse parâmetro.

Groundedness só é avaliada quando uma resposta foi anexada à mesma pergunta e ao
mesmo contexto, com a mesma sequência de IDs. O sistema rejeita misturar uma resposta
com trechos diferentes. Perguntas sem resposta não recebem nota fictícia de groundedness.
O mesmo Qwen gerando e julgando produz viés de autoavaliação, identificado nos tags.

## Relação entre as métricas e diagnóstico

| Padrão observado | Hipótese para investigar |
|---|---|
| Baixa relevância de contexto | Recuperação trouxe material pouco útil; revisar consulta, backend, filtros e referências |
| Boa relevância, mas baixa suficiência | Parte do assunto está presente, mas faltam elementos necessários; revisar cobertura da base |
| Contexto suficiente, resposta pouco apoiada | Investigar geração, prompt e uso das evidências |
| Resposta apoiada, contexto pouco pertinente | Uma resposta pode repetir corretamente textos que não resolvem a pergunta |
| AP alta, fração relevante baixa | Há material útil bem colocado e ruído no restante; comparar valores de k |
| Redundância alta | Investigar sobreposição, duplicação e diversidade dos resultados |
| Muitas fontes, baixa relevância | Quantidade de fontes não demonstra utilidade |
| Cobertura de citações baixa | Conferir se fontes úteis foram ignoradas; não exigir citar fontes irrelevantes |

A relação conceitual é: **pertinência da recuperação → suficiência do contexto →
uso fiel das evidências na resposta**, com verificação das fontes em cada etapa.
Nenhuma dessas condições isolada prova correção integral da resposta.

## Correlação estatística: o que calculamos e o que não concluímos

O artefato de correlações calcula Pearson por pares de indicadores da mesma pergunta,
dentro do mesmo conjunto de contextos. Só emite um número com pelo menos cinco pares
válidos e variação nas duas métricas. Sem isso, registra amostra insuficiente ou ausência
de variação. O limite de cinco é uma proteção técnica, não garantia de amostra adequada.

Mesmo com seis perguntas, qualquer correlação é **exploratória e instável**. Não há
inferência causal, teste de significância ou comprovação de generalização. Relevância
e AP usam os mesmos rótulos do juiz; parte da associação entre elas é matemática.
Muitas correlações simultâneas podem produzir associações ocasionais. É preciso ampliar
a amostra, incluir casos fora do escopo e usar avaliação independente.

Não usamos runs k=3 e k=5 da mesma pergunta como observações independentes. A amostra
piloto escolhe uma pergunta por nicho antes de completar o limite. Ela não comprova
cobertura de todos os casos difíceis ou das perguntas negativas.

## Executar

```bash
rag-cognus mlflow-local
python scripts/eval_local.py --generate-limit 2
```

Depois escolha um arquivo de recuperação em `outputs/` e, opcionalmente, um de respostas:

```bash
rag-cognus context-eval outputs/ID_RECUPERACAO.json \
  --answers outputs/ID_RESPOSTAS.json --judge --limit 6 --k 5
```

Os IDs reais permanecem locais. Abra a tabela Evaluation para navegar por pergunta;
abra os artefatos para ver a relação exata entre notas, trechos e fontes.

## Referências

- [MLflow: avaliação de RAG](https://mlflow.org/docs/latest/genai/eval-monitor/scorers/llm-judge/rag/): distinção entre recuperação, apoio da resposta e suficiência.
- [MLflow: scorers customizados](https://mlflow.org/docs/latest/genai/eval-monitor/scorers/custom/): avaliações programáticas e juízes customizados.

As fórmulas, o limite de amostra e o protocolo de contexto deste projeto são escolhas
locais. Não representam implementação do RAGAS nem garantias oferecidas pelo MLflow.
