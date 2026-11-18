# 005 — Catálogo curado de exercícios de comunicação oral

- **Status:** implementada (2026-11-16)
- **Módulos:** `src/rag_cognus/exercises.py` (novo), `data/exercicios.json` (novo)
- **Testes:** `tests/test_exercises.py` (novo)

## Problema
As recomendações da sessão (spec 002) dizem *qual* pilar melhorar, mas não oferecem
prática concreta. Não existe no projeto um conjunto de exercícios (respiração, articulação,
aquecimento vocal, ritmo/pausas, vícios, projeção) com passo a passo e fonte verificável. Exercício sem
fonte, ou com fonte inventada por LLM, é risco de conteúdo errado em tema de saúde vocal.

## Comportamento esperado
- Um catálogo curado à mão em `data/exercicios.json`, versionado no git, lido pelo módulo
  `src/rag_cognus/exercises.py`. Nada vem do Databricks nem de LLM em tempo de execução.
- Quem consome (API, agente de comunicação, chat) pede exercícios por pilar
  (`pace`, `pauses`, `fillers`, `clarity`, `diction`) e recebe itens com passos e fonte.
- Todo exercício cita uma fonte real (artigo revisado por pares, livro ou instituição
  reconhecida) que um humano abriu e conferiu na data `verificado_em`.
- O catálogo traz um aviso fixo: conteúdo educativo, não substitui avaliação
  fonoaudiológica.

### Formato: JSON (não YAML)
JSON é lido com a biblioteca padrão (`json`), sem dependência nova (`pyyaml` não está em
`pyproject.toml`), tem tipos sem ambiguidade (YAML converte `no`/`on`/datas sozinho) e é o
mesmo formato que a API devolve. Diffs no git continuam legíveis com indentação de 2 espaços.

### Estrutura do arquivo
```json
{
  "versao": 1,
  "aviso": "Conteúdo educativo. Não substitui avaliação fonoaudiológica. ...",
  "exercicios": [
    {
      "id": "resp-diafragmatica-01",
      "titulo": "Respiração diafragmática deitado",
      "categoria": "respiracao",
      "pilares": ["pace", "pauses"],
      "passos": ["...", "..."],
      "duracao_min": 5,
      "nivel": "iniciante",
      "fonte": {
        "titulo": "...", "autor": "...", "ano": 2019,
        "url": "https://...", "tipo": "artigo"
      },
      "verificado_em": "2026-11-16"
    }
  ]
}
```

| Campo | Tipo e regra |
|---|---|
| `id` | str, único, `^[a-z0-9]+(-[a-z0-9]+)*$` |
| `titulo` | str não vazia, em português |
| `categoria` | uma de CATEGORIAS (abaixo) |
| `pilares` | lista não vazia, sem repetição, de itens de PILARES (abaixo) |
| `passos` | lista com ≥ 2 strings não vazias, em português |
| `duracao_min` | int entre 1 e 30 |
| `nivel` | uma de `iniciante`, `intermediario`, `avancado` |
| `fonte.titulo`, `fonte.autor` | str não vazia |
| `fonte.ano` | int entre 1950 e o ano corrente |
| `fonte.url` | str começando com `https://` |
| `fonte.tipo` | uma de `artigo`, `livro`, `instituicao` |
| `verificado_em` | data ISO `AAAA-MM-DD`, não futura |

- PILARES: `pace`, `pauses`, `fillers`, `clarity`, `diction`.
- CATEGORIAS: `respiracao`, `articulacao`, `aquecimento_vocal`, `ritmo_pausas`,
  `vicios_linguagem`, `projecao`.

### Processo de verificação das fontes (manual, fora dos testes)
1. Fontes aceitas: periódico revisado por pares (ex.: CoDAS, Revista CEFAC, Journal of
   Voice, J Speech Lang Hear Res), livro técnico com editora identificável, ou instituição
   reconhecida (Sociedade Brasileira de Fonoaudiologia, Conselho Federal de Fonoaudiologia,
   ASHA, NIDCD/NIH). Blogs, vídeos sem autoria e páginas comerciais não valem.
2. A referência é encontrada por um humano (busca no periódico, SciELO, PubMed, site da
   instituição). **Nenhuma fonte é aceita por ter sido sugerida por LLM** sem essa busca.
3. O revisor abre a `url`, confere título, autor e ano exatamente como no JSON e confirma
   que o conteúdo sustenta o exercício. Preenche `verificado_em` com a data da conferência.
4. Preferir DOI (`https://doi.org/...`) ou página permanente da instituição.
5. `passos` são **paráfrase** da fonte em português, curtos e no imperativo; não copiar
   trechos literais além de termos técnicos.
6. Exercício que não passar em 1–5 não entra no arquivo. URL que deixar de abrir em revisão
   futura: corrigir a referência ou remover o exercício, e atualizar `verificado_em`.
7. O PR que altera `data/exercicios.json` lista, por exercício novo/alterado, a URL e quem
   conferiu.

### Cobertura mínima
- ≥ 12 exercícios no total.
- ≥ 2 exercícios por pilar (`pace`, `pauses`, `fillers`, `clarity`, `diction`).
- ≥ 1 exercício por categoria (as 6 categorias).
- ≥ 3 fontes distintas (por `url`) no catálogo.

### Interface (fixa — consumida por outro módulo, não alterar)
```python
def load_exercises(path: Path | None = None) -> list[dict]: ...
def exercises_for(pillar: str, limit: int = 2) -> list[dict]: ...
```
- `load_exercises(None)` lê `data/exercicios.json` na raiz do projeto; devolve a lista
  `exercicios` validada (dicts com os campos da tabela), na ordem do arquivo.
- Erro de schema levanta `ValueError` com mensagem em português que cita o `id` (ou o índice,
  se faltar `id`) e o campo problemático.
- `exercises_for` usa o catálogo padrão; devolve até `limit` exercícios que contêm o pilar,
  ordem estável (a do arquivo). Pilar inválido levanta `ValueError`.

## Critérios de aceite
- **AC-1:** Dado o arquivo real `data/exercicios.json`, quando `load_exercises()` é chamado,
  então devolve `list[dict]` com todos os campos obrigatórios da tabela e tipos corretos.
- **AC-2:** Dado um arquivo temporário com um exercício sem um campo obrigatório (ex.: sem
  `fonte`), quando carregado, então `ValueError` cita o `id` e o nome do campo ausente.
- **AC-3:** Dado um exercício com pilar fora de `pace|pauses|fillers|clarity|diction`, ou
  categoria/nível fora das listas, quando carregado, então `ValueError` cita o valor inválido.
- **AC-4:** Dado `fonte.url` que não começa com `https://` (ex.: `http://…` ou vazio), quando
  carregado, então `ValueError` menciona `https`.
- **AC-5:** Dado `verificado_em` fora do formato ISO ou no futuro, ou `fonte.ano` fora de
  1950…ano corrente, quando carregado, então `ValueError`.
- **AC-6:** Dado o arquivo real, então os `id` são únicos e seguem o padrão kebab-case;
  com `id` duplicado num arquivo temporário, `load_exercises` levanta `ValueError`.
- **AC-7:** Dado o arquivo real, então há ≥ 12 exercícios, ≥ 2 por pilar, ≥ 1 por categoria
  e ≥ 3 URLs de fonte distintas.
- **AC-8:** Dado o arquivo real, então o campo de topo `aviso` existe e contém "não substitui"
  e "fonoaudiológica".
- **AC-9:** `exercises_for("pauses", limit=2)` devolve no máximo 2 itens, todos com `pauses`
  em `pilares`, na ordem do arquivo; `limit=0` devolve `[]`.
- **AC-10:** `exercises_for("tom")` levanta `ValueError` listando os pilares válidos.
- **AC-11:** Os testes não acessam rede: as URLs são validadas só por formato (verificável
  com `socket` bloqueado por monkeypatch durante `load_exercises`).

## Fora de escopo
- Checar automaticamente se as URLs respondem (link-check) — fica para job manual/CI futuro.
- Ligar o catálogo à API, ao agente de comunicação ou aos desafios do dia (spec seguinte,
  engenheiro de IA).
- Indexar exercícios no BM25/embeddings ou publicar na Gold/Databricks.
- Áudio/vídeo demonstrativo, personalização por histórico, tradução.

## Plano (preenchido depois da aprovação)
| Passo | Arquivo | Responsável | Verificação |
|---|---|---|---|
| 1 | `tests/test_exercises.py` | engenheiro-dados | vermelho por AC-1…AC-11 |
| 2 | `src/rag_cognus/exercises.py` | engenheiro-dados | AC-2…AC-6, AC-9…AC-11 verdes |
| 3 | `data/exercicios.json` (curadoria manual) | eng.-dados + revisor | AC-1, AC-7, AC-8 |
| 4 | — | líder técnico | `python hermes/harness/check.py` |
