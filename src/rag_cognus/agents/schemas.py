"""Contratos entre os agentes. Os modelos *Draft são o formato JSON exigido do LLM."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Audience = Literal["leigo", "executivo", "academico", "estudante", "saude"]
Context = Literal["pitch", "aula", "reuniao", "palestra", "entrevista"]
Tone = Literal["formal", "neutro", "informal"]

AUDIENCES: dict[str, str] = {
    "leigo": "Público geral, sem formação técnica: linguagem cotidiana e exemplos concretos.",
    "executivo": "Executivos e gestores: conclusão primeiro, objetivo, foco em impacto e decisão.",
    "academico": "Público acadêmico: termos precisos, nuances e indicação das fontes.",
    "estudante": "Estudantes: didático, passo a passo, com analogias e exemplos.",
    "saude": "Profissionais de saúde: vocabulário técnico, sem simplificar demais.",
}
CONTEXTS: dict[str, str] = {
    "pitch": "Pitch curto: gancho, problema, proposta e chamada para ação.",
    "aula": "Aula: objetivo, explicação em etapas e recapitulação.",
    "reuniao": "Reunião: mensagem principal, dados de apoio e próximo passo.",
    "palestra": "Palestra: abertura que prende, três ideias centrais e fechamento memorável.",
    "entrevista": "Entrevista: respostas diretas, exemplos pessoais e frases curtas.",
}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SubQuestions(_Strict):
    items: list[str] = Field(min_length=1)


class Claim(_Strict):
    text: str = Field(min_length=1)
    chunk_ids: list[str]
    strength: Literal["forte", "moderada", "fraca"]


class SynthesisDraft(_Strict):
    summary: str
    claims: list[Claim]
    conflicts: list[str]
    gaps: list[str]
    confidence: Literal["alta", "media", "baixa"]


class AudienceProfile(_Strict):
    audience: Audience = "leigo"
    context: Context = "palestra"
    minutes: float = Field(default=3, gt=0, le=60)
    tone: Tone = "neutro"


class AdaptationDraft(_Strict):
    adapted_text: str = Field(min_length=1)
    changes: list[str]
    rehearsal_tips: list[str]
