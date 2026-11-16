import json

import mlflow
import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from rag_cognus.agents.agents_judges import (
    as_scores,
    judge_communication,
    judge_evidence,
    make_communication_judge,
    make_evidence_judge,
)
from rag_cognus.agents.communication import CommunicationAgent, text_metrics
from rag_cognus.agents.evidence import EvidenceAgent, needs_split
from rag_cognus.agents.pipeline import EvidenceToAudience, synthesis_to_text
from rag_cognus.agents.schemas import AudienceProfile
from rag_cognus.config import Settings
from rag_cognus.retrieval import GoldRetriever

COMPOSITE = "Como usar storytelling numa apresentação e cuidar da rouquidão, sem perder a escuta?"


def fake(payload, calls=None):
    def answer(prompt):
        if calls is not None:
            calls.append(prompt)
        return AIMessage(content=json.dumps(payload, ensure_ascii=False))

    return RunnableLambda(answer)


def boom(_):
    raise AssertionError("Não deveria chamar o modelo")


DRAFT = {
    "summary": "Storytelling ajuda a clareza; cuide da voz.",
    "claims": [
        {
            "text": "Storytelling torna a apresentação clara.",
            "chunk_ids": ["a"],
            "strength": "forte",
        },
        {"text": "Afirmação inventada.", "chunk_ids": ["zzz"], "strength": "fraca"},
        {"text": "Rouquidão pede cuidado.", "chunk_ids": ["b", "zzz"], "strength": "moderada"},
    ],
    "conflicts": [],
    "gaps": [],
    "confidence": "media",
}
ADAPTED = {
    "adapted_text": "Conte uma história. Depois mostre o dado. Feche com um pedido claro.",
    "changes": ["Frases mais curtas"],
    "rehearsal_tips": ["Ensaie em voz alta duas vezes"],
}


def evidence_agent(documents, chat=None, fast_chat=None, **kwargs):
    retriever = GoldRetriever(documents, Settings())
    return EvidenceAgent(
        retriever, Settings(), chat or fake(DRAFT), fast_chat or RunnableLambda(boom), **kwargs
    )


# ---------- decomposição ----------


def test_simple_topic_skips_decomposition(documents):  # AC-2
    assert not needs_split("Como usar storytelling?")
    assert evidence_agent(documents).decompose("Como usar storytelling?") == [
        "Como usar storytelling?"
    ]


def test_composite_topic_is_split_deduplicated_and_capped(documents):  # AC-3
    items = ["Storytelling", "storytelling ", "Rouquidão", "Escuta ativa", "Voz", "Postura"]
    agent = evidence_agent(documents, fast_chat=fake({"items": items}))
    assert needs_split(COMPOSITE)
    assert agent.decompose(COMPOSITE) == ["Storytelling", "Rouquidão", "Escuta ativa", "Voz"]


@pytest.mark.parametrize("payload", [{"items": []}, {"outra": 1}, "texto solto"])
def test_invalid_decomposition_falls_back_to_topic(documents, payload):  # AC-3
    agent = evidence_agent(documents, fast_chat=fake(payload))
    assert agent.decompose(COMPOSITE) == [COMPOSITE]


# ---------- busca ----------


def test_gather_deduplicates_and_respects_limit(documents):  # AC-4
    agent = evidence_agent(documents, max_chunks=2)
    hits = agent.gather(["storytelling apresentação", "apresentação clara", "rouquidão", "escuta"])
    ids = [h["chunk_id"] for h in hits]
    assert ids == ["a", "b"]
    assert hits[0]["subquestion"] == "storytelling apresentação"
    assert hits[0]["source_url"] == "https://example.org/a"


# ---------- síntese ----------


def test_no_evidence_returns_low_confidence_without_llm(documents):  # AC-5
    agent = evidence_agent(documents, chat=RunnableLambda(boom))
    result = agent.run("zzzzdesconhecido")
    synthesis = result["synthesis"]
    assert synthesis["claims"] == [] and synthesis["confidence"] == "baixa"
    assert synthesis["gaps"] == ["zzzzdesconhecido"]


def test_fabricated_citations_are_removed(documents):  # AC-6
    result = evidence_agent(documents, fast_chat=fake({"items": ["storytelling", "rouquidão"]}))
    result = result.run(COMPOSITE)
    claims = result["synthesis"]["claims"]
    assert [c["chunk_ids"] for c in claims] == [["a"], ["b"]]
    assert result["discarded_claims"] == 1
    assert result["subquestions"] == ["storytelling", "rouquidão"]


def test_subquestion_without_evidence_is_a_gap(documents):  # AC-7
    agent = evidence_agent(documents, fast_chat=fake({"items": ["storytelling", "xyzinexistente"]}))
    assert "xyzinexistente" in agent.run(COMPOSITE)["synthesis"]["gaps"]


# ---------- comunicação ----------


def test_text_metrics_are_deterministic():  # AC-8
    text = " ".join(["palavra"] * 150) + ". Outra frase curta aqui."
    m = text_metrics(text, target_minutes=2)
    assert (m["words"], m["sentences"]) == (154, 2)
    assert m["avg_sentence_words"] == 77.0
    assert m["estimated_minutes"] == pytest.approx(154 / 150, abs=0.01)
    assert m["time_deviation_minutes"] == pytest.approx(154 / 150 - 2, abs=0.01)
    assert 0 <= m["readability"] <= 100
    short = text_metrics("Fale devagar. Olhe o público.")
    assert short["readability"] > m["readability"]
    assert short["time_deviation_minutes"] is None


@pytest.mark.parametrize(
    "word,expected",
    [("fala", 2), ("comunicação", 5), ("saúde", 3), ("país", 2), ("poeta", 3), ("voo", 2)],
)
def test_syllable_count(word, expected):  # AC-8 (legibilidade)
    from rag_cognus.agents.communication import _syllables

    assert _syllables(word) == expected


def test_communication_rejects_empty_text():  # AC-8
    agent = CommunicationAgent(Settings(), RunnableLambda(boom))
    with pytest.raises(ValueError, match="vazio"):
        agent.run("   ", AudienceProfile())


def test_communication_adapts_and_measures():  # AC-8
    calls = []
    agent = CommunicationAgent(Settings(), fake(ADAPTED, calls))
    profile = AudienceProfile(audience="executivo", context="pitch", minutes=1)
    result = agent.run("Texto original longo sobre apresentação.", profile)
    assert result["adapted"]["adapted_text"] == ADAPTED["adapted_text"]
    assert result["metrics"]["words"] == 12
    assert result["metrics"]["target_minutes"] == 1
    assert "executivo" in calls[0].to_string().lower()


# ---------- pipeline ----------


def test_pipeline_hands_claims_to_communication(documents):  # AC-9
    calls = []
    pipe = EvidenceToAudience(
        evidence_agent(documents), CommunicationAgent(Settings(), fake(ADAPTED, calls))
    )
    result = pipe.run("Como usar storytelling?", AudienceProfile())
    sent = calls[0].to_string()
    assert "Storytelling torna a apresentação clara." in sent
    # só o trecho "a" é recuperado: a afirmação que cita "b" não chega ao agente de comunicação
    assert result["communication"]["source_claims"] == ["Storytelling torna a apresentação clara."]
    assert "Rouquidão" not in sent
    assert synthesis_to_text(result["evidence"]).startswith("Storytelling ajuda")


# ---------- juízes ----------


def score(n):
    return {"score": n, "reason": "ok"}


def test_agent_judges_scores(documents):  # AC-10
    evidence = evidence_agent(documents).run("Como usar storytelling?")
    judge = make_evidence_judge(
        Settings(),
        fake({"coverage": score(5), "groundedness": score(4), "conflict_handling": score(3)}),
    )
    assert as_scores(judge_evidence(judge, evidence)) == {
        "coverage": 5,
        "groundedness": 4,
        "conflict_handling": 3,
        "evidence_score": 4.0,
    }
    adapted = CommunicationAgent(Settings(), fake(ADAPTED)).run("Texto.", AudienceProfile())
    judge = make_communication_judge(
        Settings(), fake({"audience_fit": score(5), "fidelity": score(5), "clarity": score(2)})
    )
    assert as_scores(judge_communication(judge, adapted))["communication_score"] == 4.0


# ---------- MLflow ----------


def test_agent_run_is_traced_as_agent(documents):  # AC-11
    evidence_agent(documents).run("Como usar storytelling?")
    trace_id = mlflow.get_last_active_trace_id()
    mlflow.flush_trace_async_logging()
    trace = mlflow.get_trace(trace_id)
    root = next(s for s in trace.data.spans if s.parent_id is None)
    assert root.span_type == "AGENT"
    assert trace.info.tags["agent"] == "evidence"
