"""Contrato editorial de exercícios fonéticos vindo da Gold, sem inferência clínica."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from langchain_core.documents import Document
from pydantic import BaseModel, Field, HttpUrl, model_validator

CONTRACT_VERSION = "2026-11-18.v2"

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
AnimationKey = Literal[
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
    "none",
]
ContactRegion = Literal[
    "none",
    "bilabial",
    "labiodental",
    "dental_alveolar",
    "alveolar",
    "postalveolar",
    "palatal",
    "velar_uvular",
    "glottal",
]
AirflowKind = Literal[
    "none",
    "oral_central",
    "oral_lateral",
    "nasal",
    "fricative_constriction",
    "closure_hold",
]
ArticulationGesture = Literal[
    "neutral_prep",
    "alveolar_tap",
    "alveolar_lateral_hold",
    "posterior_fricative",
    "alveolar_trill_variant",
    "palatal_lateral_arch",
    "palatal_nasal_arch",
    "postalveolar_fricative",
    "bilabial_closure",
    "labiodental_constriction",
    "velar_closure",
    "release_vowel",
]
VoicingState = Literal["voiced", "voiceless", "variable"]
VelumState = Literal["raised", "lowered"]
MULTI_GESTURE_PROFILES = {
    "fricatives_postalveolar",
    "cluster_r",
    "cluster_l",
    "contrast_r_l",
    "mixed_diction",
}


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


class TargetSequenceItem(BaseModel):
    word: str = Field(min_length=1)
    ipa: str = Field(min_length=1)
    focus: str = Field(min_length=1)


class RegionalVariantSpec(BaseModel):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    ipa: str = Field(min_length=1)
    description: str = Field(min_length=1)
    contactRegion: ContactRegion
    gesture: ArticulationGesture
    airflow: AirflowKind


class ArticulationStageSpec(BaseModel):
    index: int = Field(ge=0, le=10)
    title: str = Field(min_length=1)
    shortLabel: str = Field(min_length=1)
    caption: str = Field(min_length=1)
    segmentLabel: str = Field(min_length=1)
    targetWord: str = Field(min_length=1)
    durationMs: int = Field(ge=400, le=10000)
    gesture: ArticulationGesture
    contactRegion: ContactRegion
    airflow: AirflowKind
    velum: VelumState
    voicingState: VoicingState


class ArticulationDemonstration(BaseModel):
    schemaVersion: Literal[2]
    contractVersion: Literal["2026-11-18.v2"]
    profileId: PhonemeId
    summary: str = Field(min_length=1)
    targetSequence: list[TargetSequenceItem] = Field(min_length=1)
    regionalVariants: list[RegionalVariantSpec] = Field(default_factory=list)
    stages: list[ArticulationStageSpec] = Field(min_length=3)

    @model_validator(mode="after")
    def validate_profile_rules(self):
        for idx, stage in enumerate(self.stages):
            if stage.index != idx:
                raise ValueError("Índice de etapa da demonstração fora de sequência.")
        gestures = {s.gesture for s in self.stages}
        airflows = {s.airflow for s in self.stages}
        regions = {s.contactRegion for s in self.stages}
        voicings = {s.voicingState for s in self.stages}
        pid = self.profileId

        if pid == "r_tap" and "alveolar_tap" not in gestures:
            raise ValueError("Perfil r_tap exige gesto alveolar_tap.")
        if pid == "l_lateral" and (
            "alveolar_lateral_hold" not in gestures or "oral_lateral" not in airflows
        ):
            raise ValueError("Perfil l_lateral exige contato sustentado e fluxo oral_lateral.")
        if pid == "lh_palatal" and (
            "palatal_lateral_arch" not in gestures
            or "oral_lateral" not in airflows
            or "palatal" not in regions
        ):
            raise ValueError("Perfil lh_palatal exige gesto palatal_lateral_arch e fluxo lateral.")
        if pid == "nh_nasal" and (
            "palatal_nasal_arch" not in gestures
            or "nasal" not in airflows
            or not any(s.velum == "lowered" for s in self.stages)
        ):
            raise ValueError("Perfil nh_nasal exige elevação palatal, véu abaixado e fluxo nasal.")
        if pid == "fricatives_postalveolar" and (
            "postalveolar_fricative" not in gestures
            or not {"voiced", "voiceless"}.issubset(voicings)
        ):
            raise ValueError("Perfil fricatives_postalveolar exige contraste surdo e sonoro.")
        if pid == "cluster_r" and not (
            "alveolar_tap" in gestures
            and bool(gestures & {"bilabial_closure", "labiodental_constriction", "velar_closure"})
        ):
            raise ValueError(
                "Perfil cluster_r exige sequência de consoante inicial + tepe alveolar."
            )
        if pid == "cluster_l" and not (
            "alveolar_lateral_hold" in gestures
            and bool(gestures & {"bilabial_closure", "labiodental_constriction", "velar_closure"})
        ):
            raise ValueError(
                "Perfil cluster_l exige sequência de consoante inicial + lateral alveolar."
            )
        if pid == "contrast_r_l" and not {"alveolar_tap", "alveolar_lateral_hold"}.issubset(
            gestures
        ):
            raise ValueError(
                "Perfil contrast_r_l exige alternância explícita entre tepe e lateral."
            )
        if pid == "mixed_diction" and len(gestures - {"neutral_prep", "release_vowel"}) < 3:
            raise ValueError(
                "Perfil mixed_diction exige ao menos três gestos consonantais distintos."
            )
        if pid == "r_strong" and len(self.regionalVariants) < 2:
            raise ValueError("Perfil r_strong exige variantes regionais explícitas.")
        if pid in MULTI_GESTURE_PROFILES and len(self.stages) < 4:
            raise ValueError("Perfis sequenciais ou de contraste exigem ao menos 4 etapas.")
        return self


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
    demonstration: ArticulationDemonstration | None = None
    steps: list[PhoneticStep] = Field(min_length=1)
    commonMistakes: list[str] = Field(min_length=1)
    selfCheck: list[str] = Field(min_length=1)
    reviewStatus: Literal["educational_review_required", "reviewed"]
    sources: list[PhoneticSource] = Field(min_length=1)

    @model_validator(mode="after")
    def consistent_target(self):
        if self.animationKey not in {self.phonemeId, "none"}:
            raise ValueError("Animação incompatível com o alvo fonético.")
        if self.animationKey == "none":
            if self.demonstration is not None:
                raise ValueError("Exercício com animationKey=none não deve ter demonstration.")
        else:
            if self.demonstration is None:
                raise ValueError("Contrato demonstration obrigatório para animationKey ativa.")
            if self.demonstration.profileId != self.phonemeId:
                raise ValueError("profileId da demonstração incompatível com phonemeId.")
        expected = {"r_tap": "/ɾ/", "l_lateral": "/l/", "lh_palatal": "/ʎ/", "nh_nasal": "/ɲ/"}
        if self.phonemeId in expected and self.ipa != expected[self.phonemeId]:
            raise ValueError("Símbolo IPA incompatível com o alvo fonético.")
        return self


class PhoneticCatalog(BaseModel):
    schemaVersion: Literal[1] = 1
    contractVersion: str = CONTRACT_VERSION
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
