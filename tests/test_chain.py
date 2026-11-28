import json

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from rag_cognus.chain import ABSTENTION, RagPipeline
from rag_cognus.config import Settings
from rag_cognus.retrieval import GoldRetriever


def pipeline(documents, answer):
    chat = RunnableLambda(lambda _: AIMessage(content=json.dumps(answer)))
    return RagPipeline(GoldRetriever(documents, Settings()), Settings(), chat)


def test_valid_citation(documents):
    result = pipeline(
        documents,
        {
            "answer": "Use storytelling na apresentação.",
            "answerable": True,
            "cited_chunk_ids": ["a"],
        },
    ).predict("storytelling")
    assert result["cited_chunk_ids"] == ["a"]
    assert result["citations"][0]["source_url"] == "https://example.org/a"


def test_rejects_fabricated_citation(documents):
    p = pipeline(
        documents, {"answer": "Texto", "answerable": True, "cited_chunk_ids": ["inventado"]}
    )
    with pytest.raises(ValueError, match="ID ausente"):
        p.predict("storytelling")


def test_rejects_answer_without_citation(documents):
    p = pipeline(documents, {"answer": "Texto", "answerable": True, "cited_chunk_ids": []})
    with pytest.raises(ValueError, match="sem fontes"):
        p.predict("storytelling")


def test_no_context_abstains_without_llm(documents):
    def fail(_):
        raise AssertionError("Não deveria chamar o modelo")

    p = RagPipeline(GoldRetriever(documents, Settings()), Settings(), RunnableLambda(fail))
    assert p.predict("zzzzdesconhecido")["response"] == ABSTENTION


def structured(**overrides):
    answer = {
        "resumo": "Use storytelling para dar clareza.",
        "pontos": ["Comece pelo conflito.", "Feche com a mensagem principal."],
        "recomendacao": "Ensaie a história em voz alta.",
        "fontes": [{"chunk_id": "a", "trecho": "Storytelling e  oratória"}],
        "answerable": True,
        "cited_chunk_ids": ["a"],
    }
    return answer | overrides


def test_structured_answer_fields_and_response_text(documents):  # AC-9, AC-12
    result = pipeline(documents, structured()).predict("storytelling")
    assert result["structured"] == {
        "resumo": "Use storytelling para dar clareza.",
        "pontos": ["Comece pelo conflito.", "Feche com a mensagem principal."],
        "recomendacao": "Ensaie a história em voz alta.",
        "fontes": [
            {
                "chunk_id": "a",
                "titulo": "a",
                "nicho": "apresentacoes_oratoria",
                "url": "https://example.org/a",
                "trecho": "Storytelling e oratória",
            }
        ],
    }
    assert result["response"] == (
        "Use storytelling para dar clareza.\n\n"
        "- Comece pelo conflito.\n- Feche com a mensagem principal.\n\n"
        "Recomendação: Ensaie a história em voz alta."
    )
    assert result["cited_chunk_ids"] == ["a"] and not result["abstained"]


def test_answer_limits_points_to_five(documents):  # AC-9
    p = pipeline(documents, structured(pontos=[f"p{i}" for i in range(6)]))
    with pytest.raises(ValueError):
        p.predict("storytelling")


def test_source_metadata_comes_from_chunk_not_llm(documents):  # AC-10
    fonte = {"chunk_id": "a", "trecho": "oratória", "titulo": "Inventado", "url": "x"}
    with pytest.raises(ValueError):
        pipeline(documents, structured(fontes=[fonte])).predict("storytelling")
    docs = [d.model_copy(deep=True) for d in documents]
    docs[0].metadata["nichos_json"] = json.dumps(["clareza_linguagem", "apresentacoes_oratoria"])
    result = pipeline(docs, structured()).predict("storytelling", "apresentacoes_oratoria")
    assert result["structured"]["fontes"][0]["nicho"] == "apresentacoes_oratoria"
    result = pipeline(docs, structured()).predict("storytelling")
    assert result["structured"]["fontes"][0]["nicho"] == "clareza_linguagem"
    docs[0].metadata["nichos_json"] = "[]"
    fontes = pipeline(docs, structured()).predict("storytelling")["structured"]["fontes"]
    assert fontes[0]["nicho"] is None


def test_excerpt_must_be_literal_or_falls_back(documents):  # AC-11
    docs = [d.model_copy(deep=True) for d in documents]
    docs[0].page_content = "Storytelling " + "palavra " * 60 + "fim."
    fonte = {"chunk_id": "a", "trecho": "frase que não está no trecho"}
    result = pipeline(docs, structured(fontes=[fonte])).predict("storytelling")
    trecho = result["structured"]["fontes"][0]["trecho"]
    assert len(trecho) <= 240 and trecho.endswith("palavra")
    assert docs[0].page_content.startswith(trecho)
    bad = structured(fontes=[{"chunk_id": "inventado", "trecho": "x"}])
    with pytest.raises(ValueError, match="ID ausente"):
        pipeline(documents, bad).predict("storytelling")


def test_cited_chunk_without_excerpt_still_listed_in_sources(documents):  # AC-11
    result = pipeline(documents, structured(fontes=[], recomendacao=None)).predict("storytelling")
    assert [f["chunk_id"] for f in result["structured"]["fontes"]] == ["a"]
    assert "Recomendação" not in result["response"]


def test_abstention_structured(documents):  # AC-12
    answer = structured(answerable=False, fontes=[], cited_chunk_ids=[])
    for result in (
        pipeline(documents, answer).predict("storytelling"),
        pipeline(documents, answer).predict("zzzzdesconhecido"),
    ):
        assert result["response"] == ABSTENTION and result["abstained"]
        assert result["structured"] == {
            "resumo": ABSTENTION,
            "pontos": [],
            "recomendacao": None,
            "fontes": [],
        }
        assert result["citations"] == []


def test_prompt_asks_for_structured_json():  # AC-9
    from rag_cognus.chain import SYSTEM

    for key in ("resumo", "pontos", "recomendacao", "fontes", "trecho"):
        assert key in SYSTEM


# ---------- spec 011: contrato do trace para os juízes do MLflow ----------


def last_trace():
    import mlflow

    mlflow.flush_trace_async_logging()
    return mlflow.get_trace(mlflow.get_last_active_trace_id())


def root_span(trace):
    return next(s for s in trace.data.spans if s.parent_id is None)


def test_root_span_is_lean_and_return_unchanged(documents):  # 011 AC-1
    result = pipeline(documents, structured()).predict("storytelling", "apresentacoes_oratoria")
    root = root_span(last_trace())
    assert root.name == "rag_cognus"
    assert root.inputs == {"query": "storytelling", "niche": "apresentacoes_oratoria"}
    assert set(root.outputs) == {"response", "abstained", "cited_chunk_ids", "fontes"}
    assert root.outputs["response"] == result["response"]
    for key in ("retrieved_context", "structured", "citations", "retrieved_chunk_ids"):
        assert key in result


def test_previews_show_question_and_answer(documents):  # 011 AC-2
    result = pipeline(documents, structured()).predict("storytelling")
    info = last_trace().info
    assert info.request_preview == "storytelling"
    assert info.response_preview == result["response"]
    pipeline(documents, structured()).predict("zzzzdesconhecido")
    assert last_trace().info.response_preview == ABSTENTION


def test_rag_trace_is_readable_by_mlflow_judges(documents):  # 011 AC-9
    from mlflow.genai.utils.trace_utils import (
        extract_request_from_trace,
        extract_response_from_trace,
        resolve_inputs_from_trace,
        resolve_outputs_from_trace,
    )

    result = pipeline(documents, structured()).predict("storytelling")
    trace = last_trace()
    assert resolve_inputs_from_trace(None, trace) and resolve_outputs_from_trace(None, trace)
    assert "storytelling" in extract_request_from_trace(trace)
    # O MLflow serializa o dict de saída em JSON com escape ASCII (ó vira \\u00f3).
    assert json.loads(extract_response_from_trace(trace))["response"] == result["response"]
    tags = trace.info.tags
    assert tags["flow"] == "rag"
    assert (
        tags["chat_model"] == "eriktonon/deepseek-v4.1-flash-1017:latest"
        and tags["judge_model"] == "eriktonon/deepseek-v4.1-flash-1017:latest"
    )


def test_rag_llm_span_has_model_role_and_options(documents):  # 011 AC-10 / 010
    from rag_cognus.llm import ollama_options

    pipeline(documents, structured()).predict("storytelling")
    span = next(s for s in last_trace().data.spans if s.name == "generate_grounded_answer")
    assert span.get_attribute("model") == "eriktonon/deepseek-v4.1-flash-1017:latest"
    assert span.get_attribute("role") == "generator"
    expected = ollama_options(Settings(), "generator", num_predict=1800)  # spec 032 AC-7
    assert span.get_attribute("options") == expected


def test_failed_rag_marks_trace_as_error(documents):  # 011 AC-12 (pipeline real)
    p = pipeline(documents, {"answer": "Texto", "answerable": True, "cited_chunk_ids": ["x"]})
    with pytest.raises(ValueError):
        p.predict("storytelling")
    trace = last_trace()
    assert trace.info.state.value == "ERROR"
    assert trace.info.tags["error"] == "true"


def test_truncated_answer_is_a_clear_error(documents):  # spec 032 AC-8
    cut = {"resumo": "Organize em três partes.", "fontes": [{"chunk_id": "a", "trecho": "x"}]}
    with pytest.raises(ValueError, match="veio incompleta"):
        pipeline(documents, cut).predict("storytelling")
