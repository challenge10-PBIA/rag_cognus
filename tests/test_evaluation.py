from dataclasses import replace

import pytest

from rag_cognus.config import Settings
from rag_cognus.evaluation import evaluate
from rag_cognus.metrics import retrieval_metrics, score_case
from rag_cognus.retrieval import GoldRetriever


def test_precision_uses_requested_k_and_recall_references():
    r = retrieval_metrics(["x", "a", "b"], ["a", "c"], 3)
    assert r["precision_at_k"] == pytest.approx(1 / 3)
    assert r["recall_at_k"] == 0.5 and r["mrr_at_k"] == 0.5
    with pytest.raises(ValueError):
        retrieval_metrics(["a", "a"], ["a"], 2)


def test_draft_labels_do_not_create_accuracy():
    row = {"expectations": {"label_status": "draft", "relevant_chunk_ids": ["a"]}}
    assert score_case(row, {"retrieved_chunk_ids": ["a"]}, 3) == {}


def test_mlflow_run_with_real_reference_contract(documents, isolated_tracking, tmp_path):
    settings = replace(Settings(), tracking_uri=isolated_tracking, experiment="tests", top_k=2)
    cases = [
        {
            "case_id": "reviewed",
            "inputs": {"query": "storytelling"},
            "expectations": {"label_status": "human_verified", "relevant_chunk_ids": ["a"]},
        }
    ]
    summary = evaluate(cases, GoldRetriever(documents, settings), settings, output_dir=tmp_path)
    assert summary["human_verified_cases"] == 1
    assert summary["metrics"]["recall_at_k"] == 1
    assert summary["metrics"]["precision_at_k"] == 0.5
    assert summary["metrics"]["error_rate"] == 0
    assert (tmp_path / (summary["run_id"] + ".json")).exists()


def test_rejects_labels_from_different_gold(documents, isolated_tracking):
    settings = replace(Settings(), tracking_uri=isolated_tracking, experiment="tests")
    cases = [
        {
            "case_id": "stale",
            "inputs": {"query": "storytelling"},
            "expectations": {"label_status": "human_verified", "relevant_chunk_ids": ["other"]},
        }
    ]
    with pytest.raises(ValueError, match="outro snapshot|ausentes"):
        evaluate(cases, GoldRetriever(documents, settings), settings)


def test_mlflow_genai_accepts_draft_optional_labels(isolated_tracking):
    import mlflow
    from mlflow.genai.scorers import scorer

    from rag_cognus.evaluation import to_genai_data

    @scorer
    def nonempty_response(outputs):
        return bool(outputs["response"])

    rows = [
        {
            "inputs": {"query": "teste"},
            "outputs": {"response": "teste"},
            "expectations": {
                "label_status": "draft",
                "should_abstain": None,
                "expected_niche": None,
                "expected_facts": [],
            },
        }
    ]
    with mlflow.start_run():
        result = mlflow.genai.evaluate(data=to_genai_data(rows), scorers=[nonempty_response])
    assert len(result.result_df) == 1
