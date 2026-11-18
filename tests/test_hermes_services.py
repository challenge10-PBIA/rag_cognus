"""Spec 009 AC-6 — status dos serviços locais em cache para o Hermes (http_get falso)."""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

HERMES = Path(__file__).resolve().parents[1] / "hermes"
SECRET = "segredo-que-nunca-aparece"


def _load(name: str, path: Path):
    sys.path.insert(0, str(path.parent))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(path.parent))


services = _load("hermes_services", HERMES / "harness" / "services.py")
inject = _load("hermes_inject_context", HERMES / "hooks" / "inject_context.py")


def _fake(up: set[str], calls: list):
    def http_get(url: str, timeout: float) -> int:
        calls.append((url, timeout))
        return 200 if any(url.startswith(u) for u in up) else 0

    return http_get


def test_services_lista_tudo_sem_grafana(tmp_path, capsys):
    calls: list = []
    env = {"GRAFANA_SERVICE_ACCOUNT_TOKEN": SECRET}
    fake = _fake({"http://127.0.0.1:11434"}, calls)
    code = services.main(http_get=fake, env=env, out=tmp_path / "services.json")
    out = capsys.readouterr().out
    assert code == 0
    assert "[DOWN] mlflow http://127.0.0.1:5001/health" in out
    assert "[UP] ollama http://127.0.0.1:11434/api/tags" in out
    assert "[DOWN] api http://127.0.0.1:8001/v1/health" in out
    assert "grafana" not in out
    assert all(timeout <= 2 for _, timeout in calls)
    assert SECRET not in out


def test_services_inclui_grafana_e_grava_cache(tmp_path, capsys):
    calls: list = []
    env = {
        "GRAFANA_URL": "https://exemplo.grafana.net/",
        "GRAFANA_SERVICE_ACCOUNT_TOKEN": SECRET,
        "MLFLOW_TRACKING_URI": "http://127.0.0.1:5001",
    }
    fake = _fake({"https://exemplo.grafana.net", "http://127.0.0.1:5001"}, calls)
    cache = tmp_path / "services.json"
    services.main(http_get=fake, env=env, out=cache)
    out = capsys.readouterr().out
    assert "[UP] grafana https://exemplo.grafana.net/api/health" in out
    assert "[UP] mlflow http://127.0.0.1:5001/health" in out
    data = json.loads(cache.read_text())
    assert {s["name"] for s in data["services"]} == {"mlflow", "ollama", "api", "grafana"}
    assert time.time() - data["ts"] < 60
    blob = out + cache.read_text() + repr(calls)
    assert SECRET not in blob


def test_services_le_so_a_url_do_env_do_repo(tmp_path, capsys):
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"GRAFANA_SERVICE_ACCOUNT_TOKEN={SECRET}\nexport GRAFANA_URL='https://repo.grafana.net'\n"
    )
    calls: list = []
    cache = tmp_path / "s.json"
    services.main(http_get=_fake(set(), calls), env={}, out=cache, env_file=env_file)
    out = capsys.readouterr().out
    assert "[DOWN] grafana https://repo.grafana.net/api/health" in out
    assert SECRET not in out + cache.read_text() + repr(calls)


def test_services_env_do_processo_vence_o_arquivo(tmp_path, capsys):
    env_file = tmp_path / ".env"
    env_file.write_text("GRAFANA_URL=https://arquivo.grafana.net\n")
    env = {"GRAFANA_URL": "https://processo.grafana.net"}
    services.main(http_get=_fake(set(), []), env=env, out=tmp_path / "s.json", env_file=env_file)
    out = capsys.readouterr().out
    assert "processo.grafana.net" in out and "arquivo.grafana.net" not in out


def test_services_padrao_e_o_env_do_repo():
    assert services.REPO_ENV == Path(__file__).resolve().parents[1] / ".env"


def test_services_ignora_tracking_uri_nao_http(tmp_path, capsys):
    env = {"MLFLOW_TRACKING_URI": "file:./mlruns"}
    services.main(http_get=_fake(set(), []), env=env, out=tmp_path / "s.json")
    assert "http://127.0.0.1:5001/health" in capsys.readouterr().out


def test_inject_context_usa_cache_recente(tmp_path):
    cache = tmp_path / "services.json"
    now = time.time()
    services_list = [
        {"name": "mlflow", "url": "u", "up": True},
        {"name": "ollama", "url": "u", "up": False},
    ]
    cache.write_text(json.dumps({"ts": now - 60, "services": services_list}))
    line = inject.services_line(cache, now=now)
    assert line.startswith("Serviços: ")
    assert "mlflow UP" in line and "ollama DOWN" in line


def test_inject_context_ignora_cache_velho_ou_ausente(tmp_path):
    cache = tmp_path / "services.json"
    assert inject.services_line(cache) is None
    cache.write_text(json.dumps({"ts": time.time() - 301, "services": []}))
    assert inject.services_line(cache) is None
    cache.write_text("não é json")
    assert inject.services_line(cache) is None
