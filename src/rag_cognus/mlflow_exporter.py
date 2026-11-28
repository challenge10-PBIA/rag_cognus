"""Exporter Prometheus do MLflow local (spec 017): `rag-cognus mlflow-exporter`.

Lê os experimentos de lote e online, publica as métricas do último run FINISHED de cada um
como gauges, os runs em andamento (spec 021: tempo decorrido, métricas já logadas, traces)
e serve `/metrics` com o servidor HTTP da stdlib. O Alloy faz o scrape e envia
ao Grafana Cloud; este processo nunca fala com a nuvem.
"""

from __future__ import annotations

import re
import threading
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from rag_cognus.api.metrics import CONTENT_TYPE, Registry
from rag_cognus.config import ensure_local_tracking

CACHE_SECONDS = 30
LABEL_MAX = 64
MAX_METRICS_PER_RUN = 100  # teto de séries por run (cardinalidade)
MAX_RUNNING_RUNS = 5  # runs RUNNING publicados por experimento (cardinalidade de run_name)
MAX_TRACES = 1_000  # teto de traces contados por run RUNNING
MAX_RUNS = 10_000  # teto de runs contados por experimento (10 páginas de 1000)
PAGE_SIZE = 1_000
BACKENDS = frozenset({"bm25", "dense", "not_used"})
STATUSES = frozenset({"RUNNING", "SCHEDULED", "FINISHED", "FAILED", "KILLED"})
ENDED = frozenset({"FINISHED", "FAILED", "KILLED"})
RUN_LABELS = ("experiment", "metric", "backend", "chat_model", "judge_model")

_NOT_METRIC = re.compile(r"[^a-z0-9_]+")
_NOT_MODEL = re.compile(r"[^A-Za-z0-9_.:/-]+")
_NOT_RUN = re.compile(r"[^A-Za-z0-9_.:-]+")


def metric_label(name: str) -> str | None:
    """Nome de métrica do MLflow → valor de label `[a-z0-9_]`, até 64 caracteres."""
    value = _NOT_METRIC.sub("_", str(name).lower()).strip("_")[:LABEL_MAX].strip("_")
    return value or None


def model_label(value: str | None) -> str:
    """Nome de modelo (ex.: `eriktonon/deepseek-v4.1-flash-1017:latest`) sem espaço, aspas nem quebra de linha."""
    if not value:
        return "unknown"
    clean = _NOT_MODEL.sub("_", str(value)).strip("_")[:LABEL_MAX]
    return clean or "unknown"


def run_label(value: str | None) -> str:
    """Nome do run (ex.: `rag-bm25-k5`) sem espaço, aspas, barra nem quebra; até 64."""
    clean = _NOT_RUN.sub("_", str(value or "")).strip("_")[:LABEL_MAX].strip("_")
    return clean or "unknown"


def backend_label(value: str | None) -> str:
    if not value:
        return "unknown"
    return value if value in BACKENDS else "other"


def _client(uri: str):
    """MlflowClient só se o servidor responder; evita minutos de retry com ele fora do ar."""
    from mlflow import MlflowClient

    if uri.startswith(("http://", "https://")):
        import httpx

        httpx.get(uri.rstrip("/") + "/health", timeout=2).raise_for_status()
    return MlflowClient(tracking_uri=uri)


def _create_registry() -> Registry:
    registry = Registry()
    registry.gauge("rag_cognus_mlflow_up", "1 se o MLflow local respondeu na última coleta.")
    registry.gauge(
        "rag_cognus_mlflow_run_metric",
        "Métricas do último run FINISHED de cada experimento.",
        RUN_LABELS,
    )
    registry.gauge(
        "rag_cognus_mlflow_runs_total",
        "Runs por status no experimento (até 10 mil mais recentes).",
        ("experiment", "status"),
    )
    registry.gauge(
        "rag_cognus_mlflow_last_run_timestamp_seconds",
        "Fim (epoch, s) do último run FINISHED do experimento.",
        ("experiment",),
    )
    # Spec 021: avaliação em lote em andamento e último run.
    ids = ("experiment", "run_name")
    registry.gauge("rag_cognus_mlflow_run_running", "1 para cada run RUNNING (até 5).", ids)
    registry.gauge(
        "rag_cognus_mlflow_run_elapsed_seconds", "Segundos desde o início do run RUNNING.", ids
    )
    registry.gauge(
        "rag_cognus_mlflow_running_run_metric",
        "Métricas já logadas num run RUNNING (progresso parcial registrado no MLflow).",
        ("experiment", "run_name", "metric"),
    )
    registry.gauge(
        "rag_cognus_mlflow_run_traces",
        "Traces ligados ao run RUNNING (o genai.evaluate grava um por caso; até 1000).",
        ids,
    )
    registry.gauge("rag_cognus_mlflow_run_cases", "Param `cases` do run RUNNING.", ids)
    registry.gauge(
        "rag_cognus_mlflow_last_run_info",
        "1 para o run mais recente (start_time) do experimento, com o status.",
        ("experiment", "run_name", "status"),
    )
    registry.gauge(
        "rag_cognus_mlflow_last_ended_timestamp_seconds",
        "Fim (epoch, s) do último run encerrado (FINISHED, FAILED ou KILLED).",
        ("experiment", "run_name", "status"),
    )
    registry.gauge(
        "rag_cognus_mlflow_last_finished_timestamp_seconds",
        "Fim (epoch, s) do último run FINISHED do experimento.",
        ("experiment",),
    )
    return registry


class MlflowCollector:
    """Coleta com cache de `ttl` s; MLflow fora do ar vira `rag_cognus_mlflow_up 0`."""

    def __init__(
        self,
        settings,
        client_factory=_client,
        now=time.monotonic,
        ttl=CACHE_SECONDS,
        wall=time.time,
    ):
        self.uri = ensure_local_tracking(settings.tracking_uri)
        self.experiments = list(dict.fromkeys([settings.experiment, settings.online_experiment]))
        self.client_factory, self.now, self.ttl, self.wall = client_factory, now, ttl, wall
        self._lock = threading.Lock()
        self._cached: tuple[float, str] | None = None

    def collect(self) -> str:
        with self._lock:
            now = self.now()
            if self._cached and now - self._cached[0] < self.ttl:
                return self._cached[1]
            text = self._build()
            self._cached = (now, text)
            return text

    def _build(self) -> str:
        registry = _create_registry()
        try:
            client = self.client_factory(self.uri)
            for name in self.experiments:
                self._experiment(registry, client, name)
        except Exception:  # conexão recusada, 5xx, timeout: só sinaliza
            registry = _create_registry()
            registry.get("rag_cognus_mlflow_up").set(0)
            return registry.render()
        registry.get("rag_cognus_mlflow_up").set(1)
        return registry.render()

    def _runs(self, client, experiment_id: str) -> list:
        runs, token = [], None
        while len(runs) < MAX_RUNS:
            page = client.search_runs(
                [experiment_id],
                max_results=PAGE_SIZE,
                order_by=["attributes.start_time DESC"],
                page_token=token,
            )
            runs += list(page)
            token = getattr(page, "token", None)
            if not token:
                break
        return runs[:MAX_RUNS]

    def _experiment(self, registry: Registry, client, name: str) -> None:
        experiment = client.get_experiment_by_name(name)
        if experiment is None:
            return  # experimento ainda não criado: não é erro
        runs = self._runs(client, experiment.experiment_id)
        statuses = Counter(r.info.status if r.info.status in STATUSES else "OTHER" for r in runs)
        statuses.update(dict.fromkeys(STATUSES, 0))  # FAILED existe antes da 1ª falha (delta)
        for status, count in statuses.items():
            registry.get("rag_cognus_mlflow_runs_total").set(count, experiment=name, status=status)
        if not runs:
            return
        latest = max(runs, key=lambda r: r.info.start_time or 0)
        registry.get("rag_cognus_mlflow_last_run_info").set(
            1, experiment=name, run_name=run_label(latest.info.run_name), status=_status(latest)
        )
        ended = [r for r in runs if r.info.status in ENDED and r.info.end_time]
        if ended:
            last_end = max(ended, key=lambda r: r.info.end_time)
            registry.get("rag_cognus_mlflow_last_ended_timestamp_seconds").set(
                last_end.info.end_time / 1000,
                experiment=name,
                run_name=run_label(last_end.info.run_name),
                status=last_end.info.status,
            )
        self._running(registry, client, experiment.experiment_id, name, runs)
        finished = [r for r in runs if r.info.status == "FINISHED"]
        if not finished:
            return
        last = max(finished, key=lambda r: (r.info.end_time or 0, r.info.start_time or 0))
        stamp = (last.info.end_time or last.info.start_time or 0) / 1000
        registry.get("rag_cognus_mlflow_last_run_timestamp_seconds").set(stamp, experiment=name)
        registry.get("rag_cognus_mlflow_last_finished_timestamp_seconds").set(
            stamp, experiment=name
        )
        params = last.data.params or {}
        base = {
            "experiment": name,
            "backend": backend_label(params.get("backend")),
            "chat_model": model_label(params.get("chat_model")),
            "judge_model": model_label(params.get("judge_model")),
        }
        _set_metrics(registry.get("rag_cognus_mlflow_run_metric"), last, base)

    def _running(self, registry: Registry, client, experiment_id: str, name: str, runs) -> None:
        """Runs RUNNING: só o que o MLflow registrou (tempo, métricas logadas, traces)."""
        running = [r for r in runs if r.info.status == "RUNNING"]
        running.sort(key=lambda r: r.info.start_time or 0, reverse=True)
        seen: set[str] = set()
        now = self.wall()
        for r in running:
            if len(seen) >= MAX_RUNNING_RUNS:
                break
            label = run_label(r.info.run_name)
            if label in seen:
                continue
            seen.add(label)
            ids = {"experiment": name, "run_name": label}
            registry.get("rag_cognus_mlflow_run_running").set(1, **ids)
            elapsed = max(0.0, now - (r.info.start_time or 0) / 1000)
            registry.get("rag_cognus_mlflow_run_elapsed_seconds").set(elapsed, **ids)
            _set_metrics(registry.get("rag_cognus_mlflow_running_run_metric"), r, ids)
            cases = str((r.data.params or {}).get("cases", "")).strip()
            if cases.isdigit():
                registry.get("rag_cognus_mlflow_run_cases").set(int(cases), **ids)
            traces = _count_traces(client, experiment_id, r.info.run_id)
            if traces is not None:
                registry.get("rag_cognus_mlflow_run_traces").set(traces, **ids)


def _status(run) -> str:
    return run.info.status if run.info.status in STATUSES else "OTHER"


def _set_metrics(gauge, run, base: dict) -> None:
    published = set()
    for raw, value in sorted((run.data.metrics or {}).items()):
        metric = metric_label(raw)
        if metric is None or metric in published or len(published) >= MAX_METRICS_PER_RUN:
            continue
        published.add(metric)
        gauge.set(float(value), metric=metric, **base)


def _count_traces(client, experiment_id: str, run_id: str) -> int | None:
    """Traces do run (progresso real do genai.evaluate); erro → None, sem derrubar a coleta."""
    total, token = 0, None
    try:
        while total < MAX_TRACES:
            page = client.search_traces(
                experiment_ids=[experiment_id],
                run_id=run_id,
                max_results=min(500, MAX_TRACES - total),
                page_token=token,
                include_spans=False,
            )
            total += len(list(page))
            token = getattr(page, "token", None)
            if not token:
                break
    except Exception:
        return None
    return min(total, MAX_TRACES)


def make_server(collector: MlflowCollector, host: str, port: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (nome exigido pelo http.server)
            if self.path.split("?")[0] != "/metrics":
                self.send_error(404, "Use /metrics")
                return
            body = collector.collect().encode()
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPE)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):  # scrape a cada 15 s: sem log por pedido
            pass

    return ThreadingHTTPServer((host, port), Handler)


def serve(settings, host: str, port: int) -> None:
    import os

    os.environ.setdefault("MLFLOW_HTTP_REQUEST_MAX_RETRIES", "1")
    os.environ.setdefault("MLFLOW_HTTP_REQUEST_TIMEOUT", "5")
    collector = MlflowCollector(settings)
    server = make_server(collector, host, port)
    if host not in {"127.0.0.1", "localhost", "::1"}:
        print(f"Aviso: escutando em {host}; o /metrics fica visível para a rede local.")
    print(f"Exporter do MLflow ({collector.uri}) em http://{host}:{port}/metrics")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
