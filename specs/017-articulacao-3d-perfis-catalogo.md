# 017 — Contrato estruturado de demonstração articulatória 3D por exercício

- **Status:** implementado
- **Módulos:** `src/rag_cognus/phonetics.py`, `src/rag_cognus/api/app.py`, `src/rag_cognus/api/schemas.py`
- **Testes:** `tests/test_phonetics.py`

## Problema
O catálogo fonético entregava apenas `animationKey` limitado a cinco valores ou `"none"`, e o
frontend exibia a visualização 3D apenas para `/ɾ/` e `/l/`, ou corria o risco de reutilizar um
único gesto para sons distintos. Exercícios de R forte (com variação regional), palatais (`LH`,
`NH`), fricativas pós-alveolares (`J`, `CH`), encontros consonantais (`PR/BR/FR`, `PL/BL/FL`),
pares mínimos (`R × L`) e sequências mistas não tinham um contrato estruturado e versionado de
demonstração articulatória vindo da Gold.

## Comportamento esperado
Cada exercício do catálogo fonético (`GET /v1/phonetics/exercises` e
`GET /v1/phonetics/exercises/{exercise_id}`) inclui um contrato versionado `demonstration`
(`schemaVersion=2`, `contractVersion="2026-11-18.v2"`) oriundo do pipeline
Medallion → Gold → snapshot → API → frontend. O contrato descreve explicitamente:
- perfil articulatório (`profileId`) compatível com `phonemeId` e `animationKey`;
- sequência de alvos e palavras contextualizadas do exercício (`targetSequence`);
- etapas didáticas com tempos ampliados, região de contato, gesto principal, direção do fluxo
  de ar (`oral_central`, `oral_lateral`, `nasal`, `fricative_constriction`, ` closure_hold`),
  acoplamento velofaríngeo (`velum`) e estado de vozeamento (`voiced`, `voiceless`, `variable`);
- variantes regionais seleccionáveis quando aplicável (`r_strong`, sem impor um gesto único).

Combinações incompatíveis entre `phonemeId`, `animationKey` e `demonstration.profileId`, ou
etapas sem região/fluxo/gesto válidos, são rejeitadas na validação do catálogo.

## Critérios de aceite
- **AC-1:** Os 10 exercícios do catálogo possuem `demonstration` versionado (`schemaVersion=2`)
  com `profileId` correspondente ao `phonemeId` e `animationKey`, regiões de contato, fluxo de
  ar, vozeamento e sequência de palavras específicas de cada treino.
- **AC-2:** Exercícios com múltiplos sons (`fricatives_postalveolar`, `cluster_r`, `cluster_l`,
  `contrast_r_l`, `mixed_diction`) possuem sequência multi-etapa que alterna explicitamente os
  gestos, pontos de contato, fluxos de ar ou vozeamento de cada segmento, e `r_strong` declara
  variantes regionais explícitas sem impor vibrante alveolar única.
- **AC-3:** Perfis desconhecidos, versões de contrato incompatíveis, `demonstration.profileId`
  divergente de `phonemeId`/`animationKey`, ou ausência de fluxo nasal em `nh_nasal` / fluxo
  lateral em `l_lateral` e `lh_palatal` são rejeitados com `ValueError`.
- **AC-4:** Os endpoints `GET /v1/phonetics/exercises` e `GET /v1/phonetics/exercises/{id}`
  expõem o contrato `demonstration` completo e validado no schema OpenAPI para consumo direto
  pelo frontend.

## Fora de escopo
Diagnóstico clínico de fala por áudio, captura biométrica da língua do usuário e alteração da
Gold geral `vw_rag_conhecimento`.

## Plano
| Passo | Arquivo | Subagente | Verificação |
|---|---|---|---|
| 1 | `tests/test_phonetics.py` | test-writer | testes falham por AC-1..AC-4 |
| 2 | `src/rag_cognus/phonetics.py` | implementer | `python hermes/harness/check.py --changed` |
| 3 | `python hermes/harness/check.py` | líder | harness completo verde |
