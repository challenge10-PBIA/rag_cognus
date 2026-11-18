"""Métricas Prometheus em memória, formato texto 0.0.4 (spec 016).

Sem dependência nova: só counter, gauge e histograma com labels. Um `Registry` por
`create_app()` (testes isolados) e por coleta do exporter do MLflow (spec 017).
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Iterable

CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"
LATENCY_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 20, 30, 60, 120)
SCORE_BUCKETS = (1, 2, 3, 4, 5)
UNMATCHED = "unmatched"
# Método vem do cliente: fora desta lista vira "OTHER" (cardinalidade fechada, AC-14).
HTTP_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})

# Relógio do middleware; trocado nos testes (AC-9).
clock = time.perf_counter


def _fmt(value: float) -> str:
    if math.isinf(value):
        return "+Inf" if value > 0 else "-Inf"
    if math.isnan(value):
        return "NaN"
    if float(value).is_integer():
        return str(int(value))
    return repr(float(value))


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _labels(names: Iterable[str], values: Iterable[str], extra: str = "") -> str:
    parts = [f'{n}="{_escape(str(v))}"' for n, v in zip(names, values, strict=True)]
    if extra:
        parts.append(extra)
    return "{" + ",".join(parts) + "}" if parts else ""


class _Metric:
    kind = ""

    def __init__(self, name: str, help_text: str, labelnames: tuple[str, ...], lock):
        self.name, self.help, self.labelnames, self._lock = name, help_text, labelnames, lock

    def _key(self, labels: dict[str, str]) -> tuple[str, ...]:
        if set(labels) != set(self.labelnames):
            raise ValueError(f"{self.name}: labels esperados {self.labelnames}, recebi {labels}")
        return tuple(str(labels[n]) for n in self.labelnames)

    def header(self) -> list[str]:
        return [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} {self.kind}"]


class Counter(_Metric):
    kind = "counter"

    def __init__(self, *args):
        super().__init__(*args)
        self._values: dict[tuple[str, ...], float] = {}

    def inc(self, amount: float = 1, **labels: str) -> None:
        key = self._key(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0) + amount

    def lines(self) -> list[str]:
        return [
            f"{self.name}{_labels(self.labelnames, k)} {_fmt(v)}"
            for k, v in sorted(self._values.items())
        ]


class Gauge(Counter):
    kind = "gauge"

    def set(self, value: float, **labels: str) -> None:
        key = self._key(labels)
        with self._lock:
            self._values[key] = float(value)


class Histogram(_Metric):
    kind = "histogram"

    def __init__(self, *args, buckets: Iterable[float]):
        super().__init__(*args)
        self.buckets = tuple(sorted(float(b) for b in buckets))
        self._series: dict[tuple[str, ...], tuple[list[int], list[float]]] = {}

    def observe(self, value: float, **labels: str) -> None:
        key = self._key(labels)
        with self._lock:
            counts, total = self._series.setdefault(key, ([0] * len(self.buckets), [0.0, 0]))
            for i, bound in enumerate(self.buckets):
                if value <= bound:
                    counts[i] += 1
            total[0] += value
            total[1] += 1

    def lines(self) -> list[str]:
        out = []
        for key, (counts, (total, count)) in sorted(self._series.items()):
            for bound, n in zip(self.buckets, counts, strict=True):
                le = f'le="{_fmt(bound)}"'
                out.append(f"{self.name}_bucket{_labels(self.labelnames, key, le)} {n}")
            inf = _labels(self.labelnames, key, 'le="+Inf"')
            out.append(f"{self.name}_bucket{inf} {_fmt(count)}")
            out.append(f"{self.name}_sum{_labels(self.labelnames, key)} {_fmt(total)}")
            out.append(f"{self.name}_count{_labels(self.labelnames, key)} {_fmt(count)}")
        return out


class Registry:
    """Conjunto de métricas de um processo/app; `render()` gera o texto 0.0.4."""

    def __init__(self):
        self._lock = threading.Lock()
        self._metrics: dict[str, _Metric] = {}

    def _add(self, metric: _Metric) -> _Metric:
        if metric.name in self._metrics:
            raise ValueError(f"Métrica duplicada: {metric.name}")
        self._metrics[metric.name] = metric
        return metric

    def counter(self, name: str, help_text: str, labelnames=()) -> Counter:
        return self._add(Counter(name, help_text, tuple(labelnames), self._lock))

    def gauge(self, name: str, help_text: str, labelnames=()) -> Gauge:
        return self._add(Gauge(name, help_text, tuple(labelnames), self._lock))

    def histogram(self, name: str, help_text: str, labelnames=(), *, buckets) -> Histogram:
        metric = Histogram(name, help_text, tuple(labelnames), self._lock, buckets=buckets)
        return self._add(metric)

    def get(self, name: str) -> _Metric:
        return self._metrics[name]

    def render(self) -> str:
        with self._lock:
            lines = []
            for metric in self._metrics.values():
                lines += metric.header() + metric.lines()
        return "\n".join(lines) + "\n"


# ---------- métricas da API ----------
HTTP_REQUESTS = "rag_cognus_http_requests_total"
HTTP_DURATION = "rag_cognus_http_request_duration_seconds"
ASK_DURATION = "rag_cognus_ask_duration_seconds"
JUDGE_SCORE = "rag_cognus_judge_score"
ONLINE_EVAL = "rag_cognus_online_eval_total"


def create_registry() -> Registry:
    """Registro com as métricas da API (um por `create_app()`, AC-11)."""
    registry = Registry()
    http = ("method", "route", "status")
    registry.counter(HTTP_REQUESTS, "Requisições HTTP atendidas pela API.", http)
    registry.histogram(
        HTTP_DURATION, "Duração das requisições HTTP em segundos.", http, buckets=LATENCY_BUCKETS
    )
    registry.histogram(
        ASK_DURATION,
        "Tempo do RAG (recuperação + LLM) no POST /v1/ask, em segundos.",
        ("outcome",),
        buckets=LATENCY_BUCKETS,
    )
    registry.histogram(
        JUDGE_SCORE, "Notas do juiz online (1 a 5) por métrica.", ("metric",), buckets=SCORE_BUCKETS
    )
    registry.counter(ONLINE_EVAL, "Avaliações online concluídas, por resultado.", ("outcome",))
    return registry


def _judge_metric_names() -> frozenset[str]:
    from rag_cognus.judges import METRICS

    return frozenset(METRICS) | {"quality_score"}


def record_judge_scores(registry: Registry, metrics: dict) -> None:
    """Observa as notas do juiz; ignora nomes fora de METRICS+quality_score e não numéricos."""
    histogram = registry.get(JUDGE_SCORE)
    for name in sorted(_judge_metric_names()):
        value = metrics.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        if math.isfinite(value):
            histogram.observe(float(value), metric=name)


def record_online_eval(registry: Registry, outcome: str) -> None:
    registry.get(ONLINE_EVAL).inc(outcome="ok" if outcome == "ok" else "error")


class MetricsMiddleware:
    """Middleware ASGI: conta e mede cada requisição pelo template da rota (AC-2…AC-9)."""

    def __init__(self, app, registry: Registry, skip: frozenset[str] = frozenset({"/metrics"})):
        self.app, self.registry, self.skip = app, registry, skip

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = clock()
        status = {"code": 500}

        async def tracking_send(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception:
            status["code"] = 500
            raise
        finally:
            self._record(scope, status["code"], started)

    def _record(self, scope, code: int, started: float) -> None:
        route = getattr(scope.get("route"), "path", None) or UNMATCHED
        if route in self.skip:
            return
        method = str(scope.get("method", "")).upper()
        method = method if method in HTTP_METHODS else "OTHER"
        labels = {"method": method, "route": route, "status": str(code)}
        self.registry.get(HTTP_REQUESTS).inc(**labels)
        self.registry.get(HTTP_DURATION).observe(max(clock() - started, 0.0), **labels)
