---
name: voz-testes-cache-real
description: Settings() padrão grava a voz em .cache/voice e lê o modelo de .cache/piper do repo; testes de voz devem apontar para tmp_path
metadata:
  type: feedback
---

Em testes da voz (spec 027), sempre use `replace(Settings(), voice_cache_dir=tmp_path/..., piper_data_dir=tmp_path/...)` e troque `voice._piper_synthesize`, `voice._http_client` e `voice._piper_installed` por fakes.

**Why:** os padrões são caminhos relativos ao repo (`.cache/voice`, `.cache/piper`), onde o modelo Piper real existe; sem override o teste polui o cache real ou sintetiza de verdade e fica dependente da máquina.

**How to apply:** qualquer teste novo em `tests/test_voice.py` ou rota de voz em `tests/test_api.py` (helper `voice_services`). Ver também [[create-app-toca-banco-real]].
