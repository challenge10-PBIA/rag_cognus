---
name: query-understanding
description: Interpreta a intenção do usuário, identifica o contexto e prepara consultas para a recuperação de conhecimento do COGNUS.
---

# Query Understanding

## 1. Objetivo

Compreender a solicitação do usuário antes de iniciar a recuperação de informações na base de conhecimento do COGNUS.

Esta skill deve ajudar a LLM a identificar o que o usuário deseja saber, preservar o contexto da conversa e preparar uma consulta adequada para o mecanismo de recuperação (Retriever).

## 2. Responsabilidades

A skill deve:

- Identificar a intenção principal do usuário.
- Identificar o assunto central da pergunta.
- Considerar o histórico relevante da conversa.
- Identificar o nicho de conhecimento relacionado à pergunta.
- Detectar ambiguidades e informações insuficientes.
- Reformular a pergunta para facilitar a recuperação de documentos, quando necessário.
- Preservar o significado original da solicitação.

## 3. Nichos de conhecimento do COGNUS

Considere os seguintes nichos disponíveis:

- `apresentacoes_oratoria`
- `assertividade_escuta`
- `clareza_linguagem`
- `voz_saude_vocal`
- `fluencia_gagueira`
- `fono_contextos_profissionais`

A identificação do nicho deve considerar o significado da pergunta, e não apenas palavras isoladas.

Caso não seja possível identificar um nicho com segurança, sinalize a incerteza.

## 4. Processo de interpretação

Siga esta sequência:

1. Leia a pergunta original.
2. Identifique a intenção do usuário.
3. Identifique o assunto principal.
4. Consulte o contexto anterior, quando disponível.
5. Identifique o nicho mais relacionado.
6. Verifique se existem ambiguidades.
7. Reformule a consulta, caso isso facilite a recuperação.
8. Encaminhe a consulta para o processo de recuperação de conhecimento.

## 5. Restrições

- Não responda à pergunta nesta etapa.
- Não invente informações ou contexto.
- Não altere a intenção original do usuário.
- Não presuma informações que não foram fornecidas.
- Não escolha um nicho sem considerar o contexto.
- Não descarte detalhes importantes da pergunta.
- Não confunda a interpretação da pergunta com a validação das evidências.

## 6. Entrada esperada

A skill pode receber:

- Pergunta original do usuário.
- Histórico relevante da conversa, quando disponível.

## 7. Saída esperada

A interpretação deve produzir uma estrutura com os seguintes campos:

- `original_query`: pergunta original.
- `intent`: intenção identificada.
- `topic`: assunto principal.
- `niche`: nicho identificado ou indicação de incerteza.
- `rewritten_query`: consulta reformulada.
- `needs_clarification`: indica se é necessário solicitar esclarecimentos.
- `clarification_reason`: motivo do esclarecimento, quando aplicável.

## 8. Critérios de qualidade

A interpretação será considerada adequada quando:

- Preservar a intenção original.
- Identificar corretamente o assunto.
- Considerar o contexto relevante.
- Selecionar um nicho compatível.
- Não acrescentar informações não fornecidas.
- Identificar ambiguidades reais.
- Produzir uma consulta útil para a recuperação de conhecimento.

## 9. Exemplo

**Pergunta do usuário:**

"Como posso melhorar minha comunicação durante apresentações?"

**Interpretação esperada:**

- `intent`: obter orientações para melhorar a comunicação.
- `topic`: comunicação durante apresentações.
- `niche`: `apresentacoes_oratoria`.
- `rewritten_query`: estratégias para melhorar a comunicação oral, a clareza e a expressividade durante apresentações.
- `needs_clarification`: false.
- `clarification_reason`: null.
