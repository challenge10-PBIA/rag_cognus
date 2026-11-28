"""Spec 037: conversa casual responde sem a base de conhecimento."""

import json

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from rag_cognus import small_talk
from rag_cognus.chain import RagPipeline
from rag_cognus.config import Settings


def fake(payload):
    return RunnableLambda(lambda _: AIMessage(json.dumps(payload, ensure_ascii=False)))


def boom(_):
    raise RuntimeError("Ollama fora do ar")


class NoRetriever:
    def retrieve(self, *args, **kwargs):
        raise AssertionError("conversa casual não deve buscar na base")


@pytest.mark.parametrize(
    "text",
    [
        "opa eae fera",
        "Opa, eaí fera!",
        "tá me ouvindo?",
        "ta me ouvindo",
        "você consegue me ouvir?",
        "alô, testando",
        "bom dia!",
        "boa noite, tudo bem?",
        "oi",
        "olá Cognus",
        "valeu mano",
        "obrigado!",
        "tchau, até mais",
        "valeu mano, até amanhã",
        "quem é você?",
        "beleza, show",
        "kkkk",
    ],
)
def test_recognizes_small_talk(text):  # AC-1
    assert small_talk.is_small_talk(text)


@pytest.mark.parametrize(
    "text",
    [
        "como melhorar minha voz?",
        "bom dia, como parar de falar né?",
        "o que é dicção?",
        "tô nervoso para apresentar amanhã",
        "me ajuda com oratória",
        "voz",
        "",
        "   ",
        "oi " * 20,
    ],
)
def test_content_requests_go_to_rag(text):  # AC-1
    assert not small_talk.is_small_talk(text)


def test_small_talk_skips_retrieval_and_rag_llm():  # AC-2/AC-3
    rag_llm = RunnableLambda(boom)  # se o RAG rodar, explode
    pipeline = RagPipeline(
        NoRetriever(),
        Settings(),
        chat=rag_llm,
        small_talk_chat=fake({"reply": "E aí! Tudo certo?"}),
    )
    result = pipeline.predict("opa eae fera")
    assert result["kind"] == "conversa" and result["response"] == "E aí! Tudo certo?"
    assert result["abstained"] is False
    assert result["cited_chunk_ids"] == [] and result["citations"] == []
    assert result["retrieved_chunk_ids"] == [] and result["retrieved_context"] == []
    assert result["structured"] == {
        "resumo": "E aí! Tudo certo?",
        "pontos": [],
        "recomendacao": None,
        "fontes": [],
    }


def test_small_talk_falls_back_when_model_fails():  # AC-3
    pipeline = RagPipeline(
        NoRetriever(), Settings(), chat=RunnableLambda(boom), small_talk_chat=RunnableLambda(boom)
    )
    result = pipeline.predict("tá me ouvindo?")
    assert result["kind"] == "conversa" and result["response"] == small_talk.FALLBACK


def test_small_talk_prompt_is_friendly_and_short():  # AC-3
    seen = {}

    def capture(prompt):
        seen["text"] = prompt.to_string()
        return AIMessage(json.dumps({"reply": "Oi!"}))

    small_talk.reply(Settings(), RunnableLambda(capture), "opa eae fera")
    assert "amigável" in seen["text"] and "opa eae fera" in seen["text"]
    assert "não cite" in seen["text"].lower()


def test_trace_flow_is_conversa(monkeypatch):  # AC-5
    tags = []
    monkeypatch.setattr(
        "rag_cognus.chain.mlflow.update_current_trace", lambda **kw: tags.append(kw)
    )
    RagPipeline(
        NoRetriever(), Settings(), chat=RunnableLambda(boom), small_talk_chat=fake({"reply": "Oi!"})
    ).predict("oi")
    merged = {k: v for call in tags for k, v in (call.get("tags") or {}).items()}
    assert merged["flow"] == "conversa"
