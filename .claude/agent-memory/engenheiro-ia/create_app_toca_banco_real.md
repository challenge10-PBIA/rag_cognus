---
name: create-app-toca-banco-real
description: create_app(Services(Settings())) abre o SQLite real do usuário e roda migrações; para amostras use FakeServices(tmp_path) dos testes
metadata:
  type: feedback
---

Para gerar JSON de exemplo da API, não instancie `create_app(Services(Settings()))` com
TestClient: o `Store` abre o `cognus.db` real do diretório de dados, roda `ALTER TABLE` e
marca avaliações pendentes como erro. `Settings` não aceita `api_data_dir` como kwarg.

**Why:** em 2026-11-16 (spec 008) isso migrou o banco local do usuário só para mostrar exemplos.
**How to apply:** use `FakeServices(tmp_path, ...)` de `tests/test_api.py` ou chame
funções puras (`mascot.options()`, `feedback.build_guided`). Gerar `openapi()` é seguro
(não faz requisição).
