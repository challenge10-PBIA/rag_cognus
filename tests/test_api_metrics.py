"""Spec 016: /metrics da API no formato texto do Prometheus 0.0.4."""

import itertools
import re
import time
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from langchain_core.runnables import RunnableLambda
from test_api import FakeServices, boom

from rag_cognus import chain
from rag_cognus.api import metrics as api_metrics
from rag_cognus.api.app import create_app
from rag_cognus.config import Settings
from rag_cognus.judges import METRICS

LE = ["0.05", "0.1", "0.25", "0.5", "1", "2.5", "5", "10", "20", "30", "60", "120", "+Inf"]


@pytest.fixture
def client(tmp_path, documents):
    return TestClient(create_app(FakeServices(tmp_path, documents)))


def scrape(client) -> str:
    response = client.get("/metrics")
    assert response.status_code == 200
    return response.text


def sample(text: str, name: str, **labels) -> float | None:
    """Valor da amostra `name{labels}` (labels na ordem dada), ou None."""
    inner = ",".join(f'{k}="{v}"' for k, v in labels.items())
    target = f"{name}{{{inner}}}" if labels else name
    for line in text.splitlines():
        if line.startswith(target + " "):
            return float(line.rsplit(" ", 1)[1])
    return None


def test_metrics_endpoint_content_type(client):  # AC-1
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain; version=0.0.4")


def test_request_counter_and_histogram(client):  # AC-2
    assert client.get("/v1/profile").status_code == 200
    text = scrape(client)
    labels = {"method": "GET", "route": "/v1/profile", "status": "200"}
    assert sample(text, "rag_cognus_http_requests_total", **labels) == 1
    name = "rag_cognus_http_request_duration_seconds"
    assert sample(text, name + "_count", **labels) == 1
    assert sample(text, name + "_sum", **labels) >= 0
    for le in LE:
        assert sample(text, name + "_bucket", **labels, le=le) is not None, le


def test_route_template_not_raw_path(client):  # AC-3
    assert client.get("/v1/sessions/id-secreto-111").status_code == 404
    assert client.get("/v1/sessions/id-secreto-222").status_code == 404
    text = scrape(client)
    labels = {"method": "GET", "route": "/v1/sessions/{session_id}", "status": "404"}
    assert sample(text, "rag_cognus_http_requests_total", **labels) == 2
    assert "id-secreto" not in text


def test_unmatched_route(client):  # AC-4
    assert client.get("/nao-existe").status_code == 404
    text = scrape(client)
    labels = {"method": "GET", "route": "unmatched", "status": "404"}
    assert sample(text, "rag_cognus_http_requests_total", **labels) == 1
    assert "/nao-existe" not in text


def test_metrics_route_is_not_counted(client):  # AC-5
    for _ in range(3):
        client.get("/metrics")
    assert 'route="/metrics"' not in scrape(client)


def test_no_user_data_in_labels(client):  # AC-6
    body = {"query": "pergunta-sigilosa-xyz", "niche": "apresentacoes_oratoria"}
    assert client.post("/v1/ask", json=body).status_code == 200
    text = scrape(client)
    assert "pergunta-sigilosa-xyz" not in text and "apresentacoes_oratoria" not in text
    labels = {"method": "POST", "route": "/v1/ask", "status": "200"}
    assert sample(text, "rag_cognus_http_requests_total", **labels) == 1


def test_ask_duration_outcome(client, monkeypatch):  # AC-7
    assert client.post("/v1/ask", json={"query": "storytelling"}).status_code == 200
    text = scrape(client)
    assert sample(text, "rag_cognus_ask_duration_seconds_count", outcome="ok") == 1

    def invalid(self, query, niche=None):
        raise ValueError("pergunta vazia")

    monkeypatch.setattr(chain.RagPipeline, "predict", invalid)
    assert client.post("/v1/ask", json={"query": "storytelling"}).status_code == 422
    text = scrape(client)
    assert sample(text, "rag_cognus_ask_duration_seconds_count", outcome="error") == 1
    assert sample(text, "rag_cognus_ask_duration_seconds_count", outcome="ok") == 1


def test_unhandled_exception_counts_500(tmp_path, documents, monkeypatch):  # AC-8
    services = FakeServices(tmp_path, documents)
    client = TestClient(create_app(services), raise_server_exceptions=False)
    monkeypatch.setattr(services.store, "profile", lambda: boom(None))
    assert client.get("/v1/profile").status_code == 500
    labels = {"method": "GET", "route": "/v1/profile", "status": "500"}
    assert sample(scrape(client), "rag_cognus_http_requests_total", **labels) == 1


def test_buckets_are_cumulative(client, monkeypatch):  # AC-9
    monkeypatch.setattr(api_metrics, "clock", itertools.cycle([100.0, 103.0]).__next__)
    assert client.get("/v1/profile").status_code == 200
    text = scrape(client)
    labels = {"method": "GET", "route": "/v1/profile", "status": "200"}
    name = "rag_cognus_http_request_duration_seconds"
    for le in LE:
        expected = 0 if le in LE[:6] else 1
        assert sample(text, name + "_bucket", **labels, le=le) == expected, le
    assert sample(text, name + "_sum", **labels) == pytest.approx(3.0)


def test_metrics_without_external_services(tmp_path):  # AC-10
    settings = replace(Settings(), tracking_uri="http://127.0.0.1:9")
    client = TestClient(create_app(FakeServices(tmp_path, settings=settings)))
    started = time.perf_counter()
    response = client.get("/metrics")
    assert response.status_code == 200
    assert time.perf_counter() - started < 1


def test_registry_per_app(tmp_path, documents):  # AC-11
    first = TestClient(create_app(FakeServices(tmp_path, documents)))
    second = TestClient(create_app(FakeServices(tmp_path, documents)))
    first.get("/v1/profile")
    assert "rag_cognus_http_requests_total{" in scrape(first)
    assert "rag_cognus_http_requests_total{" not in scrape(second)


def test_help_and_type_once_per_metric(client):  # AC-12
    client.get("/v1/profile")
    client.post("/v1/ask", json={"query": "storytelling"})
    text = scrape(client)
    assert text.endswith("\n")
    helps = re.findall(r"^# HELP (\S+) ", text, re.M)
    types = dict(re.findall(r"^# TYPE (\S+) (\S+)$", text, re.M))
    assert len(helps) == len(set(helps)) == len(types)
    assert set(types.values()) <= {"counter", "histogram"}
    seen = set()
    for line in text.splitlines():
        if line.startswith("# TYPE "):
            seen.add(line.split()[2])
        elif not line.startswith("#"):
            base = re.sub(r"(_bucket|_sum|_count)$", "", line.split("{")[0].split(" ")[0])
            assert base in seen, line


# ---------- AC-13: notas do juiz online ----------


def test_judge_scores_histogram(client):  # AC-13
    assert client.post("/v1/ask", json={"query": "storytelling"}).status_code == 200
    text = scrape(client)
    assert sample(text, "rag_cognus_online_eval_total", outcome="ok") == 1
    for metric in [*METRICS, "quality_score"]:
        assert sample(text, "rag_cognus_judge_score_count", metric=metric) == 1, metric
        for le in ["1", "2", "3", "4", "5", "+Inf"]:
            assert sample(text, "rag_cognus_judge_score_bucket", metric=metric, le=le) is not None
    # SCORES do test_api: accuracy=3 → bucket le=2 vale 0, le=3 vale 1.
    assert sample(text, "rag_cognus_judge_score_bucket", metric="accuracy", le="2") == 0
    assert sample(text, "rag_cognus_judge_score_bucket", metric="accuracy", le="3") == 1
    assert 'metric="citation_integrity"' not in text
    assert 'metric="latency_seconds"' not in text


def test_record_judge_scores_ignores_unknown_and_none():  # AC-13
    registry = api_metrics.create_registry()
    api_metrics.record_judge_scores(
        registry,
        {"accuracy": 4, "quality_score": 4.2, "nome_livre": 5, "groundedness": None, "x": "a"},
    )
    text = registry.render()
    assert sample(text, "rag_cognus_judge_score_count", metric="accuracy") == 1
    assert sample(text, "rag_cognus_judge_score_sum", metric="quality_score") == 4.2
    assert "nome_livre" not in text and 'metric="groundedness"' not in text


def test_judge_failure_counts_error(tmp_path, documents):  # AC-13
    client = TestClient(create_app(FakeServices(tmp_path, documents, judge=RunnableLambda(boom))))
    client.post("/v1/ask", json={"query": "storytelling"})
    text = scrape(client)
    assert sample(text, "rag_cognus_online_eval_total", outcome="error") == 1
    assert "rag_cognus_judge_score_count{" not in text


def test_metrics_failure_does_not_break_evaluation(client, monkeypatch):  # AC-13
    def broken(*_):
        raise RuntimeError("registro quebrado")

    monkeypatch.setattr(api_metrics, "record_judge_scores", broken)
    monkeypatch.setattr(api_metrics, "record_online_eval", broken)
    ask_id = client.post("/v1/ask", json={"query": "storytelling"}).json()["ask_id"]
    evaluation = client.get(f"/v1/ask/{ask_id}/evaluation").json()
    assert evaluation["status"] == "done" and evaluation["metrics"]["accuracy"] == 3


def test_unknown_method_becomes_other(client):  # AC-14
    client.request("PROPFIND", "/v1/profile")
    client.request("XYZ-ABC", "/nao-existe")
    client.request("DELETE", "/v1/profile")
    text = scrape(client)
    assert "PROPFIND" not in text and "XYZ-ABC" not in text
    methods = set(re.findall(r'method="([^"]+)"', text))
    assert methods == {"OTHER", "DELETE"}
