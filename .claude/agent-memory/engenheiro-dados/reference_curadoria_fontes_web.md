---
name: reference-curadoria-fontes-web
description: Quais sites abrem no WebFetch ao verificar fontes científicas (curadoria de data/exercicios.json) e quais bloqueiam
metadata:
  type: reference
---

Ao verificar fontes para o catálogo `data/exercicios.json` (spec 005), em 2026-11-16:

- Abrem bem: páginas de artigo no SciELO (`www.scielo.br/j/...`), NIDCD (`nidcd.nih.gov`),
  e a API REST da Europe PMC
  (`https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID:<PMID>%20AND%20SRC:MED&format=json&resultType=core`).
- Bloqueiam (403 ou parede de cookies): pubs.asha.org, onlinelibrary.wiley.com,
  pubmed.ncbi.nlm.nih.gov, europepmc.org/article. `doi.org` só devolve o 302.
- DOIs lembrados de memória podem estar errados (ex.: 10.1002/jaba.369 era outro artigo);
  sempre confirmar pela Europe PMC.

**How to apply:** prefira fontes SciELO/instituições para que a URL gravada seja a mesma
aberta; para JABA/ASHA, confirme metadados pela API da Europe PMC e sinalize no relatório.
