# 006 — Feedback guiado: recomendações hierárquicas, exercícios e avatar

- **Status:** implementado (AC-1…AC-16; API ligada em `api/app.py`, `chat=None` por padrão)
- **Módulos:** `src/rag_cognus/api/app.py`, `src/rag_cognus/api/schemas.py`,
  `src/rag_cognus/api/store.py`, novo `src/rag_cognus/feedback.py`, novo
  `src/rag_cognus/avatar.py`; usa `src/rag_cognus/exercises.py` (spec 005) e
  `src/rag_cognus/retrieval.py`
- **Testes:** `tests/test_feedback.py`, `tests/test_avatar.py`, `tests/test_api.py`
- **Depende de:** spec 002 (pilares), spec 003 (ocorrências), spec 005 (catálogo)

## Problema
O feedback da sessão tem só duas ou três recomendações soltas (`strength`, `next_step`,
`tip`), sem desdobramento prático nem exercício. O catálogo de exercícios da spec 005 e a
Gold `cognus.gold.vw_rag_conhecimento` não são usados juntos. O perfil não tem imagem.

## Comportamento esperado
- Cada sessão traz `guided_feedback`: recomendações ligadas a um pilar fraco ou a uma
  ocorrência da spec 003, cada uma com 1–3 sub-recomendações ancoradas em trechos da Gold
  (com a fonte citada) e 1–2 exercícios **do catálogo**.
- O LLM (opcional) só redige sub-recomendações a partir dos trechos e escolhe exercícios
  entre os ids que recebeu. Nunca inventa exercício, fonte nem número.
- O usuário envia uma foto de perfil; a API devolve uma versão cartunizada gerada
  localmente por filtro determinístico (sem modelo de imagem, sem rede).

## Interface fixa da spec 005 (não alterar)
`exercises.load_exercises(path: Path | None = None) -> list[dict]` e
`exercises.exercises_for(pillar: str, limit: int = 2) -> list[dict]`. Exercício:
`{id, titulo, categoria, pilares[], passos[], duracao_min, nivel,
fonte{titulo, autor, ano, url, tipo}, verificado_em}`. Pilares: `pace`, `pauses`,
`fillers`, `clarity`, `diction`.

## Critérios de aceite — recomendações
- **AC-1:** `feedback.build_guided(analysis, occurrences, retriever, chat=None,
  exercises_fn=exercises_for) -> list[dict]` é puro em relação a rede quando `chat=None`;
  `retriever` pode ser `None` (Gold ausente).
- **AC-2:** Seleção, em ordem: pilares com `score < 80` do menor para o maior (máx. 3,
  incluindo `diction` se `diction < 70`); depois até 2 termos de ocorrência mais
  frequentes (vício → pilar `fillers`; pleonasmo → pilar `clarity`) que ainda não tenham
  recomendação. Se nada for selecionado, uma recomendação "Manter" para o pilar de menor
  score. Total máximo: 4.
- **AC-3:** Cada recomendação tem `{id, pillar, target: {kind: "pillar"|"occurrence",
  term|null}, title, text, priority: "alta"|"media"|"baixa", subs[], exercises[],
  sources_available: bool}`; `priority` = alta (< 50), media (50–69), baixa (≥ 70).
- **AC-4:** Busca na Gold: consulta = `progress.CHALLENGES[pillar]["query"]` (ou consulta
  constante `DICTION_QUERY` para `diction`), acrescida do termo quando o alvo for
  ocorrência; `k=3` via `retriever.search`. Cada sub-recomendação tem `{text, source:
  {chunk_id, title, url}, excerpt}` com `chunk_id` de um trecho recuperado e `excerpt`
  substring literal dele (≤ 240 caracteres).
- **AC-5:** Sem `chat`, as 1–3 sub-recomendações são montadas deterministicamente: uma por
  trecho recuperado, `text` = primeira frase do trecho (≤ 200 caracteres), `excerpt` =
  mesma frase.
- **AC-6:** Com `chat` (fake nos testes), o LLM recebe os trechos e devolve
  `[{text, chunk_id, excerpt}]`; itens com `chunk_id` fora dos recuperados ou `excerpt`
  que não seja substring literal são descartados; se sobrar zero, usa AC-5. Erro do LLM →
  AC-5, sem propagar.
- **AC-7:** Gold indisponível (`retriever=None` ou `GoldUnavailable`): `subs=[]`,
  `sources_available=false`; a recomendação e os exercícios continuam.
- **AC-8:** Exercícios: `exercises_fn(pillar, limit=2)`; o LLM, se houver, só pode
  reordenar/escolher entre esses ids (ids desconhecidos ignorados). Cada recomendação traz
  1–2 exercícios quando o catálogo tem algum para o pilar e `[]` quando não tem. Os dicts
  do catálogo são devolvidos sem alteração de campos (teste compara com o fake).
- **AC-9:** Catálogo ausente ou inválido (`load_exercises` levanta) → `exercises=[]` em
  todas as recomendações e a sessão é salva normalmente.
- **AC-10:** `POST /v1/sessions` inclui `guided_feedback`; `SessionResult` ganha
  `guided_feedback: list[GuidedRecommendation] | None = None`. Sessões antigas (sem o
  campo) continuam válidas em `GET /v1/sessions/{id}`; `recommendations` atual não muda.
- **AC-11:** Marcar exercício como feito reutiliza `POST /v1/habits`: `HabitIn` e `Habit`
  ganham `exercise_id: str | None = None`; a tabela `habits` recebe a coluna se faltar
  (migração idempotente). `exercise_id` fora do catálogo → 422.

## Critérios de aceite — avatar
- **AC-12:** `avatar.cartoonize(image_bytes: bytes) -> bytes` (PNG 512×512): corrige
  orientação EXIF, recorta o quadrado central, redimensiona, suaviza (filtro mediano),
  quantiza para `AVATAR_COLORS = 8` cores sem pontilhado e sobrepõe contornos (bordas por
  Sobel/`FIND_EDGES` com limiar fixo) na cor `#15191c`. Só Pillow e numpy.
- **AC-13:** Determinismo: a mesma entrada gera bytes idênticos (hash igual em duas
  chamadas); a saída tem no máximo `AVATAR_COLORS + 1` cores distintas.
- **AC-14:** `POST /v1/profile/avatar` (multipart `image`) aceita PNG/JPEG/WebP até 5 MB e
  lado mínimo 64 px; fora disso → 422 em português. Salva só a versão cartunizada em
  `<data_dir>/avatar.png` (a foto original não é gravada) e devolve
  `{avatar_url: "/v1/profile/avatar", updated_at}`.
- **AC-15:** `GET /v1/profile/avatar` devolve `image/png` com `Cache-Control: no-cache` e
  `ETag` (hash do arquivo); 404 sem avatar. `DELETE /v1/profile/avatar` → 204.
- **AC-16:** `Profile` ganha `avatar_url: str | None = None` (preenchido quando o arquivo
  existe). Nenhum teste de avatar usa rede ou modelo; as imagens de teste são geradas em
  memória com Pillow.

## Fora de escopo
- Gerar exercícios novos, editar o catálogo (spec 005), avatar por IA generativa,
  múltiplos perfis, recorte manual da foto.

## Impacto esperado
- Nenhum nas métricas do RAG em lote. Com `chat` ligado, a sessão ganha 1 chamada ao LLM
  por recomendação (até 4): usar `fast_chat` e permitir desligar (`chat=None`) para manter
  a latência da sessão.
- DevOps: declarar `pillow` no extra `api` do `pyproject.toml` (hoje só transitivo).

## Plano (preenchido depois da aprovação)
| Passo | Arquivo | Subagente | Verificação |
|---|---|---|---|
| 1 | `tests/test_feedback.py` → `feedback.py` | engenheiro-ia | AC-1…AC-9 |
| 2 | `tests/test_avatar.py` → `avatar.py` | engenheiro-ia | AC-12, AC-13 |
| 3 | `tests/test_api.py` → `api/*` | engenheiro-ia | AC-10, AC-11, AC-14…AC-16 |
| 4 | `pyproject.toml` | engenheiro-devops | `check.py` |
