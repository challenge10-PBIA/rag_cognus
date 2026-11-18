import json
from dataclasses import replace

import mlflow
import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from mlflow.genai.utils.trace_utils import (
    extract_expectations_from_trace,
    extract_retrieval_context_from_trace,
)

from rag_cognus.chain import RagPipeline
from rag_cognus.config import Settings
from rag_cognus.evaluation import evaluate
from rag_cognus.judges import make_judge
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
    assert summary["metrics"]["recall_at_k/mean"] == 1
    assert summary["metrics"]["precision_at_k/mean"] == 0.5
    assert summary["metrics"]["error/mean"] == 0
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


# ---------- spec 010 AC-7 e spec 011: params, traces e expectativas do lote ----------

ANSWER = {
    "resumo": "Use storytelling.",
    "fontes": [{"chunk_id": "a", "trecho": "Storytelling"}],
    "answerable": True,
    "cited_chunk_ids": ["a"],
}
JUDGMENT = {
    name: {"score": 4, "reason": "ok"}
    for name in ("context_relevance", "groundedness", "answer_relevance", "accuracy")
} | {"professionalism": {"score": 5, "reason": "ok"}}
DRAFT_CASE = {
    "case_id": "gold-01",
    "inputs": {"query": "storytelling"},
    "expectations": {
        "expected_niche": "apresentacoes_oratoria",
        "label_status": "draft",
        "relevant_chunk_ids": [],
        "expected_facts": [],
        "should_abstain": None,
    },
}


def _fake(payload):
    return RunnableLambda(lambda _: AIMessage(content=json.dumps(payload)))


def _settings(isolated_tracking, **kwargs):
    return replace(Settings(), tracking_uri=isolated_tracking, experiment="tests", **kwargs)


def _run(documents, settings, tmp_path, cases=(DRAFT_CASE,), pipeline=True, judge=True):
    retriever = GoldRetriever(documents, settings)
    rag = RagPipeline(retriever, settings, _fake(ANSWER)) if pipeline is True else pipeline
    summary = evaluate(
        list(cases),
        retriever,
        settings,
        pipeline=rag,
        judge=make_judge(settings, _fake(JUDGMENT)) if judge else None,
        output_dir=tmp_path,
    )
    mlflow.flush_trace_async_logging()
    traces = mlflow.search_traces(run_id=summary["run_id"], return_type="list")
    return summary, traces


def test_run_params_show_llm_options(documents, isolated_tracking, tmp_path):  # 010 AC-7
    settings = _settings(isolated_tracking, seed=42, judge_model="outro:7b")
    summary, _ = _run(documents, settings, tmp_path)
    params = mlflow.get_run(summary["run_id"]).data.params
    generator = json.loads(params["generator_options"])
    judge = json.loads(params["judge_options"])
    assert generator["model"] == "qwen3.5:9b" and judge["model"] == "outro:7b"
    for options, predict in ((generator, 900), (judge, 700)):
        assert options["temperature"] == 0 and options["seed"] == 42
        assert options["num_predict"] == predict and options["num_ctx"] == 16384
        assert "presence_penalty" in options and "repeat_penalty" in options
    assert params["judge_is_generator"] == "false"
    summary, _ = _run(documents, _settings(isolated_tracking), tmp_path)
    assert mlflow.get_run(summary["run_id"]).data.params["judge_is_generator"] == "true"


def test_case_id_is_a_tag_not_an_input(documents, isolated_tracking, tmp_path):  # 011 AC-4
    summary, traces = _run(documents, _settings(isolated_tracking), tmp_path)
    (trace,) = traces
    root = next(s for s in trace.data.spans if s.parent_id is None)
    assert "case_id" not in root.inputs and root.inputs["query"] == "storytelling"
    assert trace.info.tags["case_id"] == "gold-01"
    rows = json.loads((tmp_path / f"{summary['run_id']}.json").read_text())["results"]
    assert (rows["case_id"], rows["query"]) == (["gold-01"], ["storytelling"])
    assert rows["response"][0].startswith("Use storytelling")


def test_retrieval_only_trace_has_context(documents, isolated_tracking, tmp_path):  # 011 AC-4
    settings = _settings(isolated_tracking)
    _, (trace,) = _run(documents, settings, tmp_path, pipeline=None, judge=False)
    assert extract_retrieval_context_from_trace(trace)
    assert trace.info.tags["case_id"] == "gold-01" and trace.info.tags["flow"] == "retrieval"


def test_only_non_empty_expectations_are_logged(documents, isolated_tracking, tmp_path):  # AC-5
    _, (trace,) = _run(documents, _settings(isolated_tracking), tmp_path)
    assert extract_expectations_from_trace(trace) == {"expected_niche": "apresentacoes_oratoria"}
    assert trace.info.tags["label_status"] == "draft"


def test_ui_judge_uses_ollama_openai_endpoint(monkeypatch):  # 011 AC-11
    from mlflow.genai.judges.adapters.gateway_adapter import GatewayAdapter
    from mlflow.genai.judges.adapters.utils import get_adapter
    from mlflow.genai.judges.utils import get_default_model
    from mlflow.metrics.genai.model_utils import _get_provider_instance

    from rag_cognus.evaluation import ui_judge_env, ui_judge_model_uri

    settings = Settings(ollama_url="http://127.0.0.1:11434")
    assert ui_judge_model_uri(settings) == "openai:/qwen3.5:9b"
    assert ui_judge_model_uri(Settings(judge_model="juiz:7b")) == "openai:/juiz:7b"
    for url in (
        "http://127.0.0.1:11434/",
        "http://127.0.0.1:11434/v1",
        "http://127.0.0.1:11434/v1/",
    ):
        base = ui_judge_env(Settings(ollama_url=url))["OPENAI_API_BASE"]
        assert base == "http://127.0.0.1:11434/v1"
    env = ui_judge_env(settings)
    assert env["OPENAI_API_KEY"] == "ollama"
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    uri = get_default_model()
    assert uri == "openai:/qwen3.5:9b"
    assert isinstance(get_adapter(uri, "x"), GatewayAdapter)
    provider = _get_provider_instance("openai", "qwen3.5:9b")
    assert provider.get_endpoint_url("llm/v1/chat") == (
        "http://127.0.0.1:11434/v1/chat/completions"
    )


def test_failed_case_marks_trace_as_error(documents, isolated_tracking, tmp_path):  # AC-12
    class Broken:
        def predict(self, query, niche=None):
            raise RuntimeError("Ollama fora do ar")

    summary, (trace,) = _run(
        documents, _settings(isolated_tracking), tmp_path, pipeline=Broken(), judge=False
    )
    assert summary["metrics"]["error/mean"] == 1
    assert trace.info.state.value == "ERROR"
    assert trace.info.tags["error"] == "true"
