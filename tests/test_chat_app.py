import json

import pytest

pytest.importorskip("streamlit")


def run_app():
    from rag_cognus.chat_app import main

    main()


@pytest.fixture
def app_env(documents, tmp_path, monkeypatch, isolated_tracking):
    from rag_cognus import chat_app
    from rag_cognus.gold import save_snapshot

    save_snapshot(documents, tmp_path / ".cache/gold.jsonl", "cognus.gold.vw_rag_conhecimento")
    monkeypatch.setattr(chat_app, "ROOT", tmp_path)
    monkeypatch.setenv("MLFLOW_TRACKING_URI", isolated_tracking)
    monkeypatch.setenv("MLFLOW_EXPERIMENT_NAME", "tests")
    return chat_app


def test_chat_retrieval_displays_evidence(app_env):
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_function(run_app, default_timeout=20).run()
    assert not app.exception
    app.toggle[0].set_value(False).run()
    app.chat_input[0].set_value("storytelling").run()
    assert not app.exception
    assert len(app.chat_message) == 2
    assert "Encontrei 1 trecho" in app.chat_message[1].markdown[0].value
    assert any("Storytelling" in text.value for text in app.text)
    assert any("citado" not in e.label and e.label.startswith("1.") for e in app.expander)
    assert [t.label for t in app.tabs] == ["💬 Conversa", "📚 Evidências", "📊 Métricas"]
    assert "1 trechos, 0 citados" in app.chat_message[1].caption[0].value
    app.chat_input[0].set_value("rouquidão").run()
    picker = next(s for s in app.selectbox if s.label == "Pergunta")
    assert picker.value == 1  # a pergunta mais recente aparece primeiro
    assert any("Rouquidão" in text.value for text in app.text)
    picker.set_value(0).run()
    assert any("Storytelling" in text.value for text in app.text)
    next(t for t in app.toggle if t.label == "Só os citados").set_value(True).run()
    assert not app.exception
    assert any("Nenhum trecho foi citado" in c.value for c in app.caption)


def test_scored_answer_shows_chips_and_session_metrics(app_env, monkeypatch):
    from langchain_core.messages import AIMessage
    from langchain_core.runnables import RunnableLambda
    from streamlit.testing.v1 import AppTest

    from rag_cognus import chain, judges

    answer = {"answer": "Use storytelling.", "answerable": True, "cited_chunk_ids": ["a"]}
    scores = {n: {"score": 4, "reason": "bom"} for n in judges.METRICS}
    monkeypatch.setattr(
        chain, "make_chat", lambda s: RunnableLambda(lambda _: AIMessage(json.dumps(answer)))
    )
    monkeypatch.setattr(
        app_env,
        "judge_for",
        lambda s: judges.make_judge(s, RunnableLambda(lambda _: AIMessage(json.dumps(scores)))),
    )
    app = AppTest.from_function(run_app, default_timeout=30).run()
    app.toggle[1].set_value(True).run()
    app.chat_input[0].set_value("storytelling").run()
    assert not app.exception
    assert "Use storytelling." in app.chat_message[1].markdown[0].value
    assert any("Acurácia <b>4</b>/5" in m.value for m in app.markdown)
    assert any(m.label == "Acurácia" and m.value == "4.0 / 5" for m in app.metric)
    import mlflow

    traces = mlflow.search_traces(locations=[mlflow.get_experiment_by_name("tests").experiment_id])
    names = {a.get("assessment_name") or a.get("name") for t in traces["assessments"] for a in t}
    assert {"accuracy", "professionalism", "context_relevance"} <= names


def test_metrics_tab_reads_judged_mlflow_runs(app_env, documents, isolated_tracking, tmp_path):
    from dataclasses import replace

    from langchain_core.messages import AIMessage
    from langchain_core.runnables import RunnableLambda
    from streamlit.testing.v1 import AppTest

    from rag_cognus.chain import RagPipeline
    from rag_cognus.config import Settings
    from rag_cognus.evaluation import evaluate
    from rag_cognus.judges import METRICS, make_judge
    from rag_cognus.retrieval import GoldRetriever

    settings = replace(Settings(), tracking_uri=isolated_tracking, experiment="tests")
    answer = {"answer": "Use storytelling.", "answerable": True, "cited_chunk_ids": ["a"]}
    chat = RunnableLambda(lambda _: AIMessage(json.dumps(answer)))
    pipeline = RagPipeline(GoldRetriever(documents, settings), settings, chat)
    cases = [{"case_id": f"c{i}", "inputs": {"query": "storytelling"}} for i in range(2)]
    for score in (3, 5):
        payload = {n: {"score": score, "reason": "ok"} for n in METRICS}
        judge = make_judge(settings, RunnableLambda(lambda _, p=payload: AIMessage(json.dumps(p))))
        evaluate(cases, pipeline.retriever, settings, pipeline, judge, output_dir=tmp_path)
    app_env.eval_runs.clear()
    app = AppTest.from_function(run_app, default_timeout=30).run()
    assert not app.exception
    accuracy = next(m for m in app.metric if m.label == "Acurácia" and m.value == "5.00")
    assert accuracy.delta == "+2.00"
    picker = next(s for s in app.selectbox if s.label == "Avaliação")
    assert picker.options[0].startswith("rag-bm25-k5")


def test_voice_question_is_transcribed_and_answered_once(app_env, monkeypatch):
    from streamlit.testing.v1 import AppTest

    from rag_cognus import speech

    calls = []
    monkeypatch.setattr(speech, "available", lambda: True)
    monkeypatch.setattr(app_env, "transcriber_for", lambda name: "modelo")
    monkeypatch.setattr(
        speech, "transcribe", lambda model, audio: calls.append(audio) or "storytelling"
    )
    app = AppTest.from_function(run_app, default_timeout=20).run()
    app.toggle[0].set_value(False).run()  # só recuperação: não precisa de Ollama
    app.audio_input[0].set_value(("pergunta.wav", b"RIFF-audio", "audio/wav")).run()
    assert not app.exception
    assert app.chat_message[0].markdown[0].value == "🎙️ storytelling"
    assert "Encontrei 1 trecho" in app.chat_message[1].markdown[0].value
    app.run()  # o mesmo áudio continua no widget; não deve responder de novo
    assert len(app.chat_message) == 2 and calls == [b"RIFF-audio"]


def test_app_works_without_whisper_installed(app_env, monkeypatch):
    from streamlit.testing.v1 import AppTest

    from rag_cognus import speech

    monkeypatch.setattr(speech, "available", lambda: False)
    app = AppTest.from_function(run_app, default_timeout=20).run()
    assert not app.exception
    assert not app.audio_input
    assert any("[audio]" in c.value for c in app.caption)
