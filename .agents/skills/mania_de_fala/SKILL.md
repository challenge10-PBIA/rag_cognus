# Documentação da Skill: rag-manias-de-fala

## 1. Identificação

- **Nome:** `rag-manias-de-fala`
- **Categoria:** Especialização de recuperação e geração de respostas.
- **Domínio:** Comunicação oral, vícios de linguagem, muletas verbais e hesitações.
- **Arquivo:** `hermes/skills/rag-manias-de-fala/SKILL.md`

## 2. Objetivo

A skill `rag-manias-de-fala` tem como objetivo orientar o COGNUS no tratamento de perguntas relacionadas a manias de fala, como o uso frequente de expressões como "né", "tipo", hesitações, pausas preenchidas e velocidade da fala.

Sua principal finalidade é garantir que as respostas sejam fundamentadas no conhecimento disponível no acervo, evitando interpretações equivocadas, generalizações e recomendações sem evidências.

A skill também estabelece uma distinção importante entre muletas verbais e gagueira, evitando que comportamentos comuns da comunicação oral sejam tratados como condições clínicas.

## 3. Problema identificado

Consultas sobre manias de fala podem apresentar dificuldades para o mecanismo de recuperação de documentos do RAG.

Por exemplo:

- **Consulta do usuário:** "Como parar de falar tipo e né?"
- **Termos utilizados no acervo:** "vícios de linguagem", "muletas verbais" ou "marcadores conversacionais".

Como o mecanismo BM25 realiza correspondência lexical, diferenças entre os termos utilizados pelo usuário e aqueles presentes nos documentos podem prejudicar a recuperação.

Isso pode resultar em respostas incompletas ou em abstenções mesmo quando existem documentos potencialmente relevantes no acervo.

## 4. Estratégia de funcionamento

A skill estabelece três etapas principais.

### 4.1. Verificação do conhecimento disponível

Antes de propor melhorias na recuperação ou no comportamento da LLM, deve-se verificar se o acervo realmente possui documentos relacionados ao tema.

A verificação utiliza o arquivo `.cache/gold.jsonl`, considerando termos como:

- Vício de linguagem;
- Muleta verbal;
- Marcador conversacional;
- Pausa preenchida;
- Hesitação;
- Repetição;
- Ritmo;
- Velocidade da fala.

Quando não existem trechos relevantes, o comportamento esperado é a abstenção.

A ausência de conhecimento não deve ser compensada pela criação de regras de prompt ou recomendações sem fundamentação.

Quando existem documentos relevantes, devem ser registrados seus identificadores (`chunk_id`), títulos (`title`) e públicos-alvo (`audience`).

### 4.2. Melhoria da recuperação de documentos

A skill propõe uma expansão de consulta por tema para melhorar a recuperação lexical.

Exemplo:

| Consulta original | Termos relacionados |
|---|---|
| Mania de fala | Vício de linguagem |
| Falar muito "tipo" | Muleta verbal |
| Usar muito "né" | Marcador conversacional |
| Ficar falando "ééé" | Hesitação |
| Fazer pausas preenchidas | Pausa preenchida |

Essa estratégia busca aproximar a linguagem utilizada pelo usuário da terminologia presente nos documentos.

A implementação deve ocorrer no mecanismo de recuperação, especialmente no componente responsável pelo processamento das consultas (`retrieval.py`).

### 4.3. Orientação para geração das respostas

As respostas devem apresentar um tom prático, respeitoso e sem julgamentos.

O COGNUS deve:

- Tratar manias de fala como comportamentos comuns da comunicação oral.
- Evitar classificar esses comportamentos como defeitos ou doenças.
- Não confundir muletas verbais com gagueira.
- Utilizar estratégias de melhoria somente quando estiverem fundamentadas nos documentos recuperados.
- Preservar o contexto e o público-alvo das fontes.
- Evitar prescrições, frequências obrigatórias de treinamento e planos terapêuticos.
- Recomendar avaliação com fonoaudiólogo quando o usuário relatar dificuldades persistentes, respeitando os limites definidos pela skill `rag-fronteira-oratoria-fono`.

## 5. Integração com a arquitetura multiagentes

Na arquitetura multiagentes proposta para o COGNUS, essa skill pode orientar diferentes etapas do processamento.

| Componente | Responsabilidade |
|---|---|
| Query Understanding | Identificar perguntas relacionadas a manias de fala e compreender a intenção do usuário. |
| Knowledge Retrieval | Aplicar expansão temática das consultas para melhorar a recuperação. |
| Research Agent | Recuperar documentos relevantes e verificar se existe conhecimento suficiente. |
| Validation Agent | Verificar a fundamentação da resposta e a distinção entre muletas verbais e questões clínicas. |
| Orchestrator | Coordenar as etapas e determinar se o sistema deve responder ou se abster. |

A skill funciona como uma especialização de domínio, enquanto os agentes executam as responsabilidades técnicas do fluxo.

Sua integração efetiva depende de um mecanismo de carregamento e disponibilização das instruções para os componentes correspondentes.

## 6. Critérios de aceitação e testes

A skill propõe três critérios para validar a expansão de consultas.

**AC-1 — Recuperação de documentos relacionados**

A consulta "como parar de falar tipo e né" deve recuperar um documento de teste cujo conteúdo aborda "vícios de linguagem".

**AC-2 — Preservação de consultas não relacionadas**

A expansão temática não deve modificar os resultados de consultas pertencentes a outros assuntos.

**AC-3 — Preservação do processamento lexical**

Devem continuar funcionando as regras existentes de tokenização, incluindo normalização de acentos, preservação da negação e geração de scores positivos.

Os testes devem ser executados sem dependência de rede, utilizando documentos de teste (fixtures).

Arquivo de testes previsto: `tests/test_retrieval.py`.

## 7. Casos de avaliação

A skill também propõe casos para avaliação do comportamento do COGNUS:

1. O que são vícios de linguagem na fala em público?
2. Como reduzir o uso de "né" e "tipo" ao apresentar?
3. Por que dizemos "ééé" quando ficamos nervosos?
4. A pausa em silêncio ajuda a evitar muletas verbais?
5. Falar rápido demais prejudica a apresentação?
6. Muleta verbal é sinal de gagueira?
7. Quantas vezes por dia devo treinar para parar de falar "tipo"?

Os casos devem permanecer com `label_status: draft` até que o conteúdo do acervo seja verificado.

O campo `should_abstain` deve permanecer nulo até a análise dos documentos e a definição do gabarito correspondente.

## 8. Relação com outras skills

A `rag-manias-de-fala` possui responsabilidades específicas e complementares a outras especializações do COGNUS.

| Skill | Responsabilidade |
|---|---|
| `communication-training` | Desenvolver habilidades comunicativas por meio de exercícios e feedback. |
| `rag-fronteira-oratoria-fono` | Estabelecer limites entre orientações de comunicação e conteúdo clínico. |
| `rag-manias-de-fala` | Orientar a recuperação e a geração de respostas sobre vícios de linguagem e hesitações. |

Essa separação evita duplicação de responsabilidades e permite que cada especialização contribua para uma etapa diferente da experiência do usuário.

## 9. Benefícios esperados

A implementação dessa especialização pode proporcionar:

- Melhor recuperação de documentos relacionados a manias de fala.
- Maior correspondência entre a linguagem do usuário e a terminologia do acervo.
- Redução de abstenções causadas por diferenças vocabulares.
- Respostas mais contextualizadas e fundamentadas.
- Menor risco de confundir comportamentos comunicativos com condições clínicas.
- Maior controle sobre os limites das orientações oferecidas pelo COGNUS.

## 10. Considerações finais

A skill `rag-manias-de-fala` representa uma especialização do conhecimento e do comportamento do COGNUS em um tema específico da comunicação oral.

Seu diferencial não está apenas em orientar a geração de respostas, mas também em identificar limitações do mecanismo de recuperação e propor melhorias técnicas verificáveis.

A implementação deve respeitar a disponibilidade real de conhecimento no acervo, preservar o comportamento atual para consultas não relacionadas e garantir que todas as orientações sejam fundamentadas nas evidências recuperadas.

Dessa forma, a skill contribui para tornar o COGNUS um sistema mais especializado, confiável e consistente na orientação sobre comunicação.