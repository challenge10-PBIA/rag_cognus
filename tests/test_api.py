import io
import json
import sqlite3
import threading
import time
import wave
from dataclasses import replace
from types import SimpleNamespace as NS

import mlflow
import numpy as np
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from rag_cognus.api import app as api_app
from rag_cognus.api.app import Services, _next_step, _pillar_detail, create_app
from rag_cognus.chain import ABSTENTION
from rag_cognus.config import Settings
from rag_cognus.judges import METRICS
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


MASCOT_TEXT = {"text": "Ritmo é a velocidade da sua fala.", "mood": "neutro"}

SCORES = dict(zip(METRICS, (5, 4, 5, 3, 4), strict=True))
JUDGMENT = {k: {"score": v, "reason": f"motivo {k}"} for k, v in SCORES.items()}


def exercise(eid, pillars):
    return {
        "id": eid,
        "titulo": f"Exercício {eid}",
        "categoria": "respiracao",
        "pilares": pillars,
        "passos": ["Inspire.", "Fale."],
        "duracao_min": 3,
        "nivel": "iniciante",
        "fonte": {
            "titulo": "Fonte",
            "autor": "Autora",
            "ano": 2020,
            "url": "https://example.org/fonte",
            "tipo": "livro",
        },
        "verificado_em": "2026-11-16",
    }


CATALOG = [
    exercise("pausa-respirada", ["pace", "pauses"]),
    exercise("silencio-no-lugar", ["fillers"]),
    exercise("frase-curta", ["clarity", "diction"]),
]


class SyncRunner:
    """Executa a avaliação na hora: o teste vê `done` logo após o POST (AC-2)."""

    def submit(self, fn, *args, **kwargs):
        fn(*args, **kwargs)


class FakeServices(Services):
    def __init__(self, tmp_path, documents=None, chat_fails=False, settings=None, **fakes):
        super().__init__(
            settings or Settings(), data_dir=tmp_path, snapshot=tmp_path / "gold.jsonl"
        )
        self._docs = documents
        self._chat_fails = chat_fails
        self.logged = []
        self.fakes = fakes

    def judge_chat(self):
        return self.fakes.get("judge") or fake(JUDGMENT)

    def evaluation_runner(self):
        return self.fakes.get("runner") or SyncRunner()

    def evaluation_logger(self):
        return self.fakes.get("logger") or self.logged.append

    def pleonasm_chat(self):
        return self.fakes.get("pleonasm") or RunnableLambda(boom)

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

    def mascot_chat(self):
        return self.fakes.get("mascot") or self.chat(MASCOT_TEXT)

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

    def exercise_catalog(self):
        if self.fakes.get("catalog_fails"):
            raise ValueError("catálogo inválido")
        return CATALOG

    def exercises_for(self, pillar, limit=2):
        return [e for e in self.exercise_catalog() if pillar in e["pilares"]][:limit]


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
    assert client.get("/v1/profile").json() == {
        "name": "Você",
        "daily_goal_minutes": 10,
        "mascot": DEFAULT_MASCOT,
    }
    updated = client.put("/v1/profile", json={"name": "Lucas", "daily_goal_minutes": 15}).json()
    assert updated["name"] == "Lucas"
    assert client.get("/v1/profile").json()["daily_goal_minutes"] == 15


def test_api_cors_allows_local_frontend_on_8001():
    app = create_app(Services(Settings()))
    origins = next(
        middleware.kwargs["allow_origins"]
        for middleware in app.user_middleware
        if middleware.cls.__name__ == "CORSMiddleware"
    )
    assert "http://127.0.0.1:8001" in origins
    assert "http://localhost:8001" in origins


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
        "kind": "vicio_fixo",
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


def test_session_exposes_occurrences_and_old_sessions_still_load(client, tmp_path):  # AC-15
    result = post_session(client).json()
    [occurrence] = result["occurrences"]
    assert occurrence["term"] == "tipo" and occurrence["kind"] == "vicio_fixo"
    assert occurrence["excerpt"].endswith("tipo resultados.")
    assert result["pillars"]["fillers"]["pleonasms"] == 0
    assert result["transcript"][0]["kind"] is None and not result["transcript"][0]["filler"]
    db = next(tmp_path.glob("*.db"))
    with sqlite3.connect(db) as conn:
        old = json.loads(conn.execute("SELECT result_json FROM sessions").fetchone()[0])
        old.pop("occurrences")
        old["pillars"]["fillers"].pop("pleonasms")
        for w in old["transcript"]:
            w.pop("kind")
        conn.execute("UPDATE sessions SET result_json = ?", (json.dumps(old),))
    loaded = client.get(f"/v1/sessions/{result['session_id']}")
    assert loaded.status_code == 200, loaded.text
    assert loaded.json()["occurrences"] is None
    assert loaded.json()["transcript"][138]["kind"] is None


def test_fillers_texts_cite_detected_term_or_pleonasm():  # AC-16
    detected = {"counts": {"tipo": 1, "então": 6}, "pleonasms": 0}
    assert _pillar_detail("fillers", detected) == "Mais usado: “então” (6×)"
    assert "“então” 6×" in _next_step("fillers", detected)
    occurrences = [
        {"kind": "pleonasmo", "term": "subir pra cima", "suggestion": "subir"},
        {"kind": "pleonasmo", "term": "elo de ligação", "suggestion": "elo"},
    ]
    only_pleonasms = {"counts": {}, "pleonasms": 2}
    assert _next_step("fillers", only_pleonasms, occurrences) == (
        "Troque “subir pra cima” por “subir”."
    )
    assert "pleonasmo" in _pillar_detail("fillers", only_pleonasms)


def test_ask_returns_before_judge_runs(tmp_path, documents):  # AC-1, AC-2
    release, judged = threading.Event(), []

    def slow_judge(_):
        release.wait(5)
        judged.append(True)
        return AIMessage(json.dumps(JUDGMENT))

    class Threaded(FakeServices):
        def evaluation_runner(self):  # executor padrão, com um worker
            return Services.evaluation_runner(self)

    services = Threaded(tmp_path, documents, judge=RunnableLambda(slow_judge))
    client = TestClient(create_app(services))
    response = client.post("/v1/ask", json={"query": "storytelling"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["evaluation_status"] == "pending" and not judged
    assert set(body) == {
        "response",
        "abstained",
        "cited_chunk_ids",
        "citations",
        "trace_id",
        "ask_id",
        "evaluation_status",
        "structured",
    }
    url = f"/v1/ask/{body['ask_id']}/evaluation"
    assert client.get(url).json()["status"] == "pending"
    release.set()
    for _ in range(100):
        if client.get(url).json()["status"] != "pending":
            break
        time.sleep(0.05)
    assert client.get(url).json()["status"] == "done"
    assert services.evaluation_runner() is services.evaluation_runner()
    assert services.evaluation_runner()._max_workers == 1


def test_ask_openapi_declares_ask_out(client):  # AC-1
    spec = client.get("/openapi.json").json()
    ok = spec["paths"]["/v1/ask"]["post"]["responses"]["200"]["content"]["application/json"]
    assert ok["schema"]["$ref"].endswith("/AskOut")
    get = spec["paths"]["/v1/ask/{ask_id}/evaluation"]["get"]["responses"]["200"]
    assert get["content"]["application/json"]["schema"]["$ref"].endswith("/AskEvaluation")


def test_evaluation_done_with_metrics_and_judges(client):  # AC-2, AC-3, AC-7, AC-8
    body = client.post(
        "/v1/ask", json={"query": "storytelling", "niche": "apresentacoes_oratoria"}
    ).json()
    assert body["structured"]["fontes"][0]["titulo"] == "a"
    evaluation = client.get(f"/v1/ask/{body['ask_id']}/evaluation").json()
    assert evaluation["status"] == "done" and evaluation["error"] is None
    assert [j["name"] for j in evaluation["judges"]] == list(METRICS)
    assert evaluation["judges"][1] == {
        "name": "groundedness",
        "label": "Fidelidade às fontes",
        "score": 4,
        "reason": "motivo groundedness",
    }
    metrics = evaluation["metrics"]
    assert metrics["quality_score"] == pytest.approx(21 / 5)
    assert metrics["citation_integrity"] == 1
    assert metrics["niche_metadata_precision_proxy"] == 1
    assert metrics["latency_seconds"] >= 0
    assert evaluation["mlflow_logged"] is True
    assert evaluation["judge_model"] == Settings().judge
    assert evaluation["created_at"] and evaluation["finished_at"]
    [payload] = client.app.state.services.logged
    assert payload["run_name"] == f"ask-{body['ask_id']}"
    assert payload["experiment"] == "rag-cognus-online"
    assert payload["tags"] == {
        "rag_cognus_online": "true",
        "ask_id": body["ask_id"],
        "abstained": "false",
    }
    assert set(payload["params"]) == {
        "chat_model",
        "judge_model",
        "backend",
        "top_k",
        "niche",
        "gold_view",
    }
    assert payload["trace_id"] == body["trace_id"]
    assert client.get("/v1/ask/nao-existe/evaluation").status_code == 404
    assert client.get("/v1/ask/nao-existe/evaluation").json()["detail"] == (
        "Avaliação não encontrada."
    )


def test_evaluation_persists_and_interrupted_becomes_error(tmp_path, documents):  # AC-4
    client = TestClient(create_app(FakeServices(tmp_path, documents)))
    done = client.post("/v1/ask", json={"query": "storytelling"}).json()["ask_id"]
    services = FakeServices(tmp_path, documents)
    services.store.create_evaluation("morto", "2026-01-01T00:00:00", "pending", "qwen")
    restarted = TestClient(create_app(FakeServices(tmp_path, documents)))
    assert restarted.get(f"/v1/ask/{done}/evaluation").json()["status"] == "done"
    dead = restarted.get("/v1/ask/morto/evaluation").json()
    assert dead["status"] == "error" and dead["error"] == "Avaliação interrompida."


@pytest.mark.parametrize(
    "judge",
    [
        RunnableLambda(boom),
        fake({"accuracy": {"score": 9, "reason": "x"}}),
        RunnableLambda(lambda _: AIMessage("isto não é json")),
    ],
)
def test_judge_failure_marks_error_in_portuguese(tmp_path, documents, judge):  # AC-5
    services = FakeServices(tmp_path, documents, judge=judge)
    client = TestClient(create_app(services))
    response = client.post("/v1/ask", json={"query": "storytelling"})
    assert response.status_code == 200
    evaluation = client.get(f"/v1/ask/{response.json()['ask_id']}/evaluation").json()
    assert evaluation["status"] == "error" and evaluation["metrics"] is None
    assert "Traceback" not in evaluation["error"] and "juiz" in evaluation["error"].lower()
    assert services.logged == []


def test_abstention_is_evaluated(tmp_path, documents):  # AC-6
    class Abstains(FakeServices):
        def rag_chat(self):
            return fake({"resumo": "x", "answerable": False, "cited_chunk_ids": []})

    client = TestClient(create_app(Abstains(tmp_path, documents)))
    body = client.post("/v1/ask", json={"query": "storytelling"}).json()
    assert body["response"] == ABSTENTION and body["structured"]["fontes"] == []
    evaluation = client.get(f"/v1/ask/{body['ask_id']}/evaluation").json()
    assert evaluation["status"] == "done"
    assert evaluation["metrics"]["citation_integrity"] == 1
    assert evaluation["metrics"]["niche_metadata_precision_proxy"] is None


def test_logger_failure_keeps_scores(tmp_path, documents):  # AC-8
    def down(payload):
        raise ConnectionError("MLflow fora do ar")

    client = TestClient(create_app(FakeServices(tmp_path, documents, logger=down)))
    ask_id = client.post("/v1/ask", json={"query": "storytelling"}).json()["ask_id"]
    evaluation = client.get(f"/v1/ask/{ask_id}/evaluation").json()
    assert evaluation["status"] == "done" and evaluation["mlflow_logged"] is False
    assert evaluation["metrics"]["accuracy"] == 3


def test_default_logger_skips_when_mlflow_is_down(tmp_path, monkeypatch):  # AC-8, AC-D5
    from rag_cognus import cli, evaluation

    calls = []
    monkeypatch.setattr(cli, "mlflow_available", lambda uri, **kw: False)
    monkeypatch.setattr(evaluation, "log_online_evaluation", lambda *a: calls.append(a))
    logger = Services(Settings(), data_dir=tmp_path).evaluation_logger()
    with pytest.raises(RuntimeError, match="MLflow"):
        logger({"run_name": "ask-x"})
    assert calls == []
    monkeypatch.setattr(cli, "mlflow_available", lambda uri, **kw: True)
    logger({"run_name": "ask-x"})
    assert len(calls) == 1


def test_online_eval_disabled(tmp_path, documents):  # AC-14
    def never(*_):
        raise AssertionError("não deveria avaliar nem logar")

    services = FakeServices(
        tmp_path,
        documents,
        settings=replace(Settings(), online_eval=False),
        judge=RunnableLambda(never),
        logger=never,
    )
    client = TestClient(create_app(services))
    body = client.post("/v1/ask", json={"query": "storytelling"}).json()
    assert body["evaluation_status"] == "disabled"
    evaluation = client.get(f"/v1/ask/{body['ask_id']}/evaluation").json()
    assert evaluation["status"] == "disabled" and evaluation["metrics"] is None


class FakeResponse:
    def __init__(self, ok):
        self.is_success = ok


@pytest.mark.parametrize(
    "uri, mlflow_up, expected",
    [
        ("http://127.0.0.1:5001", True, True),
        ("http://127.0.0.1:5001", False, False),
        ("http://127.0.0.1:5001", None, False),
        ("sqlite:///tmp/mlflow.db", True, None),
        ("file:///tmp/mlruns", True, None),
    ],
)
def test_health_reports_mlflow(tmp_path, monkeypatch, uri, mlflow_up, expected):  # AC-D3
    import httpx

    seen = []

    def get(url, timeout):
        seen.append((url, timeout))
        if "/health" in url and mlflow_up is None:
            raise httpx.ConnectError("recusado")
        return FakeResponse(mlflow_up if "/health" in url else True)

    monkeypatch.setattr(api_app.httpx, "get", get)
    services = FakeServices(tmp_path, settings=replace(Settings(), tracking_uri=uri))
    health = TestClient(create_app(services)).get("/v1/health").json()
    assert health["mlflow"] is expected and health["ollama"] is True
    if expected is not None:
        assert ("http://127.0.0.1:5001/health", 2) in seen


PLEONASM = {"confirmed": [], "suggested": [{"trecho": "Hoje mostro", "sugestao": "Mostro"}]}


def test_session_pleonasm_llm_is_off_by_default(tmp_path, documents):  # spec 003 AC-9
    def never(_):
        raise AssertionError("checker não deveria ser chamado")

    services = FakeServices(tmp_path, documents, pleonasm=RunnableLambda(never))
    result = post_session(TestClient(create_app(services))).json()
    assert all(o["source"] != "llm" for o in result["occurrences"])


def test_session_pleonasm_llm_when_enabled(tmp_path, documents):  # spec 003 AC-9
    prompts = []

    def checker(prompt):
        prompts.append(prompt.to_string())
        return AIMessage(json.dumps(PLEONASM, ensure_ascii=False))

    services = FakeServices(
        tmp_path,
        documents,
        settings=replace(Settings(), speech_pleonasm_llm=True),
        pleonasm=RunnableLambda(checker),
    )
    result = post_session(TestClient(create_app(services))).json()
    llm = [o for o in result["occurrences"] if o["source"] == "llm"]
    assert [(o["term"], o["suggestion"], o["confirmed_by_llm"]) for o in llm] == [
        ("Hoje mostro", "Mostro", True)
    ]
    assert "pleonasmo" in prompts[0].lower() and "JSON" in prompts[0]


def test_pleonasm_checker_failure_falls_back(tmp_path, documents):  # spec 003 AC-9/AC-12
    services = FakeServices(
        tmp_path, documents, settings=replace(Settings(), speech_pleonasm_llm=True)
    )
    result = post_session(TestClient(create_app(services)))
    assert result.status_code == 201
    assert all(o["source"] != "llm" for o in result.json()["occurrences"])


# ---------- spec 006: feedback guiado e exercícios ----------
GUIDED_KEYS = {
    "id",
    "pillar",
    "target",
    "title",
    "text",
    "priority",
    "subs",
    "exercises",
    "sources_available",
    "pillar_score",  # spec 008 AC-8
    "maintain",
}


def test_session_includes_guided_feedback(client, documents):  # spec 006 AC-10
    result = post_session(client).json()
    assert {"strength", "next_step"} <= {r["kind"] for r in result["recommendations"]}
    guided = result["guided_feedback"]
    assert 1 <= len(guided) <= 4
    chunk_ids = {d.id for d in documents}
    catalog = {e["id"]: e for e in CATALOG}
    for rec in guided:
        assert set(rec) == GUIDED_KEYS
        assert rec["priority"] in {"alta", "media", "baixa"}
        assert rec["sources_available"] is True
        for sub in rec["subs"]:
            assert sub["source"]["chunk_id"] in chunk_ids
        assert all(e == catalog[e["id"]] for e in rec["exercises"])
    tipo = next(r for r in guided if r["target"] == {"kind": "occurrence", "term": "tipo"})
    assert tipo["pillar"] == "fillers"
    assert [e["id"] for e in tipo["exercises"]] == ["silencio-no-lugar"]
    assert client.get(f"/v1/sessions/{result['session_id']}").json() == result


def test_guided_feedback_without_gold_or_catalog(tmp_path):  # spec 006 AC-7, AC-9, AC-10
    services = FakeServices(tmp_path, documents=None, catalog_fails=True)
    created = post_session(TestClient(create_app(services)))
    assert created.status_code == 201, created.text
    guided = created.json()["guided_feedback"]
    assert guided and all(r["subs"] == [] and not r["sources_available"] for r in guided)
    assert all(r["exercises"] == [] for r in guided)


def test_old_session_without_guided_feedback_still_loads(client, tmp_path):  # spec 006 AC-10
    result = post_session(client).json()
    db = next(tmp_path.glob("*.db"))
    with sqlite3.connect(db) as conn:
        old = json.loads(conn.execute("SELECT result_json FROM sessions").fetchone()[0])
        old.pop("guided_feedback")
        conn.execute("UPDATE sessions SET result_json = ?", (json.dumps(old),))
    loaded = client.get(f"/v1/sessions/{result['session_id']}")
    assert loaded.status_code == 200, loaded.text
    assert loaded.json()["guided_feedback"] is None
    assert loaded.json()["recommendations"] == result["recommendations"]


def test_old_guided_feedback_without_score_still_loads(client, tmp_path):  # spec 008 AC-8
    result = post_session(client).json()
    db = next(tmp_path.glob("*.db"))
    with sqlite3.connect(db) as conn:
        old = json.loads(conn.execute("SELECT result_json FROM sessions").fetchone()[0])
        for rec in old["guided_feedback"]:
            rec.pop("pillar_score")
            rec.pop("maintain")
        conn.execute("UPDATE sessions SET result_json = ?", (json.dumps(old),))
    loaded = client.get(f"/v1/sessions/{result['session_id']}")
    assert loaded.status_code == 200, loaded.text
    for rec in loaded.json()["guided_feedback"]:
        assert rec["pillar_score"] is None and rec["maintain"] is False


def test_habit_marks_catalog_exercise(client):  # spec 006 AC-11
    done = client.post("/v1/habits", json={"text": "Fiz", "exercise_id": "frase-curta"})
    assert done.status_code == 201, done.text
    assert done.json()["exercise_id"] == "frase-curta"
    plain = client.post("/v1/habits", json={"text": "Pausa"}).json()
    assert plain["exercise_id"] is None
    unknown = client.post("/v1/habits", json={"text": "Fiz", "exercise_id": "inventado"})
    assert unknown.status_code == 422 and "Exercício" in unknown.json()["detail"]
    listed = client.get("/v1/habits").json()
    assert [h["exercise_id"] for h in listed] == ["frase-curta", None]


def test_habits_migration_is_idempotent(tmp_path):  # spec 006 AC-11
    with sqlite3.connect(tmp_path / "cognus.db") as conn:
        conn.execute(
            "CREATE TABLE habits (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT "
            "NOT NULL, text TEXT NOT NULL, session_id TEXT)"
        )
        conn.execute("INSERT INTO habits (created_at, text) VALUES ('2026-01-01', 'antigo')")
    from rag_cognus.api.store import Store

    Store(tmp_path)
    store = Store(tmp_path)  # segunda abertura não falha
    store.add_habit("2026-01-02", "novo", None, exercise_id="frase-curta")
    assert [(h["text"], h["exercise_id"]) for h in store.habits()] == [
        ("antigo", None),
        ("novo", "frase-curta"),
    ]


# ---------- spec 008: mascote no perfil (substitui a foto) ----------
DEFAULT_MASCOT = {
    "figure": "masculino",
    "skin": "pele_3",
    "headwear": "gorro",
    "headwear_color": "petroleo",
    "shirt": "menta",
}
CUSTOM = {
    "figure": "feminino",
    "skin": "pele_5",
    "headwear": "cabelo_cacheado",
    "headwear_color": "ruivo",
    "shirt": "coral",
}


def put_profile(client, mascot=..., name="Lucas", goal=15):
    body = {"name": name, "daily_goal_minutes": goal}
    if mascot is not ...:
        body["mascot"] = mascot
    return client.put("/v1/profile", json=body)


@pytest.mark.parametrize(
    "mascot",
    [
        CUSTOM | {"skin": "pele_9"},
        {k: v for k, v in CUSTOM.items() if k != "shirt"},
        CUSTOM | {"chapeu": "coco"},
        "pele_3",
    ],
)
def test_profile_rejects_invalid_mascot(client, mascot):  # spec 008 AC-2
    put_profile(client, CUSTOM, name="Ana")
    rejected = put_profile(client, mascot, name="Outro")
    assert rejected.status_code == 422, rejected.text
    assert client.get("/v1/profile").json() == {
        "name": "Ana",
        "daily_goal_minutes": 15,
        "mascot": CUSTOM,
    }


def test_profile_keeps_or_replaces_mascot(client):  # spec 008 AC-3
    saved = put_profile(client, CUSTOM)
    assert saved.status_code == 200 and saved.json()["mascot"] == CUSTOM
    kept = put_profile(client, name="Lia")  # sem mascot
    assert kept.json() == {"name": "Lia", "daily_goal_minutes": 15, "mascot": CUSTOM}
    assert put_profile(client, None, goal=20).json()["mascot"] == CUSTOM
    other = DEFAULT_MASCOT | {"headwear": "nenhum"}
    assert put_profile(client, other).json()["mascot"] == other
    assert client.get("/v1/home").json()["profile"]["mascot"] == other


def test_profile_mascot_always_filled(client, tmp_path):  # spec 008 AC-4
    assert client.get("/v1/profile").json()["mascot"] == DEFAULT_MASCOT
    put_profile(client, CUSTOM)
    with sqlite3.connect(tmp_path / "cognus.db") as conn:
        conn.execute("UPDATE profile SET mascot_json = '{quebrado'")
    assert client.get("/v1/profile").json()["mascot"] == DEFAULT_MASCOT
    with sqlite3.connect(tmp_path / "cognus.db") as conn:
        conn.execute("UPDATE profile SET mascot_json = ?", ('{"skin": "pele_1", "x": 1}',))
    assert client.get("/v1/profile").json()["mascot"] == DEFAULT_MASCOT | {"skin": "pele_1"}
    schemas = client.app.openapi()["components"]["schemas"]
    assert set(schemas["Profile"]["properties"]) == {"name", "daily_goal_minutes", "mascot"}
    assert "mascot" in schemas["Profile"]["required"]


def test_profile_mascot_migration_is_idempotent(tmp_path):  # spec 008 AC-5
    with sqlite3.connect(tmp_path / "cognus.db") as conn:
        conn.execute(
            "CREATE TABLE profile (id INTEGER PRIMARY KEY CHECK (id = 1), name TEXT NOT NULL, "
            "daily_goal_minutes INTEGER NOT NULL)"
        )
        conn.execute("INSERT INTO profile VALUES (1, 'Antiga', 25)")
    from rag_cognus.api.store import Store

    Store(tmp_path)
    store = Store(tmp_path)  # segunda abertura não falha nem duplica a coluna
    with sqlite3.connect(tmp_path / "cognus.db") as conn:
        columns = [r[1] for r in conn.execute("PRAGMA table_info(profile)")]
    assert columns.count("mascot_json") == 1
    assert store.profile() == {"name": "Antiga", "daily_goal_minutes": 25, "mascot": None}
    store.save_profile("Antiga", 25, CUSTOM)
    assert store.profile()["mascot"] == CUSTOM


def test_mascot_options_endpoint(client):  # spec 008 AC-6
    from rag_cognus import mascot

    got = client.get("/v1/profile/mascot/options")
    assert got.status_code == 200, got.text
    assert got.json() == {"options": mascot.MASCOT_OPTIONS, "default": mascot.DEFAULT_MASCOT}
    schemas = client.app.openapi()["components"]["schemas"]
    assert "MascotOptions" in schemas


# ---------- spec 018: figura feminina do mascote ----------
OLD_MASCOT = {k: v for k, v in CUSTOM.items() if k != "figure"}  # corpo da spec 008


def test_018_options_lists_figure_first(client):  # spec 018 AC-4
    from rag_cognus import mascot

    body = client.get("/v1/profile/mascot/options").json()
    assert body == {"options": mascot.MASCOT_OPTIONS, "default": mascot.DEFAULT_MASCOT}
    assert next(iter(body["options"])) == "figure"
    assert body["default"]["figure"] == "masculino"
    schemas = client.app.openapi()["components"]["schemas"]
    assert "figure" in schemas["MascotPalette"]["properties"]
    assert "figure" in schemas["MascotPalette"]["required"]
    default_ref = schemas["MascotOptions"]["properties"]["default"]
    assert default_ref == {"$ref": "#/components/schemas/Mascot"}


def test_018_feminino_saved_and_read_everywhere(client):  # spec 018 AC-5
    saved = put_profile(client, CUSTOM, name="Lia")
    assert saved.status_code == 200, saved.text
    assert saved.json()["mascot"]["figure"] == "feminino"
    assert client.get("/v1/profile").json()["mascot"] == CUSTOM
    assert client.get("/v1/home").json()["profile"]["mascot"] == CUSTOM


def test_018_missing_figure_defaults_to_masculino(client):  # spec 018 AC-6
    saved = put_profile(client, OLD_MASCOT)
    assert saved.status_code == 200, saved.text
    assert saved.json()["mascot"] == OLD_MASCOT | {"figure": "masculino"}
    assert client.get("/v1/profile").json()["mascot"] == OLD_MASCOT | {"figure": "masculino"}


@pytest.mark.parametrize(
    "mascot",
    [
        CUSTOM | {"figure": "outro"},
        CUSTOM | {"figure": ""},
        CUSTOM | {"figure": None},
        CUSTOM | {"figura": "feminino"},
        {k: v for k, v in CUSTOM.items() if k != "skin"},
        {k: v for k, v in CUSTOM.items() if k != "headwear"},
        {k: v for k, v in CUSTOM.items() if k != "headwear_color"},
        {k: v for k, v in CUSTOM.items() if k != "shirt"},
    ],
)
def test_018_invalid_figure_or_missing_field_is_422(client, mascot):  # spec 018 AC-6
    put_profile(client, CUSTOM, name="Ana")
    rejected = put_profile(client, mascot, name="Outro")
    assert rejected.status_code == 422, rejected.text
    assert client.get("/v1/profile").json() == {
        "name": "Ana",
        "daily_goal_minutes": 15,
        "mascot": CUSTOM,
    }


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        (json.dumps(OLD_MASCOT), OLD_MASCOT | {"figure": "masculino"}),
        (None, DEFAULT_MASCOT),
        ("{quebrado", DEFAULT_MASCOT),
    ],
)
def test_018_old_profiles_read_without_rewrite(client, tmp_path, stored, expected):  # AC-7
    put_profile(client, CUSTOM)
    with sqlite3.connect(tmp_path / "cognus.db") as conn:
        conn.execute("UPDATE profile SET mascot_json = ?", (stored,))
    assert client.get("/v1/profile").json()["mascot"] == expected
    assert client.get("/v1/home").json()["profile"]["mascot"] == expected
    with sqlite3.connect(tmp_path / "cognus.db") as conn:
        row = conn.execute("SELECT mascot_json FROM profile").fetchone()
    assert row[0] == stored  # GET não reescreve a linha


def test_018_openapi_figure_required_out_optional_in(client):  # spec 018 AC-8
    schemas = client.app.openapi()["components"]["schemas"]
    out, inp = schemas["Mascot"], schemas["MascotIn"]
    assert "figure" in out["required"]
    assert out["properties"]["figure"]["enum"] == ["masculino", "feminino"]
    assert inp["properties"]["figure"]["enum"] == ["masculino", "feminino"]
    assert inp["properties"]["figure"]["default"] == "masculino"
    assert "figure" not in inp["required"]
    assert set(inp["required"]) == {"skin", "headwear", "headwear_color", "shirt"}
    assert inp.get("additionalProperties") is False


OLD_PHOTO_ROUTE = "/v1/profile/avatar"  # rota da foto removida (spec 008)


def test_photo_routes_removed(client, tmp_path):  # spec 008 AC-7
    old_file = tmp_path / "avatar.png"
    old_file.write_bytes(b"png antigo")
    assert (
        client.post(OLD_PHOTO_ROUTE, files={"image": ("f.png", b"x", "image/png")}).status_code
        == 404
    )
    assert client.get(OLD_PHOTO_ROUTE).status_code == 404
    assert client.delete(OLD_PHOTO_ROUTE).status_code == 404
    assert old_file.read_bytes() == b"png antigo"  # sem migração destrutiva
    spec = json.dumps(client.app.openapi()).lower()
    assert "avatar" not in spec


def test_guided_feedback_has_score_and_maintain(client):  # spec 008 AC-8
    result = post_session(client).json()
    for rec in result["guided_feedback"]:
        assert isinstance(rec["pillar_score"], int) and rec["maintain"] is False
    pillar = next(r for r in result["guided_feedback"] if r["target"]["kind"] == "pillar")
    assert pillar["pillar_score"] == round(result["pillars"][pillar["pillar"]]["score"])


# ---------- spec 013: mascote coach ----------
def test_mascot_tips_by_route(client):  # spec 013 AC-2, AC-9
    body = client.get("/v1/mascot/tips", params={"route": "/"}).json()
    assert body["enabled"] is True
    assert body["tips"][0]["id"] == "home-first-session"
    assert client.get("/v1/mascot/tips", params={"route": "/x"}).json()["tips"] == []


def test_mascot_tips_and_topics_work_without_ollama_or_gold(tmp_path):  # spec 013 AC-9
    client = TestClient(create_app(FakeServices(tmp_path, chat_fails=True)))
    assert client.get("/v1/mascot/tips", params={"route": "/metricas"}).status_code == 200
    assert client.get("/v1/mascot/topics", params={"route": "/"}).status_code == 200


def test_mascot_settings_silence_tips_and_persist(tmp_path, documents):  # spec 013 AC-10
    client = TestClient(create_app(FakeServices(tmp_path, documents)))
    assert client.get("/v1/mascot/settings").json() == {"tips_enabled": True}
    assert client.put("/v1/mascot/settings", json={"tips_enabled": False}).json() == {
        "tips_enabled": False
    }
    again = TestClient(create_app(FakeServices(tmp_path, documents)))  # mesmo banco
    body = again.get("/v1/mascot/tips", params={"route": "/"}).json()
    assert body == {"tips": [], "enabled": False}


def test_mascot_topics_follow_context(client):  # spec 013 AC-4
    ids = [t["id"] for t in client.get("/v1/mascot/topics", params={"route": "/"}).json()]
    assert "session_summary" not in ids and "weakest_pillar" not in ids
    session_id = post_session(client).json()["session_id"]
    ids = [
        t["id"]
        for t in client.get(
            "/v1/mascot/topics", params={"route": "/", "session_id": session_id}
        ).json()
    ]
    assert ids[:2] == ["session_summary", "weakest_pillar"]
    unknown = client.get("/v1/mascot/topics", params={"route": "/", "session_id": "nao-existe"})
    assert "session_summary" not in [t["id"] for t in unknown.json()]


def test_mascot_explain_with_llm(client):  # spec 013 AC-5, AC-8
    response = client.post("/v1/mascot/explain", json={"topic": "pace", "route": "/"})
    body = response.json()
    assert response.status_code == 200
    assert body["source"] == "llm" and body["text"] == MASCOT_TEXT["text"]
    assert body["topic"] == "pace" and "trace_id" in body
    mlflow.flush_trace_async_logging()
    trace = mlflow.get_trace(body["trace_id"])
    assert trace.info.tags["agent"] == "mascot"


def test_mascot_explain_falls_back_without_ollama(tmp_path):  # spec 013 AC-7
    client = TestClient(create_app(FakeServices(tmp_path, chat_fails=True)))
    session_id = post_session(client).json()["session_id"]
    body = client.post(
        "/v1/mascot/explain",
        json={"topic": "session_summary", "route": "/", "session_id": session_id},
    ).json()
    assert body["source"] == "regras"
    assert any(f["label"] == "Índice da sessão" for f in body["facts"])


def test_mascot_explain_missing_data_is_422(client):  # spec 013 AC-3
    response = client.post(
        "/v1/mascot/explain", json={"topic": "session_summary", "route": "/", "session_id": "x"}
    )
    assert response.status_code == 422 and "sessão" in response.json()["detail"]


def test_mascot_explain_unknown_topic_is_422(client):  # spec 013 AC-11
    response = client.post("/v1/mascot/explain", json={"topic": "bitcoin", "route": "/"})
    assert response.status_code == 422


# ---------- spec 014: onboarding ----------
def test_onboarding_starts_needed(client):  # spec 014 AC-1, AC-7
    body = client.get("/v1/onboarding").json()
    assert body["needed"] is True and body["step"] is None
    assert body["completed_version"] is None and body["version"] == api_app.ONBOARDING_VERSION


def test_onboarding_saves_step(client):  # spec 014 AC-2
    assert client.put("/v1/onboarding", json={"step": "mascot"}).json()["step"] == "mascot"
    assert client.get("/v1/onboarding").json()["step"] == "mascot"
    assert client.put("/v1/onboarding", json={"step": "fim"}).status_code == 422


@pytest.mark.parametrize("status", ["completed", "skipped"])
def test_onboarding_complete_or_skip(client, status):  # spec 014 AC-3
    body = client.put("/v1/onboarding", json={"status": status}).json()
    assert body["needed"] is False and body["completed_at"]
    assert body["completed_version"] == api_app.ONBOARDING_VERSION


def test_onboarding_reset(client):  # spec 014 AC-4
    client.put("/v1/onboarding", json={"step": "tour"})
    client.put("/v1/onboarding", json={"status": "completed"})
    body = client.put("/v1/onboarding", json={"status": "reset"}).json()
    assert body["needed"] is True and body["step"] is None and body["completed_version"] is None


def test_onboarding_new_version_is_needed_again(client, monkeypatch):  # spec 014 AC-5
    client.put("/v1/onboarding", json={"status": "completed"})
    monkeypatch.setattr(api_app, "ONBOARDING_VERSION", api_app.ONBOARDING_VERSION + 1)
    assert client.get("/v1/onboarding").json()["needed"] is True


def test_onboarding_persists_and_store_reopens(tmp_path, documents):  # spec 014 AC-6
    first = TestClient(create_app(FakeServices(tmp_path, documents)))
    first.put("/v1/onboarding", json={"step": "microphone"})
    second = TestClient(create_app(FakeServices(tmp_path, documents)))
    assert second.get("/v1/onboarding").json()["step"] == "microphone"
    assert second.get("/v1/profile").json()["name"] == "Você"  # perfil intocado


# ---------- spec 014: consentimento de dados de uso ----------
def test_privacy_starts_undecided(client):  # spec 014 AC-7a
    body = client.get("/v1/privacy").json()
    assert body["tracking_allowed"] is None and body["decided_at"] is None
    assert body["decided_version"] is None
    assert body["policy_version"] == api_app.PRIVACY_POLICY_VERSION


@pytest.mark.parametrize("allowed", [True, False])
def test_privacy_saves_choice_and_persists(tmp_path, documents, allowed):  # spec 014 AC-7a
    client = TestClient(create_app(FakeServices(tmp_path, documents)))
    body = client.put("/v1/privacy", json={"tracking_allowed": allowed}).json()
    assert body["tracking_allowed"] is allowed and body["decided_at"]
    assert body["decided_version"] == api_app.PRIVACY_POLICY_VERSION
    again = TestClient(create_app(FakeServices(tmp_path, documents)))
    assert again.get("/v1/privacy").json()["tracking_allowed"] is allowed


@pytest.mark.parametrize("payload", [{}, {"tracking_allowed": True, "extra": 1}])
def test_privacy_rejects_invalid_body(client, payload):  # spec 014 AC-7a
    assert client.put("/v1/privacy", json=payload).status_code == 422
    assert client.get("/v1/privacy").json()["tracking_allowed"] is None


def test_onboarding_has_privacy_step_and_version_2(client):  # spec 014 AC-2, AC-7b
    assert api_app.ONBOARDING_VERSION == 2
    assert client.put("/v1/onboarding", json={"step": "privacy"}).json()["step"] == "privacy"


def test_mascot_explains_ask_evaluation(client):  # spec 013 AC-3, AC-4, AC-17
    ask_id = client.post("/v1/ask", json={"query": "storytelling"}).json()["ask_id"]
    assert client.get(f"/v1/ask/{ask_id}/evaluation").json()["status"] == "done"
    params = {"route": "/cognus", "ask_id": ask_id}
    ids = [t["id"] for t in client.get("/v1/mascot/topics", params=params).json()]
    assert ids[0] == "ask_evaluation"
    body = client.post(
        "/v1/mascot/explain", json={"topic": "ask_evaluation", "route": "/cognus", "ask_id": ask_id}
    ).json()
    labels = {f["label"] for f in body["facts"]}
    assert {"Qualidade geral", "Fundamentação nas fontes", "Integridade das citações"} <= labels
