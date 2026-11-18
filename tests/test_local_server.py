import os
import sys

import pytest

from rag_cognus.cli import main


def test_local_server_uses_loopback_and_private_artifacts(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        sys, "argv", ["rag-cognus", "mlflow-local", "--data-dir", str(tmp_path / "store")]
    )
    for name in ("OPENAI_API_BASE", "OPENAI_BASE_URL", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("MLFLOW_GENAI_JUDGE_DEFAULT_MODEL", raising=False)
    monkeypatch.setattr("rag_cognus.cli.load_dotenv", lambda: None)
    monkeypatch.setattr(
        "rag_cognus.cli.subprocess.call", lambda cmd, env: calls.append((cmd, env)) or 0
    )
    monkeypatch.setattr("rag_cognus.cli.port_in_use", lambda port: False)
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    command, env = calls[0]
    # spec 012: herda o ambiente e acrescenta as variáveis do juiz no Ollama.
    assert {k: env[k] for k in os.environ} == dict(os.environ)
    assert env["OPENAI_API_KEY"] == "ollama"
    assert env["OPENAI_API_BASE"].endswith("/v1")
    assert env["MLFLOW_GENAI_JUDGE_DEFAULT_MODEL"].startswith("openai:/")
    assert command[command.index("--host") + 1] == "127.0.0.1"
    assert command[command.index("--port") + 1] == "5001"
    assert command[command.index("--backend-store-uri") + 1] == "sqlite:///" + str(
        tmp_path / "store/mlflow.db"
    )
    assert command[command.index("--artifacts-destination") + 1] == str(
        tmp_path / "store/artifacts"
    )


def test_invalid_port_does_not_start_server(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["rag-cognus", "mlflow-local", "--port", "0"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2


def test_busy_port_gives_clear_error(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["rag-cognus", "mlflow-local", "--port", "5000"])
    monkeypatch.setattr("rag_cognus.cli.port_in_use", lambda port: True)
    with pytest.raises(SystemExit):
        main()
    assert "AirPlay" in capsys.readouterr().err
