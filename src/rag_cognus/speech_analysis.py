"""Métricas da fala gravada: ritmo, pausas, vícios, clareza, dicção e fluxo de energia.

Tudo determinístico (spec 002): o LLM nunca inventa estes números. As faixas ficam em
constantes para calibrar com gravações reais.
"""

from __future__ import annotations

import re
import unicodedata

import numpy as np

from rag_cognus.agents.communication import text_metrics

PACE_RANGE = (120, 160)  # palavras por minuto confortáveis em apresentações em português
PAUSE_RANGE = (0.4, 2.0)  # segundos: pausa consciente
LONG_SILENCE = 3.0  # segundos: silêncio que quebra o fluxo
PAUSES_PER_MIN = (3, 8)
FILLER_WORDS = {"hã", "ã", "ah", "ahn", "hum", "humm", "hmm", "uhm", "mm", "tipo", "né"}
_ELONGATED_E = re.compile(r"^(?:[eé]{2,}h*|[eé]h+)$")  # éé, ééh, eh — "é" sozinho é verbo

PILLAR_NAMES = {
    "pace": "Ritmo & Cadência",
    "pauses": "Pausas Conscientes",
    "fillers": "Vícios Vocais",
    "clarity": "Clareza da Mensagem",
}


def _normalize(word: str) -> str:
    word = unicodedata.normalize("NFC", word.strip().lower())
    return re.sub(r"[^\wáéíóúâêôãõàç]", "", word)


def is_filler(word: str) -> bool:
    token = _normalize(word)
    return token in FILLER_WORDS or bool(_ELONGATED_E.match(token))


def _clamp(value: float) -> int:
    return int(round(min(100.0, max(0.0, value))))


def _pace(lexical: int, minutes: float) -> dict:
    ppm = lexical / minutes if minutes else 0.0
    low, high = PACE_RANGE
    distance = low - ppm if ppm < low else ppm - high if ppm > high else 0.0
    label = "lento" if ppm < low else "rapido" if ppm > high else "ideal"
    return {"value": round(ppm), "unit": "ppm", "score": _clamp(100 - 2 * distance), "label": label}


def _pauses(words: list[dict], minutes: float) -> dict:
    gaps = [b["start"] - a["end"] for a, b in zip(words, words[1:])]
    conscious = sum(PAUSE_RANGE[0] <= g <= PAUSE_RANGE[1] for g in gaps)
    long_silences = sum(g > LONG_SILENCE for g in gaps)
    per_min = conscious / minutes if minutes else 0.0
    low, high = PAUSES_PER_MIN
    score = 100.0
    if per_min < low:
        score -= 15 * (low - per_min)
    elif per_min > high:
        score -= 8 * (per_min - high)
    score -= 15 * long_silences
    label = "poucas" if per_min < low else "excessivas" if per_min > high else "equilibradas"
    return {
        "value": conscious,
        "unit": "pausas",
        "score": _clamp(score),
        "label": label,
        "per_minute": round(per_min, 1),
        "long_silences": long_silences,
    }


def _fillers(words: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for w in words:
        if is_filler(w["word"]):
            token = _normalize(w["word"])
            counts[token] = counts.get(token, 0) + 1
    rate = 100 * sum(counts.values()) / len(words)
    score = _clamp(100 - 5 * rate)
    label = "limpo" if score >= 90 else "atencao" if score >= 70 else "frequente"
    return {
        "value": round(100 - rate, 1),
        "unit": "% livre",
        "score": score,
        "label": label,
        "counts": counts,
    }


def _clarity(text: str, judge: int | None) -> dict:
    metrics = text_metrics(text)
    score = metrics["readability"]
    if judge is not None:
        score = (score + (judge - 1) * 25) / 2  # nota 1–5 do juiz → 0–100
    score = _clamp(score)
    label = "alto" if score >= 70 else "medio" if score >= 45 else "baixo"
    return {
        "value": label,
        "unit": "nível",
        "score": score,
        "label": label,
        "readability": metrics["readability"],
        "avg_sentence_words": metrics["avg_sentence_words"],
    }


def analyze_words(words: list[dict], clarity_judge: int | None = None) -> dict:
    """words: [{'word', 'start', 'end', 'probability'}] em ordem, com tempos em segundos."""
    if not words:
        raise ValueError("Não detectei fala na gravação. Fale mais perto do microfone.")
    minutes = max(words[-1]["end"] - words[0]["start"], 1.0) / 60
    lexical = sum(not is_filler(w["word"]) for w in words)
    text = " ".join(w["word"].strip() for w in words)
    pillars = {
        "pace": _pace(lexical, minutes),
        "pauses": _pauses(words, minutes),
        "fillers": _fillers(words),
        "clarity": _clarity(text, clarity_judge),
    }
    probabilities = [w.get("probability", 0.0) for w in words]
    return {
        "pillars": pillars,
        "index": round(sum(p["score"] for p in pillars.values()) / len(pillars)),
        "diction": _clamp(100 * sum(probabilities) / len(probabilities)),
        "speaking_seconds": round(minutes * 60, 1),
        "word_count": len(words),
        "text": text,
    }


def energy_contour(audio: np.ndarray, bins: int = 40) -> dict:
    """RMS por janela, normalizado 0–1, e estabilidade (coef. de variação das janelas com voz)."""
    if len(audio) < bins:
        return {"contour": [0.0] * bins, "stability": "variavel"}
    rms = np.array([float(np.sqrt(np.mean(c**2))) for c in np.array_split(audio, bins)])
    peak = rms.max() or 1.0
    contour = [round(v / peak, 3) for v in rms]
    voiced = rms[rms > 0.02 * peak]
    variation = float(voiced.std() / voiced.mean()) if len(voiced) else 1.0
    return {"contour": contour, "stability": "estavel" if variation < 0.35 else "variavel"}
