import pytest

from rag_cognus.config import Settings
from rag_cognus.context_eval import (
    context_statistics,
    correlations,
    evaluate_context,
    judged_precision,
    validate_judgment,
)


def hit(cid, doc, text="um dois tres quatro cinco seis sete"):
    return {"chunk_id": cid, "text": text, "metadata": {"doc_id": doc}}


def test_sources_are_documents_not_number_of_chunks():
    out = {
        "retrieved_context": [hit("a", "d1"), hit("b", "d1"), hit("c", "d2")],
        "response": "Resposta",
        "abstained": False,
        "cited_chunk_ids": ["a", "b"],
    }
    s = context_statistics(out)
    assert s["unique_sources"] == 2
    assert s["source_diversity"] == pytest.approx(2 / 3)
    assert s["cited_sources"] == 1 and s["citation_source_coverage"] == 0.5
    assert s["context_redundancy_5gram"] == pytest.approx(2 / 3)
    out["cited_chunk_ids"] = ["inventado"]
    assert context_statistics(out)["invalid_citations"] == 1
    assert context_statistics(out)["citation_integrity"] == 0


def test_ranked_precision_differs_from_fraction_relevant():
    a = judged_precision([True, False, False])
    b = judged_precision([False, False, True])
    assert a["context_relevance_judge"] == b["context_relevance_judge"] == 1 / 3
    assert a["context_precision_ranked_judge"] == 1
    assert b["context_precision_ranked_judge"] == 1 / 3
    assert judged_precision([])["context_precision_ranked_judge"] == 0


def test_judge_cannot_invent_or_repeat_ids():
    payload = {
        "judgments": [{"chunk_id": "fake", "relevant": True, "reason": "teste"}],
        "sufficient": True,
        "rationale": "teste",
        "answer_grounded": None,
    }
    with pytest.raises(ValueError, match="IDs"):
        validate_judgment(payload, [hit("a", "d1")])


def test_correlations_require_sample_and_variation():
    rows = [
        {"source_diversity": i, "context_characters": i * 2, "context_sufficiency_judge": 1}
        for i in range(6)
    ]
    report = correlations(rows)
    result = next(
        r
        for r in report
        if r["metric_a"] == "source_diversity" and r["metric_b"] == "context_characters"
    )
    assert result["pearson_r"] == pytest.approx(1)
    assert result["status"] == "exploratorio_nao_causal"
    assert all(r["pearson_r"] is None for r in correlations(rows[:2]))
    constant = next(
        r
        for r in report
        if r["metric_a"] == "context_sufficiency_judge" and r["metric_b"] == "source_diversity"
    )
    assert constant["status"] == "sem_variacao"


def test_context_evaluation_rejects_databricks_tracking_before_reading_files():
    with pytest.raises(ValueError, match="somente no MLflow local"):
        evaluate_context("inexistente", Settings(tracking_uri="databricks://projeto"))


def test_short_aliases_map_back_to_original_sources_and_cache(monkeypatch, tmp_path):
    from rag_cognus import context_eval

    calls = []

    class Chain:
        def invoke(self, payload):
            calls.append(payload)
            return {
                "judgments": [
                    {"chunk_id": "C2", "relevant": False, "reason": "fora da pergunta"},
                    {"chunk_id": "C1", "relevant": True, "reason": "apoia a pergunta"},
                ],
                "sufficient": True,
                "rationale": "um trecho apoia a resposta",
                "answer_grounded": None,
            }

    monkeypatch.setattr(context_eval, "_judge_chain", lambda *_: Chain())
    hits = [hit("hash-original-a", "d1"), hit("hash-original-b", "d2")]
    first = context_eval.judge_context(Settings(), "pergunta", hits, None, tmp_path, "digest1")
    mapping = {j.chunk_id: j.relevant for j in first.judgments}
    assert mapping == {"hash-original-a": True, "hash-original-b": False}
    context_eval.judge_context(Settings(), "pergunta", hits, None, tmp_path, "digest1")
    assert len(calls) == 1
    context_eval.judge_context(Settings(), "pergunta", hits, None, tmp_path, "digest2")
    assert len(calls) == 2
