import json
from dataclasses import replace

import mlflow
import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from rag_cognus.chain import RagPipeline
from rag_cognus.config import Settings
from rag_cognus.evaluation import evaluate
from rag_cognus.judges import METRICS, as_dict, judge_response, make_judge
from rag_cognus.retrieval import GoldRetriever

SCORES = {
    "context_relevance": 5,
    "groundedness": 4,
    "answer_relevance": 5,
    "accuracy": 3,
    "professionalism": 4,
}


def fake_judge():
    payload = {k: {"score": v, "reason": "ok"} for k, v in SCORES.items()}
    return make_judge(Settings(), RunnableLambda(lambda _: AIMessage(json.dumps(payload))))


def fake_rag(documents, settings):
    answer = {"answer": "Use storytelling.", "answerable": True, "cited_chunk_ids": ["a"]}
    chat = RunnableLambda(lambda _: AIMessage(content=json.dumps(answer)))
    return RagPipeline(GoldRetriever(documents, settings), settings, chat)


def test_judge_returns_all_scores_and_mean():
    out = {"response": "x", "retrieved_context": [{"chunk_id": "a", "text": "t"}]}
    scores = as_dict(judge_response(fake_judge(), "pergunta", out))
    assert set(METRICS) <= set(scores)
    assert scores["quality_score"] == pytest.approx(21 / 5)


def test_judge_rejects_out_of_scale_score():
    bad = {k: {"score": 9, "reason": "x"} for k in SCORES}
    judge = make_judge(Settings(), RunnableLambda(lambda _: AIMessage(json.dumps(bad))))
    with pytest.raises(ValueError):
        judge_response(judge, "q", {"response": "x"})


def test_evaluate_logs_response_metrics_to_mlflow(documents, isolated_tracking, tmp_path):
    settings = replace(Settings(), tracking_uri=isolated_tracking, experiment="tests", top_k=2)
    pipeline = fake_rag(documents, settings)
    cases = [{"case_id": "c1", "inputs": {"query": "storytelling"}, "expectations": {}}]
    summary = evaluate(
        cases, pipeline.retriever, settings, pipeline, fake_judge(), output_dir=tmp_path
    )
    run = mlflow.get_run(summary["run_id"])
    assert run.data.metrics["accuracy/mean"] == 3
    assert run.data.metrics["professionalism/mean"] == 4
    assert run.data.metrics["citation_integrity/mean"] == 1
    assert run.data.metrics["error/mean"] == 0
    table = mlflow.load_table("per_case.json", run_ids=[summary["run_id"]])
    assert table.loc[0, "case_id"] == "c1" and table.loc[0, "groundedness"] == 4
    assert "expected_facts" not in table.columns


def test_pipeline_errors_become_metrics(documents, isolated_tracking, tmp_path):
    settings = replace(Settings(), tracking_uri=isolated_tracking, experiment="tests")
    bad = {"answer": "x", "answerable": True, "cited_chunk_ids": ["inventado"]}
    chat = RunnableLambda(lambda _: AIMessage(content=json.dumps(bad)))
    pipeline = RagPipeline(GoldRetriever(documents, settings), settings, chat)
    cases = [{"case_id": "c1", "inputs": {"query": "storytelling"}}]
    summary = evaluate(cases, pipeline.retriever, settings, pipeline, output_dir=tmp_path)
    assert summary["metrics"]["error/mean"] == 1


def test_databricks_tracking_is_rejected():
    with pytest.raises(ValueError, match="MLflow local"):
        Settings(tracking_uri="databricks://projeto")
    assert Settings().tracking_uri == "http://127.0.0.1:5001"
