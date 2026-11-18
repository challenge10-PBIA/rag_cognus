"""Avaliação no MLflow open source local: recuperação, citações e qualidade da resposta."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import mlflow
from mlflow.entities import AssessmentSource, Feedback
from mlflow.genai.scorers import scorer

from rag_cognus.config import Settings, ensure_local_tracking
from rag_cognus.judges import METRICS, as_dict, judge_response
from rag_cognus.metrics import score_case

EVAL_TAG = "rag_cognus_eval"
ONLINE_TAG = "rag_cognus_online"


def configure_tracking(settings: Settings):
    mlflow.set_tracking_uri(ensure_local_tracking(settings.tracking_uri))
    mlflow.set_experiment(settings.experiment)


def load_cases(path: str | Path) -> list[dict]:
    cases = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if not cases:
        raise ValueError("Conjunto de avaliação vazio.")
    ids = set()
    for case in cases:
        if case["case_id"] in ids or not case["inputs"]["query"].strip():
            raise ValueError("Caso duplicado ou pergunta vazia.")
        ids.add(case["case_id"])
    return cases


def _expectations(case: dict) -> dict:
    # MLflow não aceita expectativas com valor None.
    return {k: v for k, v in case.get("expectations", {}).items() if v is not None}


def _build_scorers(settings: Settings, judge, generate: bool):
    @scorer
    def operational(outputs):
        return [
            Feedback(name="latency_seconds", value=float(outputs.get("latency_seconds", 0))),
            Feedback(name="error", value=float(bool(outputs.get("error")))),
        ]

    @scorer
    def retrieval_and_citations(outputs, expectations):
        if outputs.get("error"):
            return Feedback(name="citation_integrity", value=0.0, rationale=outputs["error"])
        case = {"expectations": expectations or {}}
        values = score_case(case, outputs, settings.top_k)
        return [Feedback(name=k, value=float(v)) for k, v in values.items()] or Feedback(
            name="retrieved_chunks", value=float(len(outputs.get("retrieved_chunk_ids", [])))
        )

    scorers = [operational, retrieval_and_citations]
    if generate and judge is not None:
        source = AssessmentSource(source_type="LLM_JUDGE", source_id=settings.judge)

        @scorer
        def response_quality(inputs, outputs, expectations):
            if outputs.get("error"):
                return Feedback(name="quality_score", error=outputs["error"])
            facts = (expectations or {}).get("expected_facts")
            judgment = judge_response(judge, inputs["query"], outputs, facts)
            feedback = [
                Feedback(
                    name=name,
                    value=getattr(judgment, name).score,
                    rationale=getattr(judgment, name).reason,
                    source=source,
                )
                for name in METRICS
            ]
            overall = as_dict(judgment)["quality_score"]
            return feedback + [Feedback(name="quality_score", value=overall, source=source)]

        scorers.append(response_quality)
    return scorers


def evaluate(
    cases: list[dict],
    retriever,
    settings: Settings,
    pipeline=None,
    judge=None,
    output_dir: str | Path = "outputs",
    run_name: str | None = None,
) -> dict:
    """Roda os casos, registra traces + notas por pergunta e médias no run do MLflow."""
    if not cases:
        raise ValueError("Conjunto de avaliação vazio.")
    configure_tracking(settings)
    known = {d.metadata["chunk_id"] for d in retriever.documents}
    for c in cases:
        e = c.get("expectations", {})
        if (
            e.get("label_status") == "human_verified"
            and set(e.get("relevant_chunk_ids", [])) - known
        ):
            raise ValueError("Referências humanas ausentes deste snapshot Gold; revisar dataset.")

    @mlflow.trace(name="rag_cognus_case", span_type="CHAIN")
    def predict(query: str, case_id: str = "", niche: str | None = None) -> dict:
        start = time.perf_counter()
        try:
            if pipeline:
                output = pipeline.predict(query, niche)
            else:
                docs = retriever.retrieve(query, niche)
                output = {
                    "retrieved_chunk_ids": [d.id for d in docs],
                    "retrieved_context": [
                        {"chunk_id": d.id, "text": d.page_content, "metadata": d.metadata}
                        for d in docs
                    ],
                }
        except Exception as exc:  # erro vira métrica, não interrompe a avaliação
            output = {"error": f"{type(exc).__name__}: {exc}"}
        output["latency_seconds"] = time.perf_counter() - start
        return output

    mode = "rag" if pipeline else "retrieval"
    judged = bool(pipeline and judge)
    data = [
        {"inputs": {**c["inputs"], "case_id": c["case_id"]}, "expectations": _expectations(c)}
        for c in cases
    ]
    # Ollama local atende uma requisição por vez; paralelismo só distorce a latência.
    os.environ.setdefault("MLFLOW_GENAI_EVAL_MAX_WORKERS", "1")
    with mlflow.start_run(
        run_name=run_name or f"{mode}-{settings.backend}-k{settings.top_k}"
    ) as run:
        mlflow.set_tags({EVAL_TAG: "true", "mode": mode, "judged": str(judged).lower()})
        payload = json.dumps(sorted((d.id, d.page_content) for d in retriever.documents))
        mlflow.log_params(
            {
                "backend": settings.backend,
                "top_k": settings.top_k,
                "chat_model": settings.chat_model if pipeline else "not_used",
                "judge_model": settings.judge if judged else "not_used",
                "gold_view": settings.gold_view,
                "gold_chunk_count": len(known),
                "gold_fingerprint": hashlib.sha256(payload.encode()).hexdigest()[:16],
                "cases": len(cases),
            }
        )
        mlflow.log_metric("index_build_seconds", retriever.build_seconds)
        result = mlflow.genai.evaluate(
            data=data, predict_fn=predict, scorers=_build_scorers(settings, judge, bool(pipeline))
        )
        metrics = {k: float(v) for k, v in result.metrics.items()}
        expectation_keys = {k for row in data for k in row["expectations"]}
        rows = _per_case_rows(result.result_df, expectation_keys)
        mlflow.log_table(rows, "per_case.json")
        summary = {"run_id": run.info.run_id, "mode": mode, "judged": judged, "metrics": metrics}
        folder = Path(output_dir)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{run.info.run_id}.json").write_text(
            json.dumps({"summary": summary, "results": rows}, ensure_ascii=False, indent=2)
        )
    return summary


def _per_case_rows(df, skip: set[str]) -> dict:
    """Tabela por pergunta (colunas -> listas) para mlflow.log_table e o app."""
    names = sorted(
        {str(c).removesuffix("/value") for c in df.columns if str(c).endswith("/value")} - skip
    )
    table = {"case_id": [], "query": [], "response": []}
    table.update({n: [] for n in names})
    for _, row in df.iterrows():
        request, response = _as_dict(row.get("request")), _as_dict(row.get("response"))
        table["case_id"].append(request.get("case_id", ""))
        table["query"].append(request.get("query", ""))
        table["response"].append(response.get("response") or response.get("error") or "")
        for n in names:
            value = row.get(f"{n}/value")
            table[n].append(None if value is None or value != value else value)
    return table


def _as_dict(value) -> dict:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return {}
    return value if isinstance(value, dict) else {}


# ---------- avaliação online de cada /v1/ask (spec 004) ----------
def score_online(
    judge, query: str, output: dict, *, niche: str | None, latency_seconds: float, k: int = 5
) -> dict:
    """Notas do juiz + métricas determinísticas com os mesmos nomes do lote."""
    judgment = judge_response(judge, query, output)
    case = {"expectations": {"expected_niche": niche}} if niche else {}
    extra = score_case(case, output, k)
    metrics = as_dict(judgment) | {
        "niche_metadata_precision_proxy": extra.get("niche_metadata_precision_proxy"),
        "citation_integrity": extra.get("citation_integrity", 0.0),
        "latency_seconds": float(latency_seconds),
    }
    judges = [
        {
            "name": name,
            "label": label,
            "score": getattr(judgment, name).score,
            "reason": getattr(judgment, name).reason,
        }
        for name, label in METRICS.items()
    ]
    return {"metrics": metrics, "judges": judges}


def online_run_payload(
    settings: Settings,
    ask_id: str,
    output: dict,
    scored: dict,
    niche: str | None,
    trace_id: str | None,
) -> dict:
    """O que o logger online registra: um run por ask no experimento online."""
    return {
        "experiment": settings.online_experiment,
        "run_name": f"ask-{ask_id}",
        "tags": {
            ONLINE_TAG: "true",
            "ask_id": ask_id,
            "abstained": str(bool(output.get("abstained"))).lower(),
        },
        "params": {
            "chat_model": settings.chat_model,
            "judge_model": settings.judge,
            "backend": settings.backend,
            "top_k": str(settings.top_k),
            "niche": niche or "none",
            "gold_view": settings.gold_view,
        },
        "metrics": {k: float(v) for k, v in scored["metrics"].items() if v is not None},
        "judges": scored["judges"],
        "judge_model": settings.judge,
        "trace_id": trace_id,
    }


def log_online_evaluation(settings: Settings, payload: dict) -> str:
    """Grava o run online no MLflow local e as notas do juiz como assessments do trace."""
    from mlflow import MlflowClient
    from mlflow.entities import Metric, Param

    uri = ensure_local_tracking(settings.tracking_uri)
    client = MlflowClient(tracking_uri=uri)
    # Garante o experimento na hora de logar: o MLflow pode ter subido depois da API.
    experiment = client.get_experiment_by_name(payload["experiment"])
    experiment_id = (
        experiment.experiment_id if experiment else client.create_experiment(payload["experiment"])
    )
    tags = dict(payload["tags"])
    if payload.get("trace_id"):
        tags["trace_id"] = payload["trace_id"]
    run = client.create_run(experiment_id, run_name=payload["run_name"], tags=tags)
    run_id = run.info.run_id
    try:
        now = int(time.time() * 1000)
        client.log_batch(
            run_id,
            metrics=[Metric(k, v, now, 0) for k, v in payload["metrics"].items()],
            params=[Param(k, str(v)) for k, v in payload["params"].items()],
        )
        trace_id = payload.get("trace_id")
        if trace_id:
            if mlflow.get_tracking_uri() != uri:
                mlflow.set_tracking_uri(uri)
            mlflow.flush_trace_async_logging()
            source = AssessmentSource(source_type="LLM_JUDGE", source_id=payload["judge_model"])
            for item in payload["judges"]:
                mlflow.log_feedback(
                    trace_id=trace_id,
                    name=item["name"],
                    value=item["score"],
                    rationale=item["reason"],
                    source=source,
                )
            client.link_traces_to_run([trace_id], run_id)
        client.set_terminated(run_id)
    except Exception:
        client.set_terminated(run_id, status="FAILED")
        raise
    return run_id
