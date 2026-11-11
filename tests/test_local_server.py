import sys

import pytest

from rag_cognus.cli import main


def test_local_server_uses_loopback_and_private_artifacts(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        sys, "argv", ["rag-cognus", "mlflow-local", "--data-dir", str(tmp_path / "store")]
    )
    monkeypatch.setattr("rag_cognus.cli.subprocess.call", lambda cmd: calls.append(cmd) or 0)
    monkeypatch.setattr("rag_cognus.cli.port_in_use", lambda port: False)
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    command = calls[0]
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
