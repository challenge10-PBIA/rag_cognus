"""Spec 017: exporter Prometheus do MLflow local (sem rede: MlflowClient falso)."""

import sys
import threading
import urllib.request
from types import SimpleNamespace as NS

import pytest

from rag_cognus import mlflow_exporter as exp
from rag_cognus.config import Settings

PARAMS = {"backend": "bm25", "chat_model": "qwen3.5:9b", "judge_model": "qwen3.5:9b"}


def run(status, start, end=None, metrics=None, params=None, name=None):
    return NS(
        info=NS(
            status=status,
            start_time=start,
            end_time=end,
            run_id=f"r{start}",
            run_name=f"run-{start}" if name is None else name,
        ),
        data=NS(metrics=metrics or {}, params=PARAMS if params is None else params),
    )


class Paged(list):
    token = None


class FakeClient:
    def __init__(self, runs_by_name, traces=None):
        self.runs_by_name = runs_by_name
        self.traces = traces or {}
        self.calls = 0
        self.trace_calls = []

    def get_experiment_by_name(self, name):
        if name not in self.runs_by_name:
            return None
        return NS(experiment_id=name, name=name)

    def search_runs(self, experiment_ids, **kwargs):
        self.calls += 1
        return Paged(self.runs_by_name[experiment_ids[0]])

    def search_traces(self, experiment_ids=None, run_id=None, **kwargs):
        self.trace_calls.append(run_id)
        return Paged(NS(info=NS(run_id=run_id)) for _ in range(self.traces.get(run_id, 0)))


def collector(client, **kw):
    uris = []

    def factory(uri):
        uris.append(uri)
        return client

    c = exp.MlflowCollector(Settings(), client_factory=factory, **kw)
    c.uris = uris
    return c


def sample(text, name, **labels):
    inner = ",".join(f'{k}="{v}"' for k, v in labels.items())
    target = f"{name}{{{inner}}}" if labels else name
    for line in text.splitlines():
        if line.startswith(target + " "):
            return float(line.rsplit(" ", 1)[1])
    return None


BATCH = [
    run("FINISHED", 1_000, 2_000, {"accuracy/mean": 4.5, "recall_at_k": 0.8}),
    run("FINISHED", 5_000, 9_000, {"accuracy/mean": 3.5, "recall_at_k": 0.9}),
    run("FAILED", 10_000, 11_000, {"accuracy/mean": 1.0}),
    run("RUNNING", 12_000),
]


def labels(metric, experiment="rag-cognus"):
    return {"experiment": experiment, "metric": metric, **PARAMS}


def test_latest_finished_run_metrics(monkeypatch):  # AC-1, AC-3
    c = collector(FakeClient({"rag-cognus": BATCH, "rag-cognus-online": []}))
    text = c.collect()
    assert sample(text, "rag_cognus_mlflow_up") == 1
    name = "rag_cognus_mlflow_run_metric"
    # O FINISHED mais recente é o de end_time 9000; FAILED/RUNNING mais novos são ignorados.
    assert sample(text, name, **labels("accuracy_mean")) == 3.5
    assert sample(text, name, **labels("recall_at_k")) == 0.9
    assert c.uris == ["http://127.0.0.1:5001"]


def test_runs_total_and_last_timestamp():  # AC-2
    text = collector(FakeClient({"rag-cognus": BATCH, "rag-cognus-online": []})).collect()
    for status, n in {"FINISHED": 2, "FAILED": 1, "RUNNING": 1}.items():
        got = sample(text, "rag_cognus_mlflow_runs_total", experiment="rag-cognus", status=status)
        assert got == n, status
    ts = sample(text, "rag_cognus_mlflow_last_run_timestamp_seconds", experiment="rag-cognus")
    assert ts == 9.0  # end_time em ms → segundos
    assert 'rag_cognus_mlflow_last_run_timestamp_seconds{experiment="rag-cognus-online"}' not in (
        text
    )


def test_cache_30_seconds():  # AC-4
    now = [100.0]
    client = FakeClient({"rag-cognus": BATCH, "rag-cognus-online": []})
    c = collector(client, now=lambda: now[0])
    c.collect()
    calls = client.calls
    now[0] += 29
    c.collect()
    assert client.calls == calls
    now[0] += 2
    c.collect()
    assert client.calls == 2 * calls
    assert exp.CACHE_SECONDS == 30


def test_mlflow_down_reports_up_zero():  # AC-5
    def down(uri):
        raise ConnectionError("MLflow fora do ar")

    c = exp.MlflowCollector(Settings(), client_factory=down)
    text = c.collect()
    assert sample(text, "rag_cognus_mlflow_up") == 0
    assert "rag_cognus_mlflow_run_metric{" not in text

    class Broken(FakeClient):
        def search_runs(self, *a, **k):
            raise RuntimeError("500 do servidor")

    text = collector(Broken({"rag-cognus": BATCH})).collect()
    assert sample(text, "rag_cognus_mlflow_up") == 0


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("accuracy/mean", "accuracy_mean"),
        ("Quality Score", "quality_score"),
        ("p95-latency.seconds", "p95_latency_seconds"),
        ("ação//x", "a_o_x"),
        ("///", None),
        ("x" * 200, "x" * 64),
    ],
)
def test_metric_name_normalized(raw, expected):  # AC-6
    assert exp.metric_label(raw) == expected


def test_params_limited_to_known_values():  # AC-6
    free = {"backend": "rm -rf /", "chat_model": 'texto "livre" com\nquebra ' * 9}
    runs = [run("FINISHED", 1, 2, {"m": 1.0, "///": 2.0}, params=free)]
    text = collector(FakeClient({"rag-cognus": runs, "rag-cognus-online": []})).collect()
    line = next(x for x in text.splitlines() if x.startswith("rag_cognus_mlflow_run_metric{"))
    assert 'backend="other"' in line and 'judge_model="unknown"' in line
    model = line.split('chat_model="')[1].split('"')[0]
    assert len(model) <= 64 and " " not in model and "\\" not in model
    assert text.count("rag_cognus_mlflow_run_metric{") == 1  # "///" descartada


def test_metric_series_are_capped():  # AC-6
    many = {f"m{i}": float(i) for i in range(500)}
    runs = [run("FINISHED", 1, 2, many)]
    text = collector(FakeClient({"rag-cognus": runs, "rag-cognus-online": []})).collect()
    assert text.count("rag_cognus_mlflow_run_metric{") == exp.MAX_METRICS_PER_RUN


def test_only_local_tracking():  # AC-7
    remote = NS(tracking_uri="http://10.0.0.5:5000", experiment="a", online_experiment="b")
    with pytest.raises(ValueError, match="MLflow local"):
        exp.MlflowCollector(remote, client_factory=lambda uri: None)


def test_missing_experiment_is_not_an_error():  # AC-10
    text = collector(FakeClient({"rag-cognus": BATCH})).collect()
    assert sample(text, "rag_cognus_mlflow_up") == 1
    assert 'experiment="rag-cognus-online"' not in text


def test_http_server_serves_metrics():  # AC-8
    c = collector(FakeClient({"rag-cognus": BATCH, "rag-cognus-online": []}))
    server = exp.make_server(c, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=5) as resp:
            assert resp.status == 200
            assert resp.headers["Content-Type"].startswith("text/plain; version=0.0.4")
            assert "rag_cognus_mlflow_up 1" in resp.read().decode()
        with pytest.raises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/outra", timeout=5)
        assert err.value.code == 404
    finally:
        server.shutdown()
        server.server_close()


def test_cli_defaults_to_loopback(monkeypatch):  # AC-9
    from rag_cognus import cli

    calls = []
    monkeypatch.setattr(sys, "argv", ["rag-cognus", "mlflow-exporter"])
    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    monkeypatch.setattr(exp, "serve", lambda settings, host, port: calls.append((host, port)))
    cli.main()
    assert calls == [("127.0.0.1", 9105)]
    monkeypatch.setattr(
        sys, "argv", ["rag-cognus", "mlflow-exporter", "--host", "0.0.0.0", "--port", "9200"]
    )
    cli.main()
    assert calls[-1] == ("0.0.0.0", 9200)


# --- Spec 021: avaliação em lote em andamento -------------------------------------------

WALL = 12_000 / 1000 + 600  # 10 min depois do start do run RUNNING de BATCH


def collector21(client):
    return collector(client, wall=lambda: WALL)


def test_running_run_elapsed():  # AC-1
    text = collector21(FakeClient({"rag-cognus": BATCH, "rag-cognus-online": []})).collect()
    ids = {"experiment": "rag-cognus", "run_name": "run-12000"}
    assert sample(text, "rag_cognus_mlflow_run_running", **ids) == 1
    assert sample(text, "rag_cognus_mlflow_run_elapsed_seconds", **ids) == 600
    assert text.count("rag_cognus_mlflow_run_running{") == 1  # FINISHED/FAILED não entram


def test_running_runs_capped_and_named():  # AC-2
    runs = [run("RUNNING", 1_000 * i, name=f"lote {i}") for i in range(1, 9)]
    runs.append(run("RUNNING", 50_000, name=""))
    runs.append(run("RUNNING", 60_000, name='x "y"\n' + "z" * 100))
    text = collector21(FakeClient({"rag-cognus": runs, "rag-cognus-online": []})).collect()
    lines = [x for x in text.splitlines() if x.startswith("rag_cognus_mlflow_run_running{")]
    assert len(lines) == exp.MAX_RUNNING_RUNS == 5
    names = [x.split('run_name="')[1].split('"')[0] for x in lines]
    assert "unknown" in names and "lote_8" in names and "lote_1" not in names
    for name in names:
        assert len(name) <= 64 and " " not in name and "\\" not in name
    assert exp.run_label("rag-bm25-k5") == "rag-bm25-k5"


def test_running_partial_metrics_only_if_logged():  # AC-3
    runs = [
        run("RUNNING", 12_000, metrics={"index_build_seconds": 0.07}, name="rag-bm25-k5"),
        run("RUNNING", 11_000, name="sem-metricas"),
        run("FINISHED", 1_000, 2_000, {"quality_score/mean": 4.6}),
    ]
    text = collector21(FakeClient({"rag-cognus": runs, "rag-cognus-online": []})).collect()
    name = "rag_cognus_mlflow_running_run_metric"
    got = sample(
        text, name, experiment="rag-cognus", run_name="rag-bm25-k5", metric="index_build_seconds"
    )
    assert got == 0.07
    assert text.count(name + "{") == 1  # nada inventado para o run sem métricas
    assert 'metric="quality_score_mean"' not in "".join(
        x for x in text.splitlines() if x.startswith(name)
    )


def test_running_traces_and_cases():  # AC-4
    params = {**PARAMS, "cases": "14"}
    runs = [
        run("RUNNING", 12_000, params=params, name="com-casos"),
        run("RUNNING", 11_000, params={**PARAMS, "cases": "muitos"}, name="sem-casos"),
        run("FINISHED", 1_000, 2_000, {"m": 1.0}),
    ]
    client = FakeClient({"rag-cognus": runs, "rag-cognus-online": []}, traces={"r12000": 9})
    text = collector21(client).collect()
    ids = {"experiment": "rag-cognus", "run_name": "com-casos"}
    assert sample(text, "rag_cognus_mlflow_run_traces", **ids) == 9
    assert sample(text, "rag_cognus_mlflow_run_cases", **ids) == 14
    assert (
        sample(text, "rag_cognus_mlflow_run_cases", experiment="rag-cognus", run_name="sem-casos")
        is None
    )
    assert sorted(client.trace_calls) == ["r11000", "r12000"]  # só runs RUNNING


def test_traces_error_keeps_up():  # AC-4
    class NoTraces(FakeClient):
        def search_traces(self, *a, **k):
            raise RuntimeError("traces indisponíveis")

    text = collector21(NoTraces({"rag-cognus": BATCH, "rag-cognus-online": []})).collect()
    assert sample(text, "rag_cognus_mlflow_up") == 1
    assert "rag_cognus_mlflow_run_traces{" not in text
    assert "rag_cognus_mlflow_run_running{" in text


def test_last_run_info_and_timestamps():  # AC-5
    text = collector21(FakeClient({"rag-cognus": BATCH, "rag-cognus-online": []})).collect()
    info = "rag_cognus_mlflow_last_run_info"
    assert sample(text, info, experiment="rag-cognus", run_name="run-12000", status="RUNNING") == 1
    assert text.count(info + "{") == 1
    ended = "rag_cognus_mlflow_last_ended_timestamp_seconds"
    assert sample(text, ended, experiment="rag-cognus", run_name="run-10000", status="FAILED") == 11
    fin = "rag_cognus_mlflow_last_finished_timestamp_seconds"
    assert sample(text, fin, experiment="rag-cognus") == 9.0


def test_runs_total_zero_for_known_statuses():  # AC-6
    runs = [run("FINISHED", 1, 2, {"m": 1.0})]
    text = collector21(FakeClient({"rag-cognus": runs, "rag-cognus-online": []})).collect()
    for status in exp.STATUSES:
        got = sample(text, "rag_cognus_mlflow_runs_total", experiment="rag-cognus", status=status)
        assert got == (1 if status == "FINISHED" else 0), status
