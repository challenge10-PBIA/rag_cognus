---
name: api-temporaria-sqlite-isolado
description: Segunda instância da API (ex. para gerar openapi.json) precisa de data_dir próprio; Store() interrompe avaliações pending
metadata:
  type: feedback
---

Para subir uma API extra (gerar tipos do front com `npm run api:types`), use
`create_app(Services(Settings.from_env(), data_dir=<scratch>))` via uvicorn em outra porta,
nunca `rag-cognus api` no mesmo `.cache/app`.

**Why:** `Store.__init__` marca toda avaliação `pending` como erro ("Avaliação interrompida."),
então abrir o mesmo `cognus.db` mataria uma avaliação em andamento na API da 8001.

**How to apply:** sempre que o líder pedir uma instância temporária da API. Também: o
`openapi.json` versionado do front é indentado (2 espaços, sem `\n` final) e o `curl` grava
minificado; reformate antes de olhar o diff.
