# 015 — Catálogo fonético normalizado da Gold

- **Status:** implementado
- **Módulos:** `phonetics.py`, `api/app.py`, `api/schemas.py`
- **Testes:** `tests/test_phonetics.py`

## Problema
O guia fonético mantinha exercícios no frontend, separados da base RAG. A seleção por
letra não distingue o tepe /ɾ/, a lateral /l/ e as realizações regionais do R forte.

## Comportamento esperado
A API entrega exercícios estruturados da Gold de fonética, com passos específicos,
proveniência e chave de animação explícita. O mesmo snapshot alimenta a recuperação RAG.
Ausência ou inconsistência da base é informada, sem substituir por um exercício genérico.

## Critérios de aceite
- **AC-1:** Catálogo válido preserva os alvos e passos distintos de /ɾ/ e /l/.
- **AC-2:** Alvo e animação incompatíveis, IDs duplicados ou conteúdo incompleto são rejeitados.
- **AC-3:** Lista e detalhe usam o snapshot validado; alvo desconhecido retorna 404.
- **AC-4:** Snapshot ausente retorna 503, sem exercícios estáticos de fallback.
- **AC-5:** O recuperador une os documentos fonéticos aos documentos Gold gerais.
- **AC-6:** A sessão persiste o exercício escolhido e seu alvo explícito, rejeita IDs
  desconhecidos e não infere erro articulatório da transcrição.
- **AC-7:** Marcar exercício fonético como hábito aceita IDs do mesmo catálogo Gold.

## Fora de escopo
Diagnóstico automático de fonemas, prescrição clínica e escrita remota no Databricks.

## Plano
Testar com snapshots sintéticos, implementar validação e endpoints, executar harness.
