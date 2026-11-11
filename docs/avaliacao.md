# Método de avaliação do RAG Cognus

O objetivo é distinguir falha de recuperação de falha da geração. A aplicação usa
somente a visão Gold elegível, preserva fonte, público e identificadores e não
transforma conteúdo fonoaudiológico em diagnóstico ou prescrição.

## Experimento reproduzível

Cada run registra backend, k, modelo, threshold denso, versão da Gold, fingerprint
do conteúdo, dataset usado, versões dos pacotes, tempo de construção do índice,
resultados por pergunta e traces com spans `RETRIEVER` e de geração. A leitura local
usa a Statement Execution API com paginação e um snapshot cujo hash é verificado.

A versão Silver registrada na Gold identifica sua origem; o fingerprint registra
os trechos exatos desta execução. Compare runs que usam o mesmo snapshot e casos.
Mudanças na Gold podem exigir revisar os IDs esperados antes de medir novamente.

## Métricas e denominadores

| Métrica | Definição | Condição |
|---|---|---|
| Precision@k | IDs relevantes recuperados / k solicitado | Referências humanas não vazias |
| Recall@k | IDs relevantes recuperados / total de IDs relevantes anotados | Mesmo conjunto de referência |
| Hit@k | 1 se algum ID relevante apareceu, 0 caso contrário | Referências humanas |
| MRR@k | Inverso da posição do primeiro ID relevante | Referências humanas |
| Abstenção | Concordância com `should_abstain` | Expectativa humana explícita |
| Integridade da citação | IDs citados pertencem ao contexto; resposta não abstida cita pelo menos um | Somente respostas de RAG |
| Proxy de nicho | Fração dos resultados com o nicho esperado nos metadados | Não mede relevância semântica |
| Latência | Tempo por pergunta, incluindo instrumentação | Não inclui construção do índice |

Um caso sem referências não vira nota zero nem nota um de recuperação: não é
pontuado nessas métricas. O run informa tamanho da amostra por métrica e quantidade
de casos revisados. IDs repetidos não recebem crédito extra.

Os IDs são trechos sobrepostos. Anotações devem incluir todos os trechos aceitos
como relevantes; referências incompletas prejudicam a interpretação de precisão
e recall. Na revisão, confira também diversidade de documentos e redundância.

## Linha de base e modelo local

BM25 normaliza acentos apenas para busca e retira uma lista pequena de palavras
funcionais. A negação não é retirada. Apenas scores positivos são devolvidos.
A alternativa densa usa `embeddinggemma:latest`, com similaridade cosseno e threshold
inicial de 0,3. Esse threshold é um parâmetro inicial, não um valor validado.
Os rótulos esperados não são inseridos como filtro nas perguntas iniciais.

O Qwen3.5 9B recebe pergunta, trechos e metadados. Retorna JSON estruturado com
resposta, indicação de apoio e IDs citados. Citações inventadas ou resposta afirmativa
sem fontes causam erro explícito. Sem contexto, o pipeline se abstém sem chamar o modelo.
Isso reduz alguns erros de estrutura; não garante que cada afirmação esteja apoiada.

## Métricas de qualidade da resposta (juiz local)

`rag-cognus evaluate --generate --judge` e o botão **Avaliar respostas** do chat usam
um juiz local (Ollama) que, em uma única chamada, dá notas inteiras de 1 a 5:

| Métrica | Pergunta que responde |
|---|---|
| `context_relevance` | Os trechos recuperados são pertinentes à pergunta? (qualidade da busca) |
| `groundedness` | Cada afirmação da resposta tem apoio nos trechos? |
| `answer_relevance` | A resposta atende diretamente ao que foi perguntado? |
| `accuracy` | A informação está correta e completa? Usa `expected_facts` quando existem; senão, os trechos. |
| `professionalism` | Tom, clareza, português correto, organização, sem diagnóstico ou prescrição. |
| `quality_score` | Média simples das cinco notas. |

No MLflow, cada pergunta vira um trace com as notas e o motivo de cada uma
(aba **Traces/Evaluations** do run); as médias aparecem como `accuracy/mean`,
`professionalism/mean` etc., comparáveis entre runs no gráfico do experimento.

Por padrão o juiz é o mesmo modelo que gera as respostas, o que traz viés de
autoavaliação. Configure `OLLAMA_JUDGE_MODEL` com outro modelo para comparar.
As notas são exploratórias e não substituem revisão humana: observe apoio factual
por afirmação, adequação ao público da fonte e abstenção quando a base não sustenta
a resposta. Um piloto sem rótulos não estabelece acurácia nem validação clínica.

## Próximos testes

1. Revisar e anotar perguntas de todos os nichos, incluindo casos fora do escopo.
2. Separar perguntas de desenvolvimento e teste; não calibrar parâmetros no teste final.
3. Comparar BM25 e embeddings com o mesmo k e snapshot.
4. Comparar k=3/k=5, threshold e diversidade por documento.
5. Revisar respostas e autoavaliações; ampliar o conjunto antes de definir metas.

## Referências

- [MLflow: avaliação de RAG](https://mlflow.org/docs/latest/genai/eval-monitor/scorers/llm-judge/rag/): separação entre recuperação e resposta, com rastros de recuperação.
- [MLflow: scorers customizados](https://mlflow.org/docs/latest/genai/eval-monitor/scorers/custom/): métricas programáticas e juízes locais.
- [LangChain: ChatOllama](https://docs.langchain.com/oss/python/integrations/chat/ollama): integração ao modelo local.
- [LangChain: vector stores](https://docs.langchain.com/oss/python/integrations/vectorstores/index): documentos, metadados e filtros.

A escolha de k, threshold, perguntas e critérios de aprovação é local ao projeto.
As referências não demonstram que os parâmetros iniciais sejam ótimos para esse acervo.

## Executar localmente

`rag-cognus mlflow-local` inicia o MLflow open source em `127.0.0.1:5001`, com banco
e artefatos em `.cache/mlflow`. URIs `databricks://` são recusadas de propósito.
Resultados, perguntas e contexto completos permanecem locais, fora do repositório.
