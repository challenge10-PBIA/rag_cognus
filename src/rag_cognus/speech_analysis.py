"""Métricas da fala gravada: ritmo, pausas, vícios, clareza, dicção e fluxo de energia.

Tudo determinístico (spec 002): o LLM nunca inventa estes números. As faixas ficam em
constantes para calibrar com gravações reais.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable

import numpy as np

from rag_cognus.agents.communication import text_metrics
from rag_cognus.retrieval import STOP_WORDS

PACE_RANGE = (120, 160)  # palavras por minuto confortáveis em apresentações em português
PAUSE_RANGE = (0.4, 2.0)  # segundos: pausa consciente
LONG_SILENCE = 3.0  # segundos: silêncio que quebra o fluxo
PAUSES_PER_MIN = (3, 8)
FILLER_WORDS = {"hã", "ã", "ah", "ahn", "hum", "humm", "hmm", "uhm", "mm", "tipo", "né"}
_ELONGATED_E = re.compile(r"^(?:[eé]{2,}h*|[eé]h+)$")  # éé, ééh, eh — "é" sozinho é verbo

# Spec 003: vícios detectados pela própria fala e pleonasmos (calibrar com gravações reais).
VICE_MIN_PER_MIN = 2.0  # ocorrências por minuto de fala para virar vício
VICE_MIN_COUNT = 3  # contagem absoluta mínima (fala curta)
VICE_MAX_NGRAM = 3
VICE_BOUNDARY_GAP = 0.25  # s de silêncio que marca fronteira de enunciado
VICE_BOUNDARY_RATIO = 0.6  # fração mínima de ocorrências em fronteira (fora das sementes)
DISCOURSE_MARKERS = {
    "então",
    "basicamente",
    "tipo assim",
    "na verdade",
    "entendeu",
    "sabe",
    "tá",
    "beleza",
    "enfim",
    "aí",
    "literalmente",
    "meio que",
    "vamos dizer assim",
}
VICE_STOPWORDS = STOP_WORDS | {
    "eu", "tu", "ele", "ela", "nós", "eles", "elas", "você", "vocês", "me", "te", "lhe",
    "nos", "o", "a", "é", "foi", "era", "são", "está", "estava", "tem", "tinha", "há",
    "mas", "não", "já", "mais", "muito", "também", "quando", "onde", "porque", "aqui", "lá",
    "este", "esta", "pelo", "pela", "pelos", "pelas", "num", "numa", "pra", "pro", "pras",
    "pros", "até", "entre", "sem", "nem", "mesmo", "seu", "sua", "meu", "minha",
}  # fmt: skip
FIXED_SUGGESTION = "Troque por um silêncio curto e respire."
_PRA = r"(?:pra|para|pro)"
_TIME = r"(?:anos?|mes|meses|dias?|semanas?|horas?|minutos?|decadas?|seculos?)"
# `padrao` casa sobre as palavras normalizadas sem acento, separadas por espaço; o grupo
# `keep` (quando existe) vira a sugestão com as palavras literais da fala.
PLEONASMS = [
    {"padrao": rf"(?P<keep>sub\w*|sobe\w*) {_PRA} cima", "termo": "subir pra cima",
     "sugestao": "subir"},
    {"padrao": rf"(?P<keep>desc\w*) {_PRA} baixo", "termo": "descer pra baixo",
     "sugestao": "descer"},
    {"padrao": r"(?P<keep>elos?) de ligacao", "termo": "elo de ligação", "sugestao": "elo"},
    {"padrao": r"(?P<keep>surpresas?) inesperadas?", "termo": "surpresa inesperada",
     "sugestao": "surpresa"},
    {"padrao": rf"(?P<keep>ha(?: \w+)? {_TIME}) atras", "termo": "há … anos atrás",
     "sugestao": "há … anos"},
    {"padrao": r"(?P<keep>encar\w*) de frente", "termo": "encarar de frente",
     "sugestao": "encarar"},
    {"padrao": rf"(?P<keep>entr\w*) {_PRA} dentro", "termo": "entrar pra dentro",
     "sugestao": "entrar"},
    {"padrao": rf"(?P<keep>sa[ie]\w*) {_PRA} fora", "termo": "sair pra fora",
     "sugestao": "sair"},
    {"padrao": r"(?P<keep>repet\w*) de novo", "termo": "repetir de novo", "sugestao": "repetir"},
    {"padrao": r"(?P<keep>planej\w*) antecipadamente", "termo": "planejar antecipadamente",
     "sugestao": "planejar"},
    {"padrao": r"(?P<keep>fatos?) rea(?:l|is)", "termo": "fato real", "sugestao": "fato"},
    {"padrao": r"(?P<keep>consensos?) gera(?:l|is)", "termo": "consenso geral",
     "sugestao": "consenso"},
]  # fmt: skip

PleonasmChecker = Callable[[str, list[dict]], dict]

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


def _fold(word: str) -> str:
    """Normaliza e remove acentos: comparação de n-gramas e pleonasmos."""
    decomposed = unicodedata.normalize("NFKD", _normalize(word))
    return "".join(c for c in decomposed if not unicodedata.combining(c))


_SEEDS = {" ".join(_fold(w) for w in m.split()): m for m in DISCOURSE_MARKERS}
_FOLDED_STOPWORDS = {_fold(w) for w in VICE_STOPWORDS}


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


def _fillers(words: list[dict], occurrences: list[dict]) -> dict:
    counts: dict[str, int] = {}
    vice_words = 0
    for o in occurrences:
        if o["kind"] != "pleonasmo":
            counts[o["term"]] = counts.get(o["term"], 0) + 1
            vice_words += o["_size"]
    pleonasms = sum(o["kind"] == "pleonasmo" for o in occurrences)
    rate = 100 * vice_words / len(words)
    score = _clamp(100 - 5 * rate - min(15, 3 * pleonasms))
    label = "limpo" if score >= 90 else "atencao" if score >= 70 else "frequente"
    return {
        "value": round(100 - rate, 1),
        "unit": "% livre",
        "score": score,
        "label": label,
        "counts": counts,
        "pleonasms": pleonasms,
    }


def _occurrence(words, i, j, term, kind, source, suggestion) -> dict:
    """Palavras i..j (inclusive); trecho copiado da transcrição (AC-8)."""
    excerpt = " ".join(w["word"].strip() for w in words[max(0, i - 4) : j + 5])
    return {
        "term": term,
        "kind": kind,
        "excerpt": excerpt,
        "start": words[i]["start"],
        "end": words[j]["end"],
        "suggestion": suggestion,
        "source": source,
        "confirmed_by_llm": None,
        "_first": i,
        "_size": j - i + 1,
    }


def _vices(words: list[dict], tokens: list[str], minutes: float) -> list[dict]:
    """Vício fixo (is_filler) e detectado (n-grama repetido); o maior n-grama vence (AC-5)."""
    idx = [i for i, t in enumerate(tokens) if t]
    gap = VICE_BOUNDARY_GAP

    def silence_before(p: int) -> bool:
        return p == 0 or words[idx[p]]["start"] - words[idx[p - 1]]["end"] >= gap

    def silence_after(p: int) -> bool:
        return p == len(idx) - 1 or words[idx[p + 1]]["start"] - words[idx[p]]["end"] >= gap

    positions: dict[tuple[str, ...], list[int]] = {}
    for n in range(1, VICE_MAX_NGRAM + 1):
        for p in range(len(idx) - n + 1):
            if any(silence_before(q) for q in range(p + 1, p + n)):
                continue  # n-grama não atravessa pausa
            positions.setdefault(tuple(tokens[i] for i in idx[p : p + n]), []).append(p)

    def frequent(gram, found) -> bool:
        return len(found) >= VICE_MIN_COUNT and len(found) / minutes >= VICE_MIN_PER_MIN

    seeds = {g for g, f in positions.items() if " ".join(g) in _SEEDS and frequent(g, f)}
    detected = set(seeds)
    for gram, found in positions.items():
        if gram in seeds or not frequent(gram, found):
            continue
        if all(t in _FOLDED_STOPWORDS for t in gram) or any(c.isdigit() for t in gram for c in t):
            continue
        if len(gram) == 1 and (len(gram[0]) <= 2 or is_filler(gram[0])):
            continue
        if any(_contains(gram, seed) for seed in seeds):
            continue  # a semente já explica a repetição
        edges = sum(silence_before(p) or silence_after(p + len(gram) - 1) for p in found)
        if edges / len(found) >= VICE_BOUNDARY_RATIO:
            detected.add(gram)

    taken: set[int] = set()
    out = []
    for gram in sorted(detected, key=len, reverse=True):
        for p in positions[gram]:
            span = idx[p : p + len(gram)]
            if taken.intersection(span):
                continue
            taken.update(span)
            head = positions[gram][0]
            term = _SEEDS.get(" ".join(gram)) or " ".join(
                _normalize(words[i]["word"]) for i in idx[head : head + len(gram)]
            )
            suggestion = f"Evite repetir “{term}”: faça uma pausa curta no lugar."
            out.append(
                _occurrence(
                    words, span[0], span[-1], term, "vicio_detectado", "estatistica", suggestion
                )
            )
    for i, w in enumerate(words):
        if i not in taken and is_filler(w["word"]):
            term = _normalize(w["word"])
            out.append(_occurrence(words, i, i, term, "vicio_fixo", "lexico", FIXED_SUGGESTION))
    return out


def _contains(gram: tuple[str, ...], part: tuple[str, ...]) -> bool:
    n = len(part)
    return len(gram) > n and any(gram[k : k + n] == part for k in range(len(gram) - n + 1))


def _folded_text(tokens: list[str]) -> tuple[str, list[int], list[int]]:
    """Texto sem acento e, por palavra não vazia, offset inicial e índice original."""
    text, offsets, owners = "", [], []
    for i, t in enumerate(tokens):
        if t:
            text += (" " if text else "") + t
            offsets.append(len(text) - len(t))
            owners.append(i)
    return text, offsets, owners


def _span(offsets: list[int], owners: list[int], start: int, end: int) -> tuple[int, int]:
    first = offsets.index(start)
    last = max(k for k, o in enumerate(offsets) if o < end)
    return owners[first], owners[last]


def _literal(words: list[dict], i: int, j: int) -> str:
    return " ".join(w["word"].strip() for w in words[i : j + 1])


def _pleonasms(words: list[dict], tokens: list[str]) -> list[dict]:
    text, offsets, owners = _folded_text(tokens)
    out = []
    for entry in PLEONASMS:
        for m in re.finditer(rf"(?<!\S){entry['padrao']}(?!\S)", text):
            i, j = _span(offsets, owners, m.start(), m.end())
            suggestion = entry["sugestao"]
            if "keep" in m.groupdict() and m.group("keep"):
                ki, kj = _span(offsets, owners, m.start("keep"), m.end("keep"))
                suggestion = _literal(words, ki, kj).rstrip(",.;:!?")
            out.append(
                _occurrence(words, i, j, _literal(words, i, j), "pleonasmo", "lexico", suggestion)
            )
    return out


def _valid_check(answer) -> bool:
    if not isinstance(answer, dict):
        return False
    confirmed, suggested = answer.get("confirmed", []), answer.get("suggested", [])
    return (
        isinstance(confirmed, list)
        and all(isinstance(k, int) and not isinstance(k, bool) for k in confirmed)
        and isinstance(suggested, list)
        and all(
            isinstance(s, dict)
            and isinstance(s.get("trecho"), str)
            and isinstance(s.get("sugestao"), str)
            and s["sugestao"].strip()
            for s in suggested
        )
    )


def _check_pleonasms(
    words: list[dict], tokens: list[str], text: str, found: list[dict], checker
) -> list[dict]:
    """Checker LLM opcional (AC-9…AC-12): só confirma ou aponta trechos literais da fala."""
    candidates = [{k: v for k, v in o.items() if not k.startswith("_")} for o in found]
    try:
        answer = checker(text, candidates)
    except Exception:
        return found
    if not _valid_check(answer):
        return found
    confirmed = set(answer.get("confirmed", []))
    checked = [dict(o, confirmed_by_llm=k in confirmed) for k, o in enumerate(found)]
    used = {i for o in checked for i in range(o["_first"], o["_first"] + o["_size"])}
    for item in answer.get("suggested", []):
        target = [_fold(w) for w in item["trecho"].split()]
        target = [t for t in target if t]
        n = len(target)
        for i in range(len(tokens) - n + 1) if n else ():
            if tokens[i : i + n] == target:
                if not used.intersection(range(i, i + n)):
                    used.update(range(i, i + n))
                    occ = _occurrence(
                        words, i, i + n - 1, _literal(words, i, i + n - 1), "pleonasmo",
                        "llm", item["sugestao"].strip(),
                    )  # fmt: skip
                    checked.append(dict(occ, confirmed_by_llm=True))
                break
    return checked


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


def analyze_words(
    words: list[dict],
    clarity_judge: int | None = None,
    pleonasm_checker: PleonasmChecker | None = None,
) -> dict:
    """words: [{'word', 'start', 'end', 'probability'}] em ordem, com tempos em segundos.

    `pleonasm_checker` (opcional, desligado por padrão) recebe o texto e os pleonasmos do
    léxico e devolve {"confirmed": [int], "suggested": [{"trecho", "sugestao"}]}.
    """
    if not words:
        raise ValueError("Não detectei fala na gravação. Fale mais perto do microfone.")
    minutes = max(words[-1]["end"] - words[0]["start"], 1.0) / 60
    lexical = sum(not is_filler(w["word"]) for w in words)
    text = " ".join(w["word"].strip() for w in words)
    tokens = [_fold(w["word"]) for w in words]
    pleonasms = _pleonasms(words, tokens)
    if pleonasm_checker is not None:
        pleonasms = _check_pleonasms(words, tokens, text, pleonasms, pleonasm_checker)
    occurrences = sorted(
        _vices(words, tokens, minutes) + pleonasms, key=lambda o: (o["start"], o["_first"])
    )
    word_kinds: list[str | None] = [None] * len(words)
    for o in sorted(occurrences, key=lambda o: o["kind"] != "pleonasmo"):  # vício prevalece
        for i in range(o["_first"], o["_first"] + o["_size"]):
            word_kinds[i] = o["kind"]
    pillars = {
        "pace": _pace(lexical, minutes),
        "pauses": _pauses(words, minutes),
        "fillers": _fillers(words, occurrences),
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
        "occurrences": [{k: v for k, v in o.items() if not k.startswith("_")} for o in occurrences],
        "word_kinds": word_kinds,
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
