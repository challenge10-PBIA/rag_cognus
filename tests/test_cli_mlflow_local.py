"""Spec 012: `rag-cognus mlflow-local` sobe o servidor com o Ollama como LLM dos juízes."""

import os
import sys

import pytest

from rag_cognus import cli

JUDGE_VARS = ("OPENAI_API_BASE", "OPENAI_BASE_URL", "OPENAI_API_KEY")
JUDGE_VARS += ("MLFLOW_GENAI_JUDGE_DEFAULT_MODEL",)
SETTINGS_VARS = ("OLLAMA_BASE_URL", "OLLAMA_JUDGE_MODEL", "OLLAMA_CHAT_MODEL", "RAG_ONLINE_EVAL")


@pytest.fixture
def run_local(monkeypatch, tmp_path):
    """Roda `main()` com subprocess e porta falsos; devolve (command, env) do subprocess."""
    for name in JUDGE_VARS + SETTINGS_VARS:
        monkeypatch.delenv(name, raising=False)
    calls = []

    def fake_call(command, env=None):
        calls.append((command, env))
        return 0

    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    monkeypatch.setattr(cli, "port_in_use", lambda port: False)
    monkeypatch.setattr(cli.subprocess, "call", fake_call)
    data_dir = tmp_path / "mlflow"
    argv = ["rag-cognus", "mlflow-local", "--port", "5001", "--data-dir", str(data_dir)]
    monkeypatch.setattr(sys, "argv", argv)

    def run():
        with pytest.raises(SystemExit) as exit_info:
            cli.main()
        assert exit_info.value.code == 0
        assert len(calls) == 1
        return calls[0]

    run.data_dir = data_dir.resolve()
    return run


def test_mlflow_local_passes_ollama_judge_env(monkeypatch, run_local):  # AC-1
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    command, env = run_local()
    assert env["OPENAI_API_BASE"] == "http://127.0.0.1:11434/v1"
    assert env["OPENAI_API_KEY"] == "ollama"
    assert env["MLFLOW_GENAI_JUDGE_DEFAULT_MODEL"] == "openai:/qwen3.5:9b"
    assert env["PATH"] == os.environ["PATH"]  # herda o resto do ambiente
    folder = run_local.data_dir
    assert command == [
        sys.executable,
        "-m",
        "mlflow",
        "server",
        "--host",
        "127.0.0.1",
        "--port",
        "5001",
        "--backend-store-uri",
        "sqlite:///" + str(folder / "mlflow.db"),
        "--serve-artifacts",
        "--artifacts-destination",
        str(folder / "artifacts"),
    ]


def test_mlflow_local_uses_judge_model(monkeypatch, run_local):  # AC-1 (OLLAMA_JUDGE_MODEL)
    monkeypatch.setenv("OLLAMA_JUDGE_MODEL", "llama3.2:3b")
    _, env = run_local()
    assert env["MLFLOW_GENAI_JUDGE_DEFAULT_MODEL"] == "openai:/llama3.2:3b"


def test_mlflow_local_keeps_existing_vars_and_hides_key(monkeypatch, capsys, run_local):  # AC-2
    secret = "sk-valor-que-nao-pode-aparecer"
    monkeypatch.setenv("OPENAI_API_BASE", "http://outro-host:9999/v1")
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    monkeypatch.setenv("MLFLOW_GENAI_JUDGE_DEFAULT_MODEL", "ollama:/qwen3.5:9b")
    _, env = run_local()
    assert env["OPENAI_API_BASE"] == "http://outro-host:9999/v1"
    assert env["OPENAI_API_KEY"] == secret
    assert env["MLFLOW_GENAI_JUDGE_DEFAULT_MODEL"] == "ollama:/qwen3.5:9b"
    out = capsys.readouterr()
    assert secret not in out.out + out.err
    assert "ollama:/qwen3.5:9b" in out.out  # a linha mostra o juiz efetivo


def test_mlflow_local_never_prints_default_key(capsys, run_local):  # AC-2
    run_local()
    out = capsys.readouterr().out
    assert "OPENAI_API_KEY=ollama" not in out
    assert "openai:/qwen3.5:9b" in out and "http://127.0.0.1:11434/v1" in out


@pytest.mark.parametrize(
    "base",
    ["http://127.0.0.1:11434/", "http://127.0.0.1:11434/v1", "http://127.0.0.1:11434/v1/"],
)
def test_mlflow_local_single_v1_suffix(monkeypatch, run_local, base):  # AC-3
    monkeypatch.setenv("OLLAMA_BASE_URL", base)
    _, env = run_local()
    assert env["OPENAI_API_BASE"] == "http://127.0.0.1:11434/v1"


def test_mlflow_local_starts_with_defaults_on_bad_settings(monkeypatch, capsys, run_local):
    # Risco da spec 012: .env inválido não impede o MLflow de subir; usa os padrões.
    monkeypatch.setenv("RAG_ONLINE_EVAL", "talvez")
    _, env = run_local()
    assert env["OPENAI_API_BASE"] == "http://127.0.0.1:11434/v1"
    assert env["MLFLOW_GENAI_JUDGE_DEFAULT_MODEL"] == "openai:/qwen3.5:9b"
    assert "RAG_ONLINE_EVAL" in capsys.readouterr().out  # avisa em uma linha


def test_mlflow_local_respects_openai_base_url(monkeypatch, capsys, run_local):  # AC-2
    # OPENAI_BASE_URL é o nome novo da mesma base; não criar uma segunda base conflitante.
    monkeypatch.setenv("OPENAI_BASE_URL", "http://outro-host:9999/v1")
    _, env = run_local()
    assert "OPENAI_API_BASE" not in env
    assert env["OPENAI_BASE_URL"] == "http://outro-host:9999/v1"
    assert "http://outro-host:9999/v1" in capsys.readouterr().out
