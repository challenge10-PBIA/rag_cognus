# Resultados iniciais — 09/11/2026

Execuções reais com os 728 trechos elegíveis da Gold. Todos os casos ainda têm referências em rascunho.

| Execução | Perguntas | Erros | Observação |
|---|---:|---:|---|
| BM25 k=3 | 14 | 0% | Recuperação exploratória, sem Precision/Recall humano. |
| BM25 k=5 | 14 | 0% | Recuperação exploratória, sem Precision/Recall humano. |
| EmbeddingGemma k=5 | 14 | 0% | Recuperação exploratória, sem Precision/Recall humano. |
| Qwen3.5 9B + BM25 k=5 | 2 | 0% | Citações presentes no contexto em 2/2 respostas; não é correção factual. |

Sem referências humanas, estes resultados não permitem afirmar uma porcentagem de acerto do RAG.
Os proxies e as latências por pergunta estão no MLflow. Os testes locais cobrem 16 comportamentos;
o notebook Databricks também foi executado com sucesso.


A indexação densa foi dividida em lotes de 16 após o servidor Ollama falhar com o lote único.
Essa correção foi testada com o corpus real; nenhum trecho foi descartado para fazê-la passar.

O comando de juiz foi validado com uma resposta real.
a comparação contra fatos esperados ficou sem pontuação por falta de referências
humanas. Essa execução verifica a integração, não estabelece qualidade geral.
