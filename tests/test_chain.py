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
