# Método de avaliação do RAG Cognus

O objetivo é distinguir falha de recuperação de falha da geração. A aplicação usa
somente a visão Gold elegível, preserva fonte, público e identificadores e não
transforma conteúdo fonoaudiológico em diagnóstico ou prescrição.

## Experimento reproduzível

Cada run registra backend, k, modelo, threshold denso, versão da Gold, fingerprint
do conteúdo, dataset usado, versões dos pacotes, tempo de construção do índice,
resultados por pergunta e traces com spans `RETRIEVER` e de geração. A leitura local
usa a Statement Execution API com paginação e um snapshot cujo hash é verificado.
A leitura no Databricks usa Spark sobre a mesma visão.

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

## Juiz opcional e avaliação humana

O juiz local usa um scorer customizado de `mlflow.genai.evaluate`, com contexto e
resposta reais. O escore `local_groundedness` é autoavaliação do Qwen e não uma nota
humana. `local_correctness` compara a resposta com `expected_facts` somente quando
os fatos estiverem presentes e o caso tiver `label_status=human_verified`; nos
rascunhos retorna `not_scored`, sem chamar o modelo para essa comparação. Abstenções ficam como `not_scored`. A configuração identifica o mesmo modelo
como gerador e juiz, permitindo substituir esse juiz em comparações posteriores.

A revisão humana deve observar: apoio factual por afirmação, pertinência à pergunta,
adequação ao público da fonte, fidelidade das citações, suficiência do contexto e
abstenção quando a base não sustenta a resposta. Um piloto sem rótulos não estabelece
acurácia nem validação clínica. Não foi treinado ou ajustado nenhum modelo.

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

O comando `rag-cognus mlflow-local` inicia API e interface em `127.0.0.1:5000`,
com banco e artefatos em `.cache/mlflow`. O padrão de tracking da aplicação é
esse endpoint HTTP. `python scripts/eval_local.py --judge` registra comparação
k=3/k=5, respostas Qwen e os scorers de groundedness e correção condicional a
referências humanas. Resultados, perguntas e contexto completos permanecem
locais, fora do repositório público.
