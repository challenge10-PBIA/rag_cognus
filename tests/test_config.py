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


ONLINE_VARS = ("MLFLOW_ONLINE_EXPERIMENT", "RAG_ONLINE_EVAL", "SPEECH_PLEONASM_LLM")


def test_online_eval_defaults(monkeypatch):  # spec 004 AC-D1
    for name in ONLINE_VARS:
        monkeypatch.delenv(name, raising=False)
    settings = Settings.from_env()
    assert settings.online_experiment == "rag-cognus-online"
    assert settings.online_eval is True
    assert settings.speech_pleonasm_llm is False


def test_online_eval_from_env(monkeypatch):  # spec 004 AC-D1 + spec 003
    monkeypatch.setenv("MLFLOW_ONLINE_EXPERIMENT", "meu-online")
    monkeypatch.setenv("RAG_ONLINE_EVAL", "false")
    monkeypatch.setenv("SPEECH_PLEONASM_LLM", "1")
    settings = Settings.from_env()
    assert (settings.online_experiment, settings.online_eval) == ("meu-online", False)
    assert settings.speech_pleonasm_llm is True


def test_invalid_bool_flag_is_rejected(monkeypatch):  # spec 004 AC-D1
    monkeypatch.setenv("RAG_ONLINE_EVAL", "talvez")
    with pytest.raises(ValueError, match="RAG_ONLINE_EVAL"):
        Settings.from_env()


def test_tracking_uri_still_rejects_databricks(monkeypatch):  # spec 004 AC-D1
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "databricks://perfil")
    with pytest.raises(ValueError, match="não é um MLflow local"):
        Settings.from_env()


def test_env_example_documents_online_eval():  # spec 004 AC-D2
    from pathlib import Path

    text = (Path(__file__).parents[1] / ".env.example").read_text()
    assert "MLFLOW_TRACKING_URI=http://127.0.0.1:5001" in text
    for name in ("MLFLOW_EXPERIMENT_NAME=", "MLFLOW_ONLINE_EXPERIMENT=", "RAG_ONLINE_EVAL="):
        assert name in text
    assert "SPEECH_PLEONASM_LLM=" in text
    assert "autoavaliação" in text
