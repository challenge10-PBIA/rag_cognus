import pytest

pytest.importorskip("streamlit")


def run_app():
    from rag_cognus.chat_app import main

    main()


def test_chat_retrieval_displays_evidence(documents, tmp_path, monkeypatch, isolated_tracking):
    from streamlit.testing.v1 import AppTest

    from rag_cognus import chat_app
    from rag_cognus.gold import save_snapshot

    save_snapshot(documents, tmp_path / ".cache/gold.jsonl", "cognus.gold.vw_rag_conhecimento")
    monkeypatch.setattr(chat_app, "ROOT", tmp_path)
    monkeypatch.setenv("MLFLOW_TRACKING_URI", isolated_tracking)
    monkeypatch.setenv("MLFLOW_EXPERIMENT_NAME", "tests")
    app = AppTest.from_function(run_app, default_timeout=20).run()
    assert not app.exception
    app.toggle[0].set_value(False).run()
    app.chat_input[0].set_value("storytelling").run()
    assert not app.exception
    assert len(app.chat_message) == 2
    assert "Encontrei 1 trecho" in app.chat_message[1].markdown[0].value
    assert any("Storytelling" in text.value for text in app.text)
    assert any("citado" not in e.label and e.label.startswith("1.") for e in app.expander)
