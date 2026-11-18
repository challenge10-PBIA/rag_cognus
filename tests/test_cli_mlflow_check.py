import sys

import pytest

from rag_cognus.cli import main, mlflow_check
from rag_cognus.config import Settings


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


class FakeClient:
    def __init__(self, names):
        self.names = set(names)
        self.created = []

    def get_experiment_by_name(self, name):
        return object() if name in self.names else None

    def create_experiment(self, name):
        self.created.append(name)
        self.names.add(name)
        return "1"


def http_ok(url, timeout):
    assert url == "http://127.0.0.1:5001/health" and timeout <= 2
    return FakeResponse(200)


def http_down(url, timeout):
    raise OSError("Connection refused")


def no_client(uri):
    raise AssertionError("não deve consultar experimentos sem servidor")


def test_ok_creates_missing_online_experiment(capsys):  # AC-D4
    client = FakeClient({"rag-cognus"})
    code = mlflow_check(Settings(), http_get=http_ok, client_factory=lambda uri: client)
    out = capsys.readouterr().out
    assert code == 0
    assert client.created == ["rag-cognus-online"]
    assert "http://127.0.0.1:5001" in out and "rag-cognus-online" in out


def test_server_down_exits_1_with_hint(capsys):  # AC-D4
    code = mlflow_check(Settings(), http_get=http_down, client_factory=no_client)
    assert code == 1
    assert "rode `rag-cognus mlflow-local`" in capsys.readouterr().out


def test_non_2xx_is_failure(capsys):  # AC-D4
    code = mlflow_check(
        Settings(), http_get=lambda url, timeout: FakeResponse(503), client_factory=no_client
    )
    assert code == 1
    assert "rode `rag-cognus mlflow-local`" in capsys.readouterr().out


def test_missing_batch_experiment_is_reported_not_created(capsys):  # AC-D4
    client = FakeClient({"rag-cognus-online"})
    code = mlflow_check(Settings(), http_get=http_ok, client_factory=lambda uri: client)
    assert code == 0
    assert client.created == []
    assert "rag-cognus: ausente" in capsys.readouterr().out


def test_command_rejects_databricks_uri(monkeypatch, capsys):  # AC-D4
    monkeypatch.setattr("rag_cognus.cli.load_dotenv", lambda: None)
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "databricks://perfil")
    monkeypatch.setattr(sys, "argv", ["rag-cognus", "mlflow-check"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "não é um MLflow local" in out and "rode `rag-cognus mlflow-local`" in out


def test_command_exit_code_follows_check(monkeypatch):  # AC-D4
    monkeypatch.setattr("rag_cognus.cli.load_dotenv", lambda: None)
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    monkeypatch.setattr("rag_cognus.cli.mlflow_check", lambda settings: 0)
    monkeypatch.setattr(sys, "argv", ["rag-cognus", "mlflow-check"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0


class CountingHttp:
    def __init__(self, ok=True):
        self.ok = ok
        self.calls = 0

    def __call__(self, url, timeout):
        self.calls += 1
        assert url == "http://127.0.0.1:5001/health" and timeout <= 2
        if not self.ok:
            raise OSError("Connection refused")
        return FakeResponse(200)


URI = "http://127.0.0.1:5001"


@pytest.fixture(autouse=True)
def _clear_mlflow_cache():
    from rag_cognus import cli

    cli.MLFLOW_HEALTH_CACHE.clear()
    yield
    cli.MLFLOW_HEALTH_CACHE.clear()


def test_availability_is_cached_for_30_seconds():  # AC-D5
    from rag_cognus.cli import mlflow_available

    http = CountingHttp(ok=False)
    assert mlflow_available(URI, now=100.0, http_get=http) is False
    assert mlflow_available(URI, now=129.9, http_get=http) is False
    assert http.calls == 1


def test_availability_retries_after_cache_expires():  # AC-D5
    from rag_cognus.cli import mlflow_available

    http = CountingHttp(ok=False)
    assert mlflow_available(URI, now=100.0, http_get=http) is False
    http.ok = True
    assert mlflow_available(URI, now=130.0, http_get=http) is True
    assert http.calls == 2


def test_availability_non_2xx_is_false():  # AC-D5
    from rag_cognus.cli import mlflow_available

    assert not mlflow_available(URI, now=0.0, http_get=lambda url, timeout: FakeResponse(503))


def test_availability_local_store_skips_http():  # AC-D5
    from rag_cognus.cli import mlflow_available

    def boom(url, timeout):
        raise AssertionError("não deve chamar HTTP para sqlite:")

    assert mlflow_available("sqlite:///mlflow.db", now=0.0, http_get=boom) is True


def test_serve_api_does_not_disable_tracing_when_mlflow_down(monkeypatch, capsys):  # AC-D5
    import mlflow
    import uvicorn

    import rag_cognus.api.app as api_app
    import rag_cognus.evaluation as evaluation
    from rag_cognus.cli import serve_api

    def down(settings):
        raise ConnectionError("MLflow fora do ar")

    disabled = []
    started = []
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    monkeypatch.setattr(evaluation, "configure_tracking", down)
    monkeypatch.setattr(mlflow.tracing, "disable", lambda: disabled.append(True))
    monkeypatch.setattr(api_app, "Services", lambda settings: object())
    monkeypatch.setattr(api_app, "create_app", lambda services: "app")
    monkeypatch.setattr(uvicorn, "run", lambda app, host, port: started.append(app))
    serve_api("127.0.0.1", 8001)
    assert disabled == [] and started == ["app"]
    assert "tenta de novo" in capsys.readouterr().out
