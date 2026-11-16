---
name: knowledge-retrieval
description: Orienta a preparação, execução e avaliação da recuperação de conhecimento do COGNUS, considerando tanto as dúvidas dos usuários quanto seus objetivos de desenvolvimento em comunicação.
---

# Knowledge Retrieval

## 1. Objetivo

Orientar o processo de recuperação de conhecimento para encontrar documentos relevantes, relacionados à intenção do usuário e adequados ao contexto da pergunta.

Além de recuperar informações para responder dúvidas, esta skill deve apoiar a atuação do COGNUS como mentor e especialista em comunicação.

A recuperação deve considerar conhecimentos que permitam explicar conceitos, apresentar estratégias, sugerir práticas e orientar o desenvolvimento das habilidades comunicativas.

## 2. Responsabilidades

A skill deve:

- Utilizar a pergunta interpretada pela skill Query Understanding.
- Identificar os termos centrais da consulta.
- Identificar conceitos relacionados ao assunto pesquisado.
- Considerar sinônimos e variações linguísticas.
- Preservar o contexto e o nicho de conhecimento identificado.
- Orientar a construção de consultas claras e específicas.
- Considerar a relevância dos documentos recuperados.
- Identificar diferentes necessidades de conhecimento do usuário.
- Sinalizar quando os documentos encontrados forem insuficientes.
- Priorizar documentos que contribuam para o objetivo comunicativo apresentado.

## 3. Processo de recuperação

Siga estas etapas:

1. Receba a pergunta original e a consulta interpretada.
2. Identifique os conceitos fundamentais da busca.
3. Identifique termos alternativos, sinônimos e expressões relacionadas.
4. Preserve o nicho de conhecimento identificado.
5. Identifique o objetivo do usuário: compreender, solucionar uma dificuldade, desenvolver uma habilidade ou praticar.
6. Prepare consultas adequadas à necessidade identificada.
7. Utilize o Retriever disponível no sistema.
8. Analise a relação entre os documentos recuperados e a pergunta original.
9. Identifique possíveis lacunas na recuperação.
10. Encaminhe os documentos relevantes para a etapa de análise de evidências.

## 4. Estratégias de busca

### 4.1. Busca por termos principais

Priorize palavras e expressões diretamente relacionadas à pergunta.

### 4.2. Busca por sinônimos

Considere diferentes formas de expressar o mesmo conceito.

### 4.3. Busca contextual

Considere o contexto da pergunta para evitar recuperar documentos que contenham palavras semelhantes, mas tratem de assuntos diferentes.

### 4.4. Busca por nicho

Utilize o nicho identificado para restringir a recuperação quando esse filtro estiver disponível no Retriever.

### 4.5. Busca complementar

Quando os resultados forem insuficientes, considere reformular a consulta com termos relacionados, sem alterar a intenção original.

### 4.6. Recuperação orientada ao desenvolvimento comunicativo

Quando o usuário demonstrar interesse em desenvolver uma habilidade de comunicação, considere recuperar conhecimentos relacionados a:

- Fundamentos e conceitos da habilidade.
- Possíveis fatores que influenciam a dificuldade apresentada.
- Estratégias e técnicas de desenvolvimento.
- Exercícios e atividades práticas.
- Exemplos de aplicação em situações reais.
- Critérios de observação e avaliação da habilidade.

Não presuma que todos esses tipos de conteúdo existem na base. Recupere somente o que estiver disponível e sinalize eventuais lacunas.

## 5. Dimensões de conhecimento

Considere quatro dimensões para orientar a recuperação:

### 5.1. Conhecimento conceitual

Documentos que expliquem conceitos, fundamentos e características relacionadas à comunicação.

Exemplos:
- Fundamentos da oratória.
- Clareza e organização da linguagem.
- Comunicação assertiva.
- Características da fluência verbal.

### 5.2. Estratégias de desenvolvimento

Documentos que apresentem técnicas e orientações para desenvolver habilidades comunicativas.

Exemplos:
- Estratégias para estruturar apresentações.
- Técnicas de organização de ideias.
- Orientações para melhorar a comunicação interpessoal.
- Estratégias de preparação para falar em público.

### 5.3. Prática e aplicação

Documentos que apresentem exercícios, atividades e situações de aprendizagem.

Exemplos:
- Exercícios de expressão oral.
- Atividades de organização da fala.
- Práticas de comunicação em situações profissionais.
- Simulações de apresentações.

### 5.4. Avaliação e acompanhamento

Documentos que apresentem critérios para observar o desempenho e identificar oportunidades de melhoria.

Exemplos:
- Critérios de clareza e objetividade.
- Indicadores de organização da fala.
- Parâmetros de avaliação de apresentações.
- Orientações para feedback comunicativo.

## 6. Critérios de relevância

Um documento deve ser considerado relevante quando:

- Apresentar relação direta com a pergunta.
- Abordar o assunto central da consulta.
- Estiver alinhado ao nicho identificado.
- Contiver informações úteis para responder à solicitação.
- Apresentar contexto suficiente para interpretação.
- Contribuir para o objetivo de aprendizagem ou desenvolvimento, quando aplicável.

A presença de palavras semelhantes, isoladamente, não significa que um documento seja relevante.

A relevância deve ser avaliada considerando tanto a correspondência com a pergunta quanto a utilidade do conteúdo para a necessidade comunicativa apresentada.

## 7. Restrições

- Não invente documentos ou fontes.
- Não considere um documento relevante apenas pela correspondência de palavras.
- Não altere a intenção original da pergunta.
- Não utilize conhecimento externo como se tivesse sido recuperado da base.
- Não crie respostas nesta etapa.
- Não descarte documentos relevantes sem justificativa.
- Não considere a recuperação bem-sucedida quando os documentos não sustentarem a pergunta.
- Não presuma que existem exercícios ou estratégias específicos na base.
- Não transforme sugestões de busca em afirmações sobre a eficácia de uma técnica.
- Não confunda recuperação de conhecimento com avaliação clínica ou diagnóstico.

## 8. Entrada esperada

A skill pode receber:

- Pergunta original do usuário.
- Consulta interpretada.
- Intenção identificada.
- Nicho de conhecimento.
- Objetivo comunicativo do usuário, quando disponível.
- Resultados retornados pelo Retriever, quando disponíveis.

## 9. Saída esperada

O processo deve disponibilizar:

- `search_query`: consulta utilizada na recuperação.
- `search_terms`: termos principais e relacionados.
- `niche`: nicho utilizado como filtro, quando aplicável.
- `retrieval_dimensions`: dimensões de conhecimento relevantes para a consulta.
- `retrieved_documents`: documentos recuperados.
- `relevant_documents`: documentos considerados relevantes.
- `retrieval_sufficient`: indicação de suficiência dos resultados.
- `missing_information`: informações que não foram encontradas.

As dimensões de recuperação podem incluir:

- `conceptual_knowledge`
- `development_strategies`
- `practical_exercises`
- `evaluation_criteria`

Esses campos representam a orientação da recuperação e não garantem que o Retriever implemente filtros específicos para cada dimensão.

## 10. Critérios de qualidade

A recuperação será considerada adequada quando:

- Os documentos apresentarem relação com a pergunta.
- A consulta preservar a intenção do usuário.
- O nicho utilizado for compatível com o assunto.
- Os resultados contiverem informações úteis para a análise.
- As dimensões de conhecimento forem compatíveis com o objetivo do usuário.
- A insuficiência de evidências for identificada corretamente.
- Nenhuma fonte ou informação for inventada.
- O conteúdo recuperado puder sustentar as orientações que serão produzidas pelo COGNUS.

## 11. Exemplo de aplicação

**Pergunta do usuário:**

"Tenho dificuldade para organizar minhas ideias quando preciso apresentar um projeto. Como posso melhorar?"

**Consulta principal:**

"organização de ideias, estruturação de apresentações, clareza e sequência lógica da comunicação oral."

**Nicho:**

`apresentacoes_oratoria`

**Dimensões de recuperação:**

- `conceptual_knowledge`: fundamentos da organização de apresentações.
- `development_strategies`: técnicas para estruturar ideias e organizar discursos.
- `practical_exercises`: atividades para praticar introdução, desenvolvimento e conclusão.
- `evaluation_criteria`: critérios para observar clareza, coerência e organização.

**Resultado esperado:**

Recuperar documentos que ajudem o COGNUS a explicar como organizar uma apresentação, apresentar estratégias aplicáveis e propor exercícios quando houver material disponível na base.

O COGNUS deverá utilizar os documentos recuperados para fundamentar sua orientação, identificando eventuais informações ausentes antes de formular recomendações.