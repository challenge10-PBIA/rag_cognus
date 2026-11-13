---
name: rag-tdd
description: Ciclo TDD vermelho→verde→refatorar no rag_cognus com pytest, fakes sem rede e harness. Use ao escrever testes ou implementar código em src/rag_cognus.
---

# TDD no rag_cognus

## Vermelho
- Um teste por AC, nome `test_<comportamento>_<condição>`; cite o AC em comentário
  (`# AC-2`).
- Arquivo: `tests/test_<modulo>.py` (mesmo nome do módulo em `src/rag_cognus/`).
- Sem rede: Ollama, Databricks e MLflow sempre via `monkeypatch` ou fakes.
  Veja os fixtures em `tests/conftest.py` antes de criar novos.
- Rode: `.venv/bin/python -m pytest -q tests/test_<modulo>.py -x --tb=short`.
- Confirme que falha **pelo motivo certo** (AssertionError/AttributeError esperado), não
  por ImportError ou erro de sintaxe no teste.

## Verde
- Menor mudança possível em `src/`. Use `patch` com contexto suficiente.
- Rode `python hermes/harness/check.py --changed`. Leia só o primeiro erro e corrija.
- Não altere o teste para passar.

## Refatorar (opcional)
- Só com tudo verde. Uma melhoria por vez, harness depois de cada uma.

## Pronto quando
`python hermes/harness/check.py` imprime `HARNESS OK`. Copie essa linha no relatório.

## Exemplo de fake
```python
def test_answer_cita_fontes(monkeypatch):  # AC-1
    from rag_cognus import chain

    monkeypatch.setattr(chain, "ChatOllama", lambda **_: FakeLLM("Resposta [1]"))
    out = chain.answer("pergunta", docs=[...])
    assert out.citations == ["doc-1"]
```
(Confira os nomes reais em `src/rag_cognus/chain.py` antes de usar.)
