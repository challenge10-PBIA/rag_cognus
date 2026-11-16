import pytest
from pydantic import BaseModel

from rag_cognus.config import Settings
from rag_cognus.llm import make_ollama


def test_llm_settings_from_env(monkeypatch):  # AC-1
    monkeypatch.setenv("OLLAMA_NUM_CTX", "32768")
    monkeypatch.setenv("OLLAMA_KEEP_ALIVE", "1h")
    monkeypatch.setenv("OLLAMA_FAST_MODEL", "qwen3.5:4b")
    settings = Settings.from_env()
    assert (settings.num_ctx, settings.keep_alive, settings.fast) == (32768, "1h", "qwen3.5:4b")


def test_llm_settings_defaults(monkeypatch):  # AC-1
    for name in ("OLLAMA_NUM_CTX", "OLLAMA_KEEP_ALIVE", "OLLAMA_FAST_MODEL"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings.from_env()
    assert (settings.num_ctx, settings.keep_alive) == (16384, "30m")
    assert settings.fast == settings.chat_model


def test_rejects_tiny_context():  # AC-1
    with pytest.raises(ValueError, match="num_ctx"):
        Settings(num_ctx=1024)


def test_make_ollama_uses_shared_context():  # AC-1
    class Out(BaseModel):
        text: str

    chat = make_ollama(Settings(num_ctx=12000, keep_alive="5m"), Out, model="m", num_predict=99)
    assert (chat.model, chat.num_ctx, chat.keep_alive, chat.num_predict) == ("m", 12000, "5m", 99)
    assert chat.format == Out.model_json_schema()
