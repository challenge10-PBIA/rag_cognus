"""Specs 017 e 021: checagens estáticas do Alloy, do compose e do dashboard (sem Docker, sem rede)."""

import json
import re
from pathlib import Path

import yaml

from rag_cognus import mlflow_exporter
from rag_cognus.api import metrics as api_metrics

ROOT = Path(__file__).resolve().parents[1]
ALLOY = ROOT / "infra/alloy/config.alloy"
COMPOSE = ROOT / "infra/alloy/docker-compose.yml"
DASHBOARD = ROOT / "infra/grafana/rag-cognus-dashboard.json"
ALERTS = ROOT / "infra/grafana/alerts.yaml"
ENV_VARS = {"GRAFANA_PROM_REMOTE_WRITE_URL", "GRAFANA_PROM_USER", "GRAFANA_CLOUD_ACCESS_TOKEN"}


def test_alloy_uses_only_sys_env_and_no_token():  # AC-11
    text = ALLOY.read_text()
    assert set(re.findall(r'sys\.env\("([A-Z_]+)"\)', text)) == ENV_VARS
    assert not re.search(r"gl(c|sa)_", text)
    # url, username e password só vêm de sys.env, nunca de string literal.
    for key in ("url", "username", "password"):
        for value in re.findall(rf"^\s*{key}\s*=\s*(.+)$", text, re.M):
            assert value.startswith("sys.env("), (key, value)
    assert "grafana.net" not in text


def test_alloy_scrapes_api_and_exporter():  # AC-11
    text = ALLOY.read_text()
    assert '"host.docker.internal:8001"' in text and '"host.docker.internal:9105"' in text
    assert 'job_name        = "rag-cognus-api"' in text
    assert 'job_name        = "rag-cognus-mlflow"' in text
    assert text.count('scrape_interval = "15s"') == 2
    assert "prometheus.remote_write" in text


def test_compose_passes_only_three_vars():  # AC-12
    compose = yaml.safe_load(COMPOSE.read_text())
    alloy = compose["services"]["alloy"]
    assert "env_file" not in alloy  # o .env inteiro (Databricks etc.) não entra no container
    env = alloy["environment"]
    assert set(env) == ENV_VARS
    for name, value in env.items():
        assert value.startswith("${" + name + ":?"), (name, value)
    assert alloy["image"].startswith("grafana/alloy:v")
    assert alloy["image"] != "grafana/alloy:latest"
    assert "./config.alloy:/etc/alloy/config.alloy:ro" in alloy["volumes"]
    assert alloy["ports"] == ["127.0.0.1:12346:12345"]


def _known_series() -> set[str]:
    names = set()
    registries = [api_metrics.create_registry(), mlflow_exporter._create_registry()]
    for registry in registries:
        for name, metric in registry._metrics.items():
            names.add(name)
            if metric.kind == "histogram":
                names |= {name + "_bucket", name + "_sum", name + "_count"}
    return names


def _panels(dashboard: dict) -> list[dict]:
    return [p for p in dashboard["panels"] if p["type"] != "row"]


def test_dashboard_queries_use_existing_metrics():  # spec 017 AC-13, spec 021 AC-7
    dashboard = json.loads(DASHBOARD.read_text())
    assert dashboard["__inputs"][0]["name"] == "DS_PROMETHEUS"
    known = _known_series()
    exprs = [t["expr"] for p in _panels(dashboard) for t in p["targets"]]
    exprs += [v["query"]["query"] for v in dashboard["templating"]["list"] if v["type"] == "query"]
    assert exprs
    used = set()
    for panel in _panels(dashboard):
        assert panel["datasource"]["uid"] == "${DS_PROMETHEUS}", panel["title"]
    for expr in exprs:
        found = set(re.findall(r"rag_cognus_[a-z0-9_]+", expr))
        assert found, expr
        assert found <= known, found - known
        used |= found
    for required in (
        "rag_cognus_http_request_duration_seconds_bucket",
        "rag_cognus_http_requests_total",
        "rag_cognus_ask_duration_seconds_bucket",
        "rag_cognus_judge_score_sum",
        "rag_cognus_mlflow_run_metric",
        "rag_cognus_mlflow_up",
        "rag_cognus_mlflow_run_elapsed_seconds",
        "rag_cognus_mlflow_last_ended_timestamp_seconds",
        "rag_cognus_mlflow_runs_total",
    ):
        assert required in used, required


def test_dashboard_batch_row():  # spec 021 AC-7
    dashboard = json.loads(DASHBOARD.read_text())
    panels = dashboard["panels"]
    ids = [p["id"] for p in panels]
    assert len(ids) == len(set(ids))
    row = next(i for i, p in enumerate(panels) if p["type"] == "row")
    assert panels[row]["title"] == "Avaliação em lote"
    below = panels[row + 1 :]
    assert all(p["gridPos"]["y"] > panels[row]["gridPos"]["y"] for p in below)

    def find(word: str, kind: str | None = None) -> dict:
        return next(p for p in below if word in p["title"] and kind in (None, p["type"]))

    running = find("Em andamento")
    assert running["type"] == "stat"
    assert "run_elapsed_seconds" in running["targets"][0]["expr"]
    assert running["targets"][0]["legendFormat"] == "{{run_name}}"
    last = find("Último run concluído")
    assert "last_ended_timestamp_seconds" in last["targets"][0]["expr"]
    assert "{{status}}" in last["targets"][0]["legendFormat"]
    history = find("ao longo do tempo")
    assert history["type"] == "timeseries" and "by (metric)" in history["targets"][0]["expr"]
    table = find("Métricas do último run", "table")
    order = table["transformations"][0]["options"]["indexByName"]
    assert {"experiment", "backend", "judge_model"} <= set(order)
    assert "status" in find("Runs por status")["targets"][0]["expr"]
    variable = next(v for v in dashboard["templating"]["list"] if v["name"] == "experiment")
    assert variable["datasource"]["uid"] == "${DS_PROMETHEUS}"


def _alloy_jobs() -> set[str]:
    return set(re.findall(r'job_name\s*=\s*"([^"]+)"', ALLOY.read_text()))


def test_alerts_yaml_rules():  # spec 021 AC-8
    doc = yaml.safe_load(ALERTS.read_text())
    assert set(doc) == {"groups"}
    rules = {}
    for group in doc["groups"]:
        assert "limit" not in group  # a importação do Grafana Cloud recusa `limit`
        assert group["name"] and group["interval"]
        for rule in group["rules"]:
            assert set(rule) <= {"alert", "expr", "for", "labels", "annotations"}, rule
            assert "query" not in str(rule.get("annotations", {}))
            rules[rule["alert"]] = rule
    expected = {
        "RagCognusMlflowFora": ("rag_cognus_mlflow_up", "== 0", "5m"),
        "RagCognusAvaliacaoTravada": ("rag_cognus_mlflow_run_elapsed_seconds", "> 3600", None),
        "RagCognusQualidadeBaixa": ('metric="quality_score_mean"', "< 3.5", None),
        "RagCognusCitacaoBaixa": ('metric="citation_integrity_mean"', "< 0.9", None),
        "RagCognusRunFalhou": ('rag_cognus_mlflow_runs_total{status="FAILED"}', "> 0", None),
        "RagCognusApiSemDados": ('up{job="rag-cognus-api"}', "== 0", "5m"),
    }
    assert set(rules) == set(expected)
    for name, (needle, op, duration) in expected.items():
        expr = " ".join(rules[name]["expr"].split())
        assert needle in expr and op in expr, (name, expr)
        if duration:
            assert rules[name]["for"] == duration, name
    # gauge: delta, nunca increase/rate (exclusão de run viraria "reset" e falso positivo)
    failed = rules["RagCognusRunFalhou"]["expr"]
    assert failed.startswith("delta(") and "increase" not in failed and "rate(" not in failed
    known = _known_series()
    for rule in rules.values():
        found = set(re.findall(r"rag_cognus_[a-z0-9_]+", rule["expr"]))
        assert found <= known, found - known
        for job in re.findall(r'job="([^"]+)"', rule["expr"]):
            assert job in _alloy_jobs(), job
