import io
import json
import wave
from types import SimpleNamespace as NS

import numpy as np
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from rag_cognus.api.app import Services, create_app
from rag_cognus.config import Settings
from rag_cognus.retrieval import GoldRetriever


def wav_bytes(seconds=2.0, rate=16000):
    t = np.linspace(0, seconds, int(rate * seconds), endpoint=False)
    frames = (np.sin(2 * np.pi * 220 * t) * 8000).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(frames.tobytes())
    return buffer.getvalue()


class FakeWhisper:
    """140 palavras a 140 ppm, com dois vícios."""

    def transcribe(self, audio, **kwargs):
        texts = ["Hoje"] + ["mostro"] * 137 + ["tipo", "resultados."]
        words = [
            NS(word=" " + w, start=i * 60 / 140, end=i * 60 / 140 + 0.3, probability=0.95)
            for i, w in enumerate(texts)
        ]
        return iter([NS(text=" ".join(texts), words=words)]), NS(language="pt")


def fake(payload):
    return RunnableLambda(lambda _: AIMessage(json.dumps(payload, ensure_ascii=False)))


def boom(_):
    raise RuntimeError("Ollama fora do ar")


ADAPTED = {
    "adapted_text": "Hoje mostro resultados.",
    "changes": ["Corte de repetições"],
    "rehearsal_tips": ["Respire antes do número principal"],
}


class FakeServices(Services):
    def __init__(self, tmp_path, documents=None, chat_fails=False):
        super().__init__(Settings(), data_dir=tmp_path, snapshot=tmp_path / "gold.jsonl")
        self._docs = documents
        self._chat_fails = chat_fails

    def retriever(self):
        if self._docs is None:
            return super().retriever()  # sem snapshot: 503
        return GoldRetriever(self._docs, self.settings)

    def transcriber(self):
        return FakeWhisper()

    def chat(self, payload):
        return RunnableLambda(boom) if self._chat_fails else fake(payload)

    def rag_chat(self):
        return self.chat(
            {"answer": "Use storytelling.", "answerable": True, "cited_chunk_ids": ["a"]}
        )

    def communication_chat(self):
        return self.chat(ADAPTED)

    def synthesis_chat(self):
        return self.chat(
            {
                "summary": "Histórias ajudam.",
                "claims": [
                    {"text": "Storytelling dá clareza.", "chunk_ids": ["a"], "strength": "forte"}
                ],
                "conflicts": [],
                "gaps": [],
                "confidence": "alta",
            }
        )

    def fast_chat(self):
        return self.chat({"items": ["storytelling"]})


@pytest.fixture
def client(tmp_path, documents):
    return TestClient(create_app(FakeServices(tmp_path, documents)))


def post_session(client, **form):
    files = {"audio": ("fala.wav", wav_bytes(), "audio/wav")}
    data = {"mode": "daily_pitch", **form}
    return client.post("/v1/sessions", files=files, data=data)


def test_meta_and_profile(client):  # AC-10
    meta = client.get("/v1/meta").json()
    assert {m["id"] for m in meta["modes"]} >= {
        "daily_pitch",
        "reuniao_1_1",
        "apresentacao_tecnica",
    }
    assert "executivo" in {a["id"] for a in meta["audiences"]}
    assert client.get("/v1/profile").json() == {"name": "Você", "daily_goal_minutes": 10}
    updated = client.put("/v1/profile", json={"name": "Lucas", "daily_goal_minutes": 15}).json()
    assert updated["name"] == "Lucas"
    assert client.get("/v1/profile").json()["daily_goal_minutes"] == 15


def test_session_is_analyzed_saved_and_listed(client):  # AC-8
    created = post_session(client, anxiety_before="4", anxiety_after="2")
    assert created.status_code == 201, created.text
    result = created.json()
    assert result["pillars"]["pace"]["label"] == "ideal"
    assert result["pillars"]["fillers"]["counts"] == {"tipo": 1}
    assert result["index"] == round(sum(p["score"] for p in result["pillars"].values()) / 4)
    assert result["transcript"][138] == {
        "word": "tipo",
        "start": pytest.approx(138 * 60 / 140),
        "end": pytest.approx(138 * 60 / 140 + 0.3),
        "filler": True,
    }
    assert result["adapted"]["adapted_text"] == "Hoje mostro resultados."
    kinds = {r["kind"] for r in result["recommendations"]}
    assert {"strength", "next_step"} <= kinds
    assert len(result["flow"]["contour"]) == 40
    again = client.get(f"/v1/sessions/{result['session_id']}").json()
    assert again == result
    listed = client.get("/v1/sessions").json()
    assert [s["session_id"] for s in listed] == [result["session_id"]]
    audio = client.get(f"/v1/sessions/{result['session_id']}/audio")
    assert audio.headers["content-type"] == "audio/wav" and audio.content[:4] == b"RIFF"


def test_session_survives_llm_failure(tmp_path, documents):  # AC-8
    client = TestClient(create_app(FakeServices(tmp_path, documents, chat_fails=True)))
    result = post_session(client).json()
    assert result["adapted"] is None and result["index"] > 0


def test_session_rejects_bad_audio_and_mode(client):
    bad = client.post(
        "/v1/sessions",
        files={"audio": ("x.wav", b"nada", "audio/wav")},
        data={"mode": "daily_pitch"},
    )
    assert bad.status_code == 422 and "Áudio inválido" in bad.json()["detail"]
    assert post_session(client, mode="inexistente").status_code == 422
    assert client.get("/v1/sessions/nao-existe").status_code == 404


def test_home_progress_challenges_and_habits(client):  # AC-6, AC-7, AC-10
    home = client.get("/v1/home").json()
    assert home["streak_days"] == 0 and home["latest"] is None
    assert len(home["challenges"]) >= 2
    challenge = home["challenges"][0]["id"]
    result = post_session(client, challenge_id=challenge).json()
    home = client.get("/v1/home").json()
    assert home["streak_days"] == 1
    assert home["latest"]["index"] == result["index"]
    assert next(c for c in home["challenges"] if c["id"] == challenge)["done"]
    progress = client.get("/v1/progress", params={"period": "week"}).json()
    assert len(progress["bars"]) == 7 and progress["index"] == result["index"]
    assert client.get("/v1/progress", params={"period": "ano"}).status_code == 422
    habit = client.post(
        "/v1/habits",
        json={"text": "Pausa de 1 s entre tópicos", "session_id": result["session_id"]},
    )
    assert habit.status_code == 201
    assert [h["text"] for h in client.get("/v1/habits").json()] == ["Pausa de 1 s entre tópicos"]


def test_ask_requires_gold(tmp_path):  # AC-9
    client = TestClient(create_app(FakeServices(tmp_path)))
    response = client.post("/v1/ask", json={"query": "storytelling"})
    assert response.status_code == 503 and "sync-gold" in response.json()["detail"]


def test_ask_and_agents(client):
    answer = client.post("/v1/ask", json={"query": "storytelling"}).json()
    assert answer["response"] == "Use storytelling." and answer["citations"][0]["chunk_id"] == "a"
    evidence = client.post("/v1/agents/evidence", json={"topic": "Como usar storytelling?"})
    assert evidence.json()["synthesis"]["claims"][0]["chunk_ids"] == ["a"]
    adapted = client.post(
        "/v1/agents/communication",
        json={"text": "Texto longo.", "profile": {"audience": "executivo", "context": "pitch"}},
    )
    assert adapted.json()["adapted"]["adapted_text"] == "Hoje mostro resultados."
    pipeline = client.post(
        "/v1/agents/pipeline",
        json={"topic": "Como usar storytelling?", "profile": {"audience": "estudante"}},
    )
    assert pipeline.json()["communication"]["source_claims"] == ["Storytelling dá clareza."]


def test_transcribe_and_feedback(client):  # AC-10
    text = client.post(
        "/v1/speech/transcribe", files={"audio": ("q.wav", wav_bytes(), "audio/wav")}
    ).json()["text"]
    assert text.startswith("Hoje mostro")
    trace_id = client.post("/v1/ask", json={"query": "storytelling"}).json()["trace_id"]
    sent = client.post(
        "/v1/feedback", json={"trace_id": trace_id, "value": True, "comment": "útil"}
    )
    assert sent.status_code == 204


def test_cors_allows_local_front(client):
    response = client.options(
        "/v1/meta",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_session_adaptation_never_pads_short_speech(tmp_path, documents):  # AC-8
    prompts = []

    class Capturing(FakeServices):
        def communication_chat(self):
            return RunnableLambda(
                lambda p: (
                    prompts.append(p.to_string())
                    or AIMessage(json.dumps(ADAPTED, ensure_ascii=False))
                )
            )

    client = TestClient(create_app(Capturing(tmp_path, documents)))
    post_session(client, mode="apresentacao_tecnica")  # modo de 5 min, fala de 2 s
    assert "TEMPO-ALVO: 0.5 min" in prompts[0]
    assert "limite máximo" in prompts[0]
