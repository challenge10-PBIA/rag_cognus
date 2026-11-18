"""Spec 009 — mascote coach: dicas por regras, fatos e explicação com guarda de números."""

import json
from datetime import date, timedelta

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from rag_cognus import coach
from rag_cognus.config import Settings
from rag_cognus.speech_analysis import PACE_RANGE, PAUSE_RANGE

TODAY = date(2026, 11, 18)


def record(days_ago=0, index=70, minutes=5.0, **pillars):
    scores = {"pace": 80, "pauses": 70, "fillers": 90, "clarity": 75} | pillars
    return {
        "created_at": f"{TODAY - timedelta(days=days_ago)}T10:00:00",
        "duration_seconds": minutes * 60,
        "index": index,
        "challenge_id": None,
        "anxiety_before": None,
        "anxiety_after": None,
        "mode": "pitch",
        "pillars": scores,
    }


def data(records=(), goal=10, session=None, evaluation=None):
    return {
        "records": list(records),
        "today": TODAY,
        "profile": {"name": "Ana", "daily_goal_minutes": goal},
        "session": session,
        "evaluation": evaluation,
    }


SESSION = {
    "session_id": "s1",
    "index": 82,
    "headline": "Bom ritmo",
    "duration_seconds": 120,
    "diction": 93,
    "pillars": {
        "pace": {"title": "Ritmo & Cadência", "value": 138, "unit": "ppm", "score": 90},
        "pauses": {"title": "Pausas Conscientes", "value": 5, "unit": "pausas", "score": 85},
        "fillers": {"title": "Vícios Vocais", "value": 96, "unit": "% livre", "score": 80},
        "clarity": {"title": "Clareza da Mensagem", "value": "alto", "unit": "", "score": 55},
    },
}


# ---------- AC-1: glossário ----------
def test_glossary_covers_concepts_with_short_text():
    for topic in coach.CONCEPTS:
        entry = coach.GLOSSARY[topic]
        assert entry["label"] and entry["text"]
        sentences = [s for s in entry["text"].split(".") if s.strip()]
        assert len(sentences) <= 2, topic


def test_glossary_ranges_come_from_speech_constants():
    assert f"{PACE_RANGE[0]}–{PACE_RANGE[1]}" in coach.GLOSSARY["pace"]["text"]
    low = f"{PAUSE_RANGE[0]:g}".replace(".", ",")
    assert low in coach.GLOSSARY["pauses"]["text"]


# ---------- AC-2: dicas ----------
def test_home_without_sessions_invites_first_practice():
    tips = coach.tips("/", data())
    assert tips[0]["id"] == "home-first-session"
    assert tips[0]["mood"] == "feliz"


def test_home_goal_done_congratulates():
    tips = coach.tips("/", data([record(minutes=12)], goal=10))
    assert tips[0]["id"].startswith("home-goal-done")
    assert tips[0]["mood"] == "feliz"


def test_home_streak_reminder():
    tips = coach.tips("/", data([record(days_ago=2), record(days_ago=1)], goal=10))
    assert tips[0]["id"].startswith("home-streak")
    assert "2" in tips[0]["text"]


def test_tip_ids_are_stable():
    d = data([record(days_ago=1)])
    assert coach.tips("/metricas", d) == coach.tips("/metricas", d)


def test_metrics_points_weakest_pillar():
    tips = coach.tips("/metricas", data([record(clarity=40)]))
    assert tips[0]["id"] == "metrics-weakest-clarity"
    assert tips[0]["topic"] == "weakest_pillar"
    assert tips[0]["mood"] == "pensativo"


def test_metrics_without_data_explains_empty_state():
    assert coach.tips("/metricas", data())[0]["id"] == "metrics-empty"


@pytest.mark.parametrize(
    ("route", "tip_id"), [("/cognus", "cognus-how"), ("/perfil", "profile-mascot")]
)
def test_static_route_tips(route, tip_id):
    assert coach.tips(route, data())[0]["id"] == tip_id


def test_unknown_route_has_no_tips():
    assert coach.tips("/qualquer", data()) == []


def test_at_most_two_tips():
    for route in ("/", "/metricas", "/cognus", "/perfil"):
        assert len(coach.tips(route, data([record(days_ago=1), record()]))) <= 2


# ---------- AC-3: fatos ----------
def test_session_summary_facts_come_from_session():
    facts = coach.facts("session_summary", data(session=SESSION))
    values = " ".join(f["value"] for f in facts)
    assert "82" in values and "138" in values


def test_session_summary_without_session_raises():
    with pytest.raises(ValueError, match="sessão"):
        coach.facts("session_summary", data())


def test_weakest_pillar_without_sessions_raises():
    with pytest.raises(ValueError):
        coach.facts("weakest_pillar", data())


def test_ask_evaluation_requires_done_evaluation():
    with pytest.raises(ValueError):
        coach.facts("ask_evaluation", data(evaluation={"status": "pending"}))
    evaluation = {
        "status": "done",
        "metrics": {"quality_score": 4.2, "groundedness": 5, "citation_integrity": 1.0},
        "judges": [],
    }
    facts = coach.facts("ask_evaluation", data(evaluation=evaluation))
    assert any("4,2" in f["value"] or "4.2" in f["value"] for f in facts)


def test_concept_without_data_has_no_facts():
    assert coach.facts("streak", data()) == [{"label": "Sequência atual", "value": "0 dias"}]
    assert coach.facts("index", data()) == []


# ---------- AC-4: tópicos ----------
def test_topics_depend_on_available_data():
    ids = {t["id"] for t in coach.topics("/", data())}
    assert {"index", "pace"} <= ids
    assert "weakest_pillar" not in ids and "session_summary" not in ids
    ids = {t["id"] for t in coach.topics("/", data([record()], session=SESSION))}
    assert {"weakest_pillar", "session_summary"} <= ids
    done = {"status": "done", "metrics": {}, "judges": []}
    assert "ask_evaluation" in {t["id"] for t in coach.topics("/cognus", data(evaluation=done))}


# ---------- AC-5…AC-7: explicação ----------
def fake_chat(payload):
    return RunnableLambda(lambda _: AIMessage(json.dumps(payload, ensure_ascii=False)))


def boom(_):
    raise RuntimeError("Ollama fora do ar")


FACTS = [{"label": "Índice da sessão", "value": "82"}]


def test_explain_uses_llm_when_numbers_are_grounded():
    agent = coach.MascotCoach(
        Settings(), chat=fake_chat({"text": "Seu índice foi 82. Ótimo!", "mood": "feliz"})
    )
    out = agent.explain("index", FACTS)
    assert out == {"text": "Seu índice foi 82. Ótimo!", "mood": "feliz", "source": "llm"}


@pytest.mark.parametrize(
    "text",
    ["Seu índice foi 95.", "", "x" * 601],
)
def test_explain_falls_back_on_invented_number_or_bad_text(text):
    agent = coach.MascotCoach(Settings(), chat=fake_chat({"text": text, "mood": "feliz"}))
    out = agent.explain("index", FACTS)
    assert out["source"] == "regras"
    assert coach.GLOSSARY["index"]["text"] in out["text"] and "82" in out["text"]


def test_explain_accepts_number_formats_and_glossary_numbers():
    text = f"Faixa ideal: {PACE_RANGE[0]} a {PACE_RANGE[1]} ppm; você fez 138,0."
    agent = coach.MascotCoach(Settings(), chat=fake_chat({"text": text, "mood": "neutro"}))
    out = agent.explain("pace", [{"label": "Ritmo", "value": "138 ppm"}])
    assert out["source"] == "llm"


def test_explain_falls_back_when_llm_fails():
    agent = coach.MascotCoach(Settings(), chat=RunnableLambda(boom))
    out = agent.explain("pace", [])
    assert out["source"] == "regras"
    assert out["text"] == coach.GLOSSARY["pace"]["text"]


def test_rules_mood_follows_score():
    assert coach.mood_for("session_summary", data(session=SESSION)) == "feliz"
    assert coach.mood_for("weakest_pillar", data([record(clarity=40)])) == "pensativo"
    assert coach.mood_for("pace", data()) == "neutro"


# ---------- spec 013 AC-8 + specs 010/011: contrato do trace do mascote ----------


def last_trace():
    import mlflow

    mlflow.flush_trace_async_logging()
    return mlflow.get_trace(mlflow.get_last_active_trace_id())


def test_explain_trace_follows_spec_011_contract():
    from rag_cognus.llm import ollama_options

    agent = coach.MascotCoach(
        Settings(), chat=fake_chat({"text": "Seu índice foi 82. Ótimo!", "mood": "feliz"})
    )
    out = agent.explain("index", FACTS)
    trace = last_trace()
    root = next(s for s in trace.data.spans if s.parent_id is None)
    assert root.name == "mascot_agent" and root.span_type == "AGENT"
    assert root.inputs == {"topic": "index", "facts": FACTS}
    assert root.outputs == {"response": out["text"], "mood": "feliz", "source": "llm"}
    tags = trace.info.tags
    assert tags["flow"] == "mascot" and tags["agent"] == "mascot" and tags["topic"] == "index"
    assert {"chat_model", "judge_model"} <= set(tags)
    llm = next(s for s in trace.data.spans if s.name == "mascot_explain")
    assert llm.span_type == "LLM"
    assert llm.get_attribute("role") == "fast"
    expected = ollama_options(Settings(), "fast", num_predict=coach.EXPLAIN_NUM_PREDICT)
    assert llm.get_attribute("options") == expected


def test_explain_trace_marks_rules_fallback():
    coach.MascotCoach(Settings(), chat=RunnableLambda(boom)).explain("pace", [])
    trace = last_trace()
    root = next(s for s in trace.data.spans if s.parent_id is None)
    assert root.outputs["source"] == "regras"
    assert trace.info.tags["mascot_source"] == "regras"
