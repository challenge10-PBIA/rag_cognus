"""Contrato editorial de exercícios fonéticos vindo da Gold, sem inferência clínica."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from langchain_core.documents import Document
from pydantic import BaseModel, Field, HttpUrl, model_validator

PhonemeId = Literal[
    "r_tap",
    "l_lateral",
    "r_strong",
    "lh_palatal",
    "nh_nasal",
    "fricatives_postalveolar",
    "cluster_r",
    "cluster_l",
    "contrast_r_l",
    "mixed_diction",
]
AnimationKey = Literal["r_tap", "l_lateral", "r_strong", "lh_palatal", "nh_nasal", "none"]


class PhoneticStep(BaseModel):
    title: str = Field(min_length=1)
    instruction: str = Field(min_length=1)
    repetitions: int = Field(ge=1, le=100)
    durationSeconds: int | None = Field(default=None, ge=1, le=600)


class PhoneticSource(BaseModel):
    title: str = Field(min_length=1)
    url: HttpUrl
    scope: str | None = None
    chunk_id: str | None = None


class MinimalPair(BaseModel):
    pair: tuple[str, str]
    contrast: str


class PhoneticExercise(BaseModel):
    schemaVersion: Literal[1]
    id: str = Field(min_length=1)
    phonemeId: PhonemeId
    title: str = Field(min_length=1)
    phoneme: str = Field(min_length=1)
    ipa: str = Field(min_length=1)
    category: Literal[
        "vibrantes", "palatais", "fricativas", "encontros", "pares_minimos", "trava_linguas"
    ]
    categoryLabel: str
    articulationPoint: str = Field(min_length=1)
    articulationMode: str = Field(min_length=1)
    voicing: str
    acquisitionAge: str | None = None
    clinicalTip: str = Field(min_length=1)
    targetWords: list[str] = Field(min_length=1)
    practicePhrases: list[str] = Field(min_length=1)
    minimalPairs: list[MinimalPair] = Field(default_factory=list)
    recommendedMode: Literal["daily_pitch", "reuniao_1_1", "apresentacao_tecnica", "espontanea"]
    animationKey: AnimationKey
    steps: list[PhoneticStep] = Field(min_length=1)
    commonMistakes: list[str] = Field(min_length=1)
    selfCheck: list[str] = Field(min_length=1)
    reviewStatus: Literal["educational_review_required", "reviewed"]
    sources: list[PhoneticSource] = Field(min_length=1)

    @model_validator(mode="after")
    def consistent_target(self):
        if self.animationKey not in {self.phonemeId, "none"}:
            raise ValueError("Animação incompatível com o alvo fonético.")
        expected = {"r_tap": "/ɾ/", "l_lateral": "/l/", "lh_palatal": "/ʎ/", "nh_nasal": "/ɲ/"}
        if self.phonemeId in expected and self.ipa != expected[self.phonemeId]:
            raise ValueError("Símbolo IPA incompatível com o alvo fonético.")
        return self


class PhoneticCatalog(BaseModel):
    schemaVersion: Literal[1] = 1
    exercises: list[PhoneticExercise]


def catalog_from_documents(documents: Iterable[Document]) -> PhoneticCatalog:
    items, seen = [], set()
    for doc in documents:
        if doc.metadata.get("document_type") != "phonetic_exercise":
            raise ValueError("Snapshot fonético contém documento de outro tipo.")
        item = PhoneticExercise.model_validate(doc.metadata.get("exercise"))
        if item.id in seen:
            raise ValueError("Catálogo fonético contém ID de exercício duplicado.")
        seen.add(item.id)
        items.append(item)
    if not items:
        raise ValueError("Catálogo fonético vazio.")
    return PhoneticCatalog(exercises=items)
