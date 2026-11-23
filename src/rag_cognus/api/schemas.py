"""Modelos de entrada e saída da API: viram o OpenAPI que gera os tipos do front."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rag_cognus.agents.schemas import AudienceProfile
from rag_cognus.coach import TOPICS as COACH_TOPICS
from rag_cognus.mascot import IDS as MASCOT_IDS
from rag_cognus.phonetics import PhoneticCatalog as PhoneticCatalog
from rag_cognus.phonetics import PhoneticExercise as PhoneticExercise


# ---------- entrada ----------
class AskIn(BaseModel):
    query: str = Field(min_length=1, max_length=3000)
    niche: str | None = None


class EvidenceIn(BaseModel):
    topic: str = Field(min_length=1, max_length=1000)
    niche: str | None = None


class CommunicationIn(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    profile: AudienceProfile = AudienceProfile()
    source_claims: list[str] | None = None


class PipelineIn(BaseModel):
    topic: str = Field(min_length=1, max_length=1000)
    profile: AudienceProfile = AudienceProfile()
    niche: str | None = None


class Mascot(BaseModel):
    """Ids da paleta fechada de `rag_cognus.mascot` (specs 008 e 018)."""

    figure: Literal[MASCOT_IDS["figure"]]
    skin: Literal[MASCOT_IDS["skin"]]
    headwear: Literal[MASCOT_IDS["headwear"]]
    headwear_color: Literal[MASCOT_IDS["headwear_color"]]
    shirt: Literal[MASCOT_IDS["shirt"]]


class MascotIn(Mascot):
    model_config = ConfigDict(extra="forbid")

    # Opcional só na entrada (spec 018 AC-6): o front antigo envia o mascote sem `figure`.
    figure: Literal[MASCOT_IDS["figure"]] = "masculino"


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    daily_goal_minutes: int = Field(ge=1, le=240)
    mascot: MascotIn | None = None  # ausente/null mantém o salvo (spec 008 AC-3)


class HabitIn(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    session_id: str | None = None
    exercise_id: str | None = Field(default=None, max_length=120)  # id do catálogo (spec 006)


class FeedbackIn(BaseModel):
    trace_id: str
    value: bool
    comment: str | None = Field(default=None, max_length=1000)


# ---------- saída ----------
class Profile(BaseModel):
    name: str
    daily_goal_minutes: int
    mascot: Mascot  # sempre preenchido; padrão quando nunca salvo (spec 008 AC-4)


class MascotOption(BaseModel):
    id: str
    label: str
    hex: str | None


class MascotPalette(BaseModel):
    figure: list[MascotOption]
    skin: list[MascotOption]
    headwear: list[MascotOption]
    headwear_color: list[MascotOption]
    shirt: list[MascotOption]


class MascotOptions(BaseModel):
    options: MascotPalette
    default: Mascot


class Option(BaseModel):
    id: str
    label: str
    description: str = ""


class Mode(BaseModel):
    id: str
    label: str
    scenario: str
    audience: str
    context: str
    minutes: float


class Meta(BaseModel):
    modes: list[Mode]
    audiences: list[Option]
    contexts: list[Option]
    tones: list[Option]
    niches: list[Option]


VoiceProvider = Literal["piper", "elevenlabs", "off"]


class Health(BaseModel):
    ollama: bool
    gold_chunks: int | None
    chat_model: str
    whisper_model: str
    # true/false = servidor MLflow local respondeu /health; null = sqlite:/file: (sem servidor)
    mlflow: bool | None = None
    # Voz do avatar (spec 027): só configuração e modelo em disco, sem sintetizar.
    voice_available: bool = False
    voice_provider: VoiceProvider = "off"
    presentation_voice_provider: VoiceProvider = "off"


# ---------- RAG (spec 004) ----------
EvaluationStatus = Literal["pending", "done", "error", "disabled"]


class Citation(BaseModel):
    chunk_id: str
    source_url: str | None = None
    title: str | None = None
    audience: str | None = None


class StructuredSource(BaseModel):
    chunk_id: str
    titulo: str | None = None
    nicho: str | None = None
    url: str | None = None
    trecho: str


class StructuredAnswer(BaseModel):
    resumo: str
    pontos: list[str] = Field(default_factory=list, max_length=5)
    recomendacao: str | None = None
    fontes: list[StructuredSource] = []


class AskOut(BaseModel):
    response: str
    abstained: bool
    cited_chunk_ids: list[str]
    citations: list[Citation]
    trace_id: str | None = None
    ask_id: str
    evaluation_status: EvaluationStatus
    structured: StructuredAnswer


class JudgeScore(BaseModel):
    name: str
    label: str
    score: int = Field(ge=1, le=5)
    reason: str


class OnlineMetrics(BaseModel):
    context_relevance: int
    groundedness: int
    answer_relevance: int
    accuracy: int
    professionalism: int
    quality_score: float
    niche_metadata_precision_proxy: float | None = None
    citation_integrity: float
    latency_seconds: float


class AskEvaluation(BaseModel):
    ask_id: str
    status: EvaluationStatus
    metrics: OnlineMetrics | None = None
    judges: list[JudgeScore] = []
    judge_model: str | None = None
    mlflow_logged: bool = False
    error: str | None = None
    created_at: str
    finished_at: str | None = None


class Pillar(BaseModel):
    title: str
    value: int | float | str
    unit: str
    score: int
    label: str
    detail: str
    counts: dict[str, int] | None = None
    long_silences: int | None = None
    per_minute: float | None = None
    pleonasms: int | None = None


class Pillars(BaseModel):
    pace: Pillar
    pauses: Pillar
    fillers: Pillar
    clarity: Pillar


OccurrenceKind = Literal["vicio_fixo", "vicio_detectado", "pleonasmo"]


class Word(BaseModel):
    word: str
    start: float
    end: float
    filler: bool
    kind: OccurrenceKind | None = None


class Occurrence(BaseModel):
    term: str
    kind: OccurrenceKind
    excerpt: str
    start: float
    end: float
    suggestion: str
    source: Literal["lexico", "estatistica", "llm"]
    confirmed_by_llm: bool | None = None


class Source(BaseModel):
    chunk_id: str
    title: str | None = None
    url: str | None = None


class Recommendation(BaseModel):
    kind: Literal["strength", "next_step", "tip"]
    title: str
    text: str
    sources: list[Source] = []


# ---------- feedback guiado (spec 006) ----------
class ExerciseSource(BaseModel):
    titulo: str
    autor: str
    ano: int
    url: str
    tipo: Literal["artigo", "livro", "instituicao"]


class Exercise(BaseModel):
    id: str
    titulo: str
    categoria: str
    pilares: list[str]
    passos: list[str]
    duracao_min: int
    nivel: Literal["iniciante", "intermediario", "avancado"]
    fonte: ExerciseSource
    verificado_em: str


class GuidedTarget(BaseModel):
    kind: Literal["pillar", "occurrence"]
    term: str | None = None


class GuidedSub(BaseModel):
    text: str
    source: Source
    excerpt: str


class GuidedRecommendation(BaseModel):
    id: str
    pillar: Literal["pace", "pauses", "fillers", "clarity", "diction"]
    target: GuidedTarget
    title: str
    text: str
    priority: Literal["alta", "media", "baixa"]
    subs: list[GuidedSub] = []
    exercises: list[Exercise] = []
    sources_available: bool
    pillar_score: int | None = None  # score do pilar alvo; sessões antigas: None (spec 008)
    maintain: bool = False  # recomendação "Manter" (spec 006 AC-2)


class Flow(BaseModel):
    contour: list[float]
    stability: Literal["estavel", "variavel"]


class Adapted(BaseModel):
    adapted_text: str
    changes: list[str]
    rehearsal_tips: list[str]


class SessionResult(BaseModel):
    exercise_id: str | None = None
    phoneme_id: str | None = None
    session_id: str
    created_at: str
    mode: str
    mode_label: str
    scenario: str
    duration_seconds: float
    index: int
    headline: str
    summary: str
    pillars: Pillars
    diction: int
    flow: Flow
    transcript: list[Word]
    occurrences: list[Occurrence] | None = None
    recommendations: list[Recommendation]
    guided_feedback: list[GuidedRecommendation] | None = None
    adapted: Adapted | None
    challenge_id: str | None
    anxiety_before: int | None
    anxiety_after: int | None
    trace_id: str | None


class SessionSummary(BaseModel):
    session_id: str
    created_at: str
    mode: str
    mode_label: str
    duration_seconds: float
    index: int
    headline: str


class Challenge(BaseModel):
    id: str
    pillar: str
    title: str
    description: str
    minutes: int
    mode: str
    priority: Literal["alta", "media", "baixa"]
    done: bool


class Level(BaseModel):
    number: int
    name: str


class DailyGoal(BaseModel):
    minutes_today: float
    goal_minutes: int
    percent: int


class Latest(BaseModel):
    session_id: str
    created_at: str
    mode_label: str
    index: int
    index_change: int | None
    headline: str
    feedback: str


class Home(BaseModel):
    profile: Profile
    streak_days: int
    daily_goal: DailyGoal
    level: Level
    latest: Latest | None
    modes: list[Mode]
    challenges: list[Challenge]


class Bar(BaseModel):
    label: str
    minutes: float
    index: int | None
    calm: int | None
    pillars: dict[str, int | None] | None = None  # spec 029 AC-8; None = barra sem sessões


class Achievement(BaseModel):
    id: str
    title: str
    description: str
    badge: str
    unlocked: bool


class Guidance(BaseModel):
    pillar: str
    focus: str
    title: str
    description: str
    minutes: int
    mode: str
    sources: list[Source] = []


class Progress(BaseModel):
    period: Literal["week", "month", "quarter"]
    bars: list[Bar]
    index: int | None
    index_change_pct: float | None
    level: Level
    sessions: int
    avg_daily_minutes: float
    anxiety_change_pct: float | None
    pillars: dict[str, int | None]
    # Spec 029 AC-8: período anterior (mesma janela de index_change_pct) e variação em pontos.
    pillars_previous: dict[str, int | None] = {}
    pillars_change: dict[str, int | None] = {}
    bar_goal_minutes: float | None = None  # meta diária × dias da barra (1 ou 7)
    streak_days: int
    achievements: list[Achievement]
    guidance: list[Guidance]


class Habit(BaseModel):
    id: int
    created_at: str
    text: str
    session_id: str | None
    exercise_id: str | None = None


class Transcription(BaseModel):
    text: str


# ---------- mascote coach (spec 013) ----------
MascotMood = Literal["feliz", "neutro", "pensativo"]
CoachTopic = Literal[COACH_TOPICS]


class MascotTip(BaseModel):
    id: str
    text: str
    mood: MascotMood
    topic: CoachTopic | None = None


class MascotTips(BaseModel):
    tips: list[MascotTip]
    enabled: bool


class MascotTopic(BaseModel):
    id: CoachTopic
    label: str


class ExplainIn(BaseModel):
    topic: CoachTopic
    route: str = Field(default="/", max_length=200)
    session_id: str | None = Field(default=None, max_length=120)
    ask_id: str | None = Field(default=None, max_length=120)


class Fact(BaseModel):
    label: str
    value: str


class Explanation(BaseModel):
    topic: CoachTopic
    text: str
    mood: MascotMood
    facts: list[Fact]
    source: Literal["llm", "regras"]
    trace_id: str | None = None


class MascotSettings(BaseModel):
    tips_enabled: bool = True
    # Spec 027: Piper é local, então a voz vem ligada; falar sozinho só se a pessoa pedir.
    voice_enabled: bool = True
    voice_autoplay: bool = False


class SpeakIn(BaseModel):
    """Corpo de POST /v1/voice/speak; o limite de 600 vale após normalizar (voice.py)."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2000)
    purpose: Literal["tip", "explain", "presentation"] = "tip"
    facts: list[Fact] = []


# ---------- onboarding (spec 014) ----------
OnboardingStep = Literal["welcome", "privacy", "profile", "mascot", "microphone", "tour", "done"]


class OnboardingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: OnboardingStep | None = None
    status: Literal["completed", "skipped", "reset"] | None = None


class Onboarding(BaseModel):
    version: int
    completed_version: int | None
    completed_at: str | None
    step: OnboardingStep | None
    needed: bool


# ---------- consentimento de dados de uso (spec 014 AC-7a) ----------
class PrivacyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tracking_allowed: bool


class Privacy(BaseModel):
    tracking_allowed: bool | None  # None = ainda não decidiu (tratar como não permitido)
    decided_at: str | None
    policy_version: int
    decided_version: int | None
