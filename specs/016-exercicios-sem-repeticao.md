# Exercícios distintos no feedback da sessão

## Problema
O feedback seleciona sempre os dois primeiros exercícios de cada pilar. Exercícios
que pertencem a vários pilares aparecem repetidos na mesma sessão e ocultam outras
opções relevantes do catálogo.

## Critérios de aceite
- AC-1: um exercício aparece no máximo uma vez entre as recomendações de uma sessão.
- AC-2: a seleção procura outras opções do mesmo pilar antes de devolver menos de dois.
- AC-3: sem alternativas elegíveis, devolve menos opções; não inventa nem repete conteúdo.
- AC-4: a seleção do LLM só pode usar os candidatos elegíveis e não reintroduz repetidos.
- AC-5: os exercícios e suas fontes são preservados integralmente; falhas no catálogo
  continuam sem impedir a análise.

## Verificação
Testes com catálogo sintético compartilhado entre pilares, catálogo esgotado e LLM
tentando repetir um ID. Harness completo, sem chamadas externas.
