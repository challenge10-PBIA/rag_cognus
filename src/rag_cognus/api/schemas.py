"""Modelos de entrada e saída da API: viram o OpenAPI que gera os tipos do front."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from rag_cognus.agents.schemas import AudienceProfile


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


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    daily_goal_minutes: int = Field(ge=1, le=240)


class HabitIn(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    session_id: str | None = None


class FeedbackIn(BaseModel):
    trace_id: str
    value: bool
    comment: str | None = Field(default=None, max_length=1000)


# ---------- saída ----------
class Profile(BaseModel):
    name: str
    daily_goal_minutes: int


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


class Health(BaseModel):
    ollama: bool
    gold_chunks: int | None
    chat_model: str
    whisper_model: str


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


class Pillars(BaseModel):
    pace: Pillar
    pauses: Pillar
    fillers: Pillar
    clarity: Pillar


class Word(BaseModel):
    word: str
    start: float
    end: float
    filler: bool


class Source(BaseModel):
    chunk_id: str
    title: str | None = None
    url: str | None = None


class Recommendation(BaseModel):
    kind: Literal["strength", "next_step", "tip"]
    title: str
    text: str
    sources: list[Source] = []


class Flow(BaseModel):
    contour: list[float]
    stability: Literal["estavel", "variavel"]


class Adapted(BaseModel):
    adapted_text: str
    changes: list[str]
    rehearsal_tips: list[str]


class SessionResult(BaseModel):
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
    recommendations: list[Recommendation]
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
    streak_days: int
    achievements: list[Achievement]
    guidance: list[Guidance]


class Habit(BaseModel):
    id: int
    created_at: str
    text: str
    session_id: str | None


class Transcription(BaseModel):
    text: str
