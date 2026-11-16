"""API HTTP do Cognus para o front web/mobile (spec 002). Rode com `rag-cognus api`."""

from __future__ import annotations

import os
import threading
import uuid
from datetime import date, datetime
from pathlib import Path

import httpx
import mlflow
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from rag_cognus import progress, speech
from rag_cognus.agents.communication import CommunicationAgent
from rag_cognus.agents.evidence import EvidenceAgent
from rag_cognus.agents.pipeline import EvidenceToAudience
from rag_cognus.agents.schemas import AUDIENCES, CONTEXTS, AudienceProfile
from rag_cognus.api import schemas as s
from rag_cognus.api.store import Store
from rag_cognus.config import Settings
from rag_cognus.speech_analysis import PILLAR_NAMES, analyze_words, energy_contour, is_filler

ROOT = Path(__file__).resolve().parents[3]

MODES = {
    "daily_pitch": {
        "label": "Daily Pitch",
        "scenario": "Atualização rápida para o time",
        "audience": "executivo",
        "context": "pitch",
        "minutes": 1,
    },
    "reuniao_1_1": {
        "label": "Reunião 1:1",
        "scenario": "Conversa individual com sua liderança",
        "audience": "executivo",
        "context": "reuniao",
        "minutes": 3,
    },
    "apresentacao_tecnica": {
        "label": "Apres. Técnica",
        "scenario": "Apresentação para stakeholders",
        "audience": "executivo",
        "context": "palestra",
        "minutes": 5,
    },
    "espontanea": {
        "label": "Prática Espontânea",
        "scenario": "Fale por 60 segundos sobre o que aprendeu hoje",
        "audience": "leigo",
        "context": "palestra",
        "minutes": 1,
    },
}
NICHE_LABELS = {
    "apresentacoes_oratoria": "Apresentações e oratória",
    "assertividade_escuta": "Comunicação assertiva e escuta",
    "clareza_linguagem": "Clareza e linguagem",
    "voz_saude_vocal": "Voz e saúde vocal",
    "fluencia_gagueira": "Fluência e gagueira",
    "fono_contextos_profissionais": "Fonoaudiologia e contextos profissionais",
}
TONES = {"neutro": "Neutro", "formal": "Formal", "informal": "Informal"}
STRONG = {
    "pace": "ritmo e cadência",
    "pauses": "uso de pausas",
    "fillers": "fala limpa",
    "clarity": "clareza da mensagem",
}


class GoldUnavailable(RuntimeError):
    pass


class Services:
    """Dependências da API. Os testes trocam modelos e dados por fakes via subclasse."""

    def __init__(
        self, settings: Settings, data_dir: Path | None = None, snapshot: Path | None = None
    ):
        self.settings = settings
        self.snapshot = Path(snapshot or ROOT / ".cache/gold.jsonl")
        self.store = Store(data_dir or ROOT / ".cache/app")
        self._lock = threading.Lock()
        self._retriever = None
        self._transcriber = None

    def retriever(self):
        with self._lock:
            if self._retriever is None:
                if not self.snapshot.exists():
                    raise GoldUnavailable(
                        "Base de conhecimento não carregada: rode `rag-cognus sync-gold`."
                    )
                from rag_cognus.gold import load_snapshot
                from rag_cognus.retrieval import GoldRetriever

                self._retriever = GoldRetriever(load_snapshot(self.snapshot), self.settings)
            return self._retriever

    def transcriber(self):
        with self._lock:
            if self._transcriber is None:
                self._transcriber = speech.load_transcriber(self.settings)
            return self._transcriber

    # Modelos de linguagem: None = ChatOllama padrão (llm.make_ollama).
    def rag_chat(self):
        return None

    def synthesis_chat(self):
        return None

    def fast_chat(self):
        return None

    def communication_chat(self):
        return None


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _pillar_detail(name: str, pillar: dict) -> str:
    if name == "pace":
        return {
            "ideal": "Cadência calma e natural",
            "lento": "Um pouco devagar para o público",
            "rapido": "Acelerado: o público pode se perder",
        }[pillar["label"]]
    if name == "pauses":
        long = pillar["long_silences"]
        return f"{long} silêncio(s) longo(s)" if long else "Sem silêncio constrangedor"
    if name == "fillers":
        if not pillar["counts"]:
            return "Zero “éé” ou “tipo”"
        word, count = max(pillar["counts"].items(), key=lambda kv: kv[1])
        return f"Mais usado: “{word}” ({count}×)"
    return "Vocabulário objetivo" if pillar["label"] == "alto" else "Frases podem ser mais curtas"


def _next_step(name: str, pillar: dict) -> str:
    if name == "pace":
        if pillar["label"] == "lento":
            return "Acelere um pouco: mire entre 120 e 160 palavras por minuto."
        if pillar["label"] == "rapido":
            return "Desacelere nos pontos-chave: mire entre 120 e 160 palavras por minuto."
        return "Mantenha o ritmo e varie a velocidade para destacar o que importa."
    if name == "pauses":
        if pillar["long_silences"]:
            return "Evite silêncios acima de 3 segundos: tenha o próximo tópico anotado."
        if pillar["label"] == "excessivas":
            return "Junte ideias relacionadas: pausas demais quebram o fluxo."
        return "Faça pausas de 1 segundo ao mudar de tópico para reforçar o impacto."
    if name == "fillers":
        if pillar["counts"]:
            word, count = max(pillar["counts"].items(), key=lambda kv: kv[1])
            return f"Você usou “{word}” {count}×: troque por um silêncio curto e respire."
        return "Continue assim: silêncio curto no lugar dos vícios."
    return "Use frases mais curtas e diga a conclusão primeiro."


def _strength(name: str, pillar: dict) -> str:
    return {
        "pace": f"Seu ritmo de {pillar['value']} ppm ajuda o público a acompanhar.",
        "pauses": f"Você fez {pillar['value']} pausas conscientes, dando peso às ideias.",
        "fillers": f"{pillar['value']}% da sua fala ficou livre de vícios.",
        "clarity": "Sua mensagem ficou objetiva e fácil de seguir.",
    }[name]


def _headline(index: int, best: str) -> str:
    if index >= 85:
        return f"Excelente {STRONG[best]}"
    if index >= 70:
        return f"Boa sessão, com destaque para {STRONG[best]}"
    if index >= 50:
        return "Sessão em evolução"
    return "Vamos ajustar o básico"


def _sources(services: Services, query: str, k: int = 2) -> list[dict]:
    try:
        docs = services.retriever().search(query, k=k)
    except GoldUnavailable:
        return []
    return [
        {"chunk_id": d.id, "title": d.metadata.get("title"), "url": d.metadata.get("source_url")}
        for d in docs
    ]


def analyze_session(
    services: Services,
    wav: bytes,
    mode: str,
    challenge_id: str | None,
    anxiety_before: int | None,
    anxiety_after: int | None,
) -> dict:
    settings = services.settings
    heard = speech.transcribe_words(services.transcriber(), wav)
    analysis = analyze_words(heard["words"])
    pillars = {
        name: {"title": PILLAR_NAMES[name], "detail": _pillar_detail(name, p), **p}
        for name, p in analysis["pillars"].items()
    }
    ranked = sorted(pillars, key=lambda n: pillars[n]["score"])
    best, worst = ranked[-1], ranked[0]
    config = MODES[mode]
    adapted, trace_id = None, None
    try:
        # Tempo-alvo = o menor entre o modo e a fala real: a adaptação pode encurtar,
        # nunca alongar com conteúdo novo (fala de 20 s num modo de 5 min).
        spoken = max(0.5, round(heard["duration"] / 60, 1))
        profile = AudienceProfile(
            audience=config["audience"],
            context=config["context"],
            minutes=min(config["minutes"], spoken),
        )
        agent = CommunicationAgent(settings, chat=services.communication_chat())
        adapted = agent.run(heard["text"] or analysis["text"], profile)["adapted"]
        trace_id = mlflow.get_last_active_trace_id()
    except Exception:
        adapted = None  # sem LLM a análise acústica continua valendo (AC-8)
    recommendations = [
        {
            "kind": "strength",
            "title": "Ponto Forte",
            "text": _strength(best, pillars[best]),
            "sources": [],
        },
        {
            "kind": "next_step",
            "title": "Dica para a próxima sessão",
            "text": _next_step(worst, pillars[worst]),
            "sources": _sources(services, progress.CHALLENGES[worst]["query"]),
        },
    ]
    for tip in (adapted or {}).get("rehearsal_tips", [])[:2]:
        recommendations.append(
            {"kind": "tip", "title": "Dica de ensaio", "text": tip, "sources": []}
        )
    index = analysis["index"]
    return {
        "session_id": uuid.uuid4().hex[:12],
        "created_at": _now(),
        "mode": mode,
        "mode_label": config["label"],
        "scenario": config["scenario"],
        "duration_seconds": round(heard["duration"], 1),
        "index": index,
        "headline": _headline(index, best),
        "summary": f"Seu ponto mais forte foi {STRONG[best]}; o próximo foco é {STRONG[worst]}.",
        "pillars": pillars,
        "diction": analysis["diction"],
        "flow": energy_contour(heard["audio"]),
        "transcript": [
            {
                "word": w["word"],
                "start": w["start"],
                "end": w["end"],
                "filler": is_filler(w["word"]),
            }
            for w in heard["words"]
        ],
        "recommendations": recommendations,
        "adapted": adapted,
        "challenge_id": challenge_id,
        "anxiety_before": anxiety_before,
        "anxiety_after": anxiety_after,
        "trace_id": trace_id,
    }


def _record(result: dict) -> dict:
    return {
        k: result[k]
        for k in (
            "created_at",
            "duration_seconds",
            "index",
            "challenge_id",
            "anxiety_before",
            "anxiety_after",
            "mode",
        )
    } | {"pillars": {n: p["score"] for n, p in result["pillars"].items()}}


def _summary(result: dict) -> dict:
    return {
        k: result[k]
        for k in (
            "session_id",
            "created_at",
            "mode",
            "mode_label",
            "duration_seconds",
            "index",
            "headline",
        )
    }


def _modes() -> list[dict]:
    return [{"id": k, **v} for k, v in MODES.items()]


def create_app(services: Services | None = None) -> FastAPI:
    services = services or Services(Settings.from_env())
    app = FastAPI(
        title="Cognus API",
        version="0.2.0",
        description="Treino de fala: sessões, progresso, RAG e agentes (local).",
    )
    origins = os.getenv("API_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    app.add_middleware(
        CORSMiddleware, allow_origins=origins.split(","), allow_methods=["*"], allow_headers=["*"]
    )
    store = services.store

    def gold():
        try:
            return services.retriever()
        except GoldUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc

    @app.get("/v1/health", response_model=s.Health)
    def health():
        try:
            ollama = httpx.get(services.settings.ollama_url + "/api/tags", timeout=2).is_success
        except httpx.HTTPError:
            ollama = False
        try:
            chunks = len(services.retriever().documents)
        except GoldUnavailable:
            chunks = None
        return {
            "ollama": ollama,
            "gold_chunks": chunks,
            "chat_model": services.settings.chat_model,
            "whisper_model": services.settings.whisper_model,
        }

    @app.get("/v1/meta", response_model=s.Meta)
    def meta():
        return {
            "modes": _modes(),
            "audiences": [
                {"id": k, "label": k.capitalize(), "description": v} for k, v in AUDIENCES.items()
            ],
            "contexts": [
                {"id": k, "label": k.capitalize(), "description": v} for k, v in CONTEXTS.items()
            ],
            "tones": [{"id": k, "label": v} for k, v in TONES.items()],
            "niches": [{"id": k, "label": v} for k, v in NICHE_LABELS.items()],
        }

    @app.get("/v1/profile", response_model=s.Profile)
    def get_profile():
        return store.profile()

    @app.put("/v1/profile", response_model=s.Profile)
    def put_profile(body: s.ProfileIn):
        return store.save_profile(body.name, body.daily_goal_minutes)

    @app.post("/v1/sessions", response_model=s.SessionResult, status_code=201)
    def create_session(
        audio: UploadFile = File(...),
        mode: str = Form("espontanea"),
        challenge_id: str | None = Form(None),
        anxiety_before: int | None = Form(None, ge=1, le=5),
        anxiety_after: int | None = Form(None, ge=1, le=5),
    ):
        if mode not in MODES:
            raise HTTPException(422, f"Modo desconhecido: {mode}.")
        wav = audio.file.read()
        try:
            result = analyze_session(
                services, wav, mode, challenge_id, anxiety_before, anxiety_after
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        store.save_session(result, _record(result), wav)
        return result

    @app.get("/v1/sessions", response_model=list[s.SessionSummary])
    def list_sessions():
        return [_summary(r) for r in store.sessions()]

    @app.get("/v1/sessions/{session_id}", response_model=s.SessionResult)
    def get_session(session_id: str):
        result = store.session(session_id)
        if result is None:
            raise HTTPException(404, "Sessão não encontrada.")
        return result

    @app.get("/v1/sessions/{session_id}/audio")
    def get_audio(session_id: str):
        path = store.audio_path(session_id)
        if path is None:
            raise HTTPException(404, "Áudio não encontrado.")
        return FileResponse(path, media_type="audio/wav")

    @app.get("/v1/home", response_model=s.Home)
    def home():
        today = date.today()
        records, results = store.records(), store.sessions()
        profile = store.profile()
        latest = None
        if results:
            last = results[0]
            before = results[1]["index"] if len(results) > 1 else None
            step = next(r for r in last["recommendations"] if r["kind"] == "next_step")
            latest = {
                "session_id": last["session_id"],
                "created_at": last["created_at"],
                "mode_label": last["mode_label"],
                "index": last["index"],
                "index_change": None if before is None else last["index"] - before,
                "headline": last["headline"],
                "feedback": f"{last['headline']} na sessão {last['mode_label']}. {step['text']}",
            }
        week = progress.summary(records, "week", today)
        return {
            "profile": profile,
            "streak_days": progress.streak(records, today),
            "daily_goal": progress.daily_goal(records, today, profile["daily_goal_minutes"]),
            "level": week["level"] if records else progress.level(None),
            "latest": latest,
            "modes": _modes(),
            "challenges": progress.challenges(records, today),
        }

    @app.get("/v1/progress", response_model=s.Progress)
    def get_progress(period: str = Query("week", pattern="^(week|month|quarter)$")):
        today = date.today()
        records = store.records()
        data = progress.summary(records, period, today)
        # Direcionamentos: pilares mais fracos das últimas sessões + fontes da Gold.
        guidance = [
            {k: v for k, v in g.items() if k != "query"}
            | {"sources": _sources(services, g["query"])}
            for g in progress.guidance(records)
        ]
        return data | {
            "streak_days": progress.streak(records, today),
            "achievements": progress.achievements(records, today),
            "guidance": guidance,
        }

    @app.get("/v1/habits", response_model=list[s.Habit])
    def list_habits():
        return store.habits()

    @app.post("/v1/habits", response_model=s.Habit, status_code=201)
    def add_habit(body: s.HabitIn):
        return store.add_habit(_now(), body.text, body.session_id)

    @app.post("/v1/speech/transcribe", response_model=s.Transcription)
    def transcribe(audio: UploadFile = File(...)):
        try:
            return {"text": speech.transcribe(services.transcriber(), audio.file.read())}
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/v1/ask")
    def ask(body: s.AskIn):
        from rag_cognus.chain import RagPipeline

        pipeline = RagPipeline(gold(), services.settings, chat=services.rag_chat())
        try:
            result = pipeline.predict(body.query, body.niche)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return result | {"trace_id": mlflow.get_last_active_trace_id()}

    def evidence_agent():
        return EvidenceAgent(
            gold(),
            services.settings,
            chat=services.synthesis_chat(),
            fast_chat=services.fast_chat(),
        )

    def communication_agent():
        return CommunicationAgent(services.settings, chat=services.communication_chat())

    @app.post("/v1/agents/evidence")
    def agent_evidence(body: s.EvidenceIn):
        result = evidence_agent().run(body.topic, body.niche)
        return result | {"trace_id": mlflow.get_last_active_trace_id()}

    @app.post("/v1/agents/communication")
    def agent_communication(body: s.CommunicationIn):
        result = communication_agent().run(body.text, body.profile, body.source_claims)
        return result | {"trace_id": mlflow.get_last_active_trace_id()}

    @app.post("/v1/agents/pipeline")
    def agent_pipeline(body: s.PipelineIn):
        result = EvidenceToAudience(evidence_agent(), communication_agent()).run(
            body.topic, body.profile, body.niche
        )
        return result | {"trace_id": mlflow.get_last_active_trace_id()}

    @app.post("/v1/feedback", status_code=204)
    def feedback(body: s.FeedbackIn):
        from mlflow.entities import AssessmentSource

        mlflow.flush_trace_async_logging()
        mlflow.log_feedback(
            trace_id=body.trace_id,
            name="user_feedback",
            value=body.value,
            rationale=body.comment,
            source=AssessmentSource(source_type="HUMAN", source_id="usuario-local"),
        )
        return Response(status_code=204)

    return app
