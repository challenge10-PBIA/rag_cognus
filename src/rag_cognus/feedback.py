"""Feedback guiado da sessão (spec 006): recomendações → sub-recomendações da Gold → exercícios.

Sem `chat`, tudo é determinístico e sem rede. O LLM (opcional) só redige sub-recomendações a
partir dos trechos recuperados e escolhe exercícios entre os ids recebidos; a saída é validada.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Callable

from rag_cognus.exercises import exercises_for
from rag_cognus.progress import CHALLENGES

DICTION_QUERY = "dicção articulação pronúncia clara das palavras"
PILLAR_THRESHOLD = 80
DICTION_THRESHOLD = 70
MAX_PILLARS = 3
MAX_OCCURRENCES = 2
MAX_RECOMMENDATIONS = 4
MAX_SUBS = 3
SEARCH_K = 3
SUB_TEXT_MAX = 200
EXCERPT_MAX = 240

PILLAR_LABELS = {
    "pace": "ritmo da fala",
    "pauses": "uso de pausas",
    "fillers": "fala limpa",
    "clarity": "clareza da mensagem",
    "diction": "dicção",
}
PILLAR_TEXTS = {
    "pace": "Ajuste a velocidade para o público acompanhar os pontos-chave.",
    "pauses": "Use pausas curtas para separar ideias e dar peso às conclusões.",
    "fillers": "Troque os vícios de linguagem por um silêncio curto e respire.",
    "clarity": "Organize a mensagem em frases curtas e diretas.",
    "diction": "Articule bem as sílabas finais para cada palavra chegar inteira.",
}
_SENTENCE_END = re.compile(r"(?<=[.!?])\s")
_THINK = re.compile(r"<think>.*?</think>", re.S)

SUBS_PROMPT = """Você orienta treinos de comunicação oral. Foco: {foco}.
Use SOMENTE os trechos abaixo. Escreva até 3 sub-recomendações práticas em português.
Cada uma cita o chunk_id de um trecho e um `excerpt` copiado literalmente dele.
Você pode reordenar os exercícios, escolhendo apenas entre estes ids: {ids}.
Responda só JSON: {{"subs": [{{"text": "...", "chunk_id": "...", "excerpt": "..."}}],
"exercises": ["id"]}}

Trechos:
{trechos}"""


def _score(analysis: dict, pillar: str) -> float:
    if pillar == "diction":
        return float(analysis.get("diction", 100))
    value = analysis["pillars"][pillar]
    return float(value["score"] if isinstance(value, dict) else value)


def _priority(score: float) -> str:
    return "alta" if score < 50 else "media" if score < 70 else "baixa"


def _occurrence_pillar(kind: str) -> str:
    return "clarity" if kind == "pleonasmo" else "fillers"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "termo"


def _targets(analysis: dict, occurrences: list[dict]) -> list[dict]:
    pillars = list(analysis["pillars"])
    if "diction" in analysis:
        pillars.append("diction")
    scores = {p: _score(analysis, p) for p in pillars}
    weak = [
        p
        for p in pillars
        if scores[p] < (DICTION_THRESHOLD if p == "diction" else PILLAR_THRESHOLD)
    ]
    weak.sort(key=lambda p: scores[p])  # sort estável: empate mantém a ordem dos pilares
    targets = [
        {"pillar": p, "kind": "pillar", "term": None, "score": scores[p]}
        for p in weak[:MAX_PILLARS]
    ]
    counts = Counter(o["term"] for o in occurrences)
    kinds: dict[str, str] = {}
    for o in occurrences:
        kinds.setdefault(o["term"], o["kind"])
    for term, count in counts.most_common():  # empate: ordem da primeira ocorrência
        if len(targets) >= MAX_RECOMMENDATIONS:
            break
        if sum(t["kind"] == "occurrence" for t in targets) >= MAX_OCCURRENCES:
            break
        pillar = _occurrence_pillar(kinds[term])
        targets.append(
            {
                "pillar": pillar,
                "kind": "occurrence",
                "term": term,
                "score": scores.get(pillar, 100.0),
                "count": count,
                "occurrence": next(o for o in occurrences if o["term"] == term),
            }
        )
    if not targets:
        lowest = min(pillars, key=lambda p: scores[p])
        targets.append({"pillar": lowest, "kind": "keep", "term": None, "score": scores[lowest]})
    return targets[:MAX_RECOMMENDATIONS]


def _title_text(target: dict) -> tuple[str, str]:
    pillar, term = target["pillar"], target["term"]
    label = PILLAR_LABELS.get(pillar, pillar)
    if target["kind"] == "keep":
        return f"Manter: {label}", f"Bom trabalho. Siga treinando {label} para não perder o nível."
    if target["kind"] == "pillar":
        return f"Melhore: {label}", PILLAR_TEXTS.get(pillar, "")
    vezes = "vez" if target["count"] == 1 else "vezes"
    suggestion = (target["occurrence"].get("suggestion") or "").strip()
    if pillar == "clarity":
        title = f"Evite o pleonasmo “{term}”"
        text = f"Apareceu {target['count']} {vezes}."
        return title, f"{text} Prefira: {suggestion}." if suggestion else text
    title = f"Reduza “{term}”"
    return title, f"Apareceu {target['count']} {vezes}. {PILLAR_TEXTS['fillers']}"


def _query(target: dict) -> str:
    pillar = target["pillar"]
    query = DICTION_QUERY if pillar == "diction" else CHALLENGES[pillar]["query"]
    return f"{query} {target['term']}" if target["kind"] == "occurrence" else query


def _chunk_id(doc) -> str:
    return str(getattr(doc, "id", None) or doc.metadata["chunk_id"])


def _source(doc) -> dict:
    meta = doc.metadata or {}
    return {
        "chunk_id": _chunk_id(doc),
        "title": meta.get("title"),
        "url": meta.get("source_url") or meta.get("url"),
    }


def _first_sentence(text: str) -> str:
    sentence = _SENTENCE_END.split(text.strip(), maxsplit=1)[0].strip()
    return sentence[:SUB_TEXT_MAX].rstrip()


def _deterministic_subs(docs: list) -> list[dict]:
    subs = []
    for doc in docs[:MAX_SUBS]:
        sentence = _first_sentence(doc.page_content)
        if sentence:
            subs.append({"text": sentence, "source": _source(doc), "excerpt": sentence})
    return subs


def _parse_llm(content: str):
    content = _THINK.sub("", content).strip()
    content = re.sub(r"^```(?:json)?|```$", "", content.strip()).strip()
    return json.loads(content)


def _llm_choice(chat, target: dict, docs: list, exercises: list[dict]):
    """Devolve (subs validadas, ids de exercício) ou ([], []) em qualquer erro."""
    trechos = "\n".join(f"[{_chunk_id(d)}] {d.page_content}" for d in docs)
    prompt = SUBS_PROMPT.format(
        foco=_title_text(target)[0],
        ids=", ".join(e["id"] for e in exercises) or "nenhum",
        trechos=trechos or "(nenhum)",
    )
    try:
        data = _parse_llm(chat.invoke([("human", prompt)]).content)
    except Exception:
        return [], []
    if not isinstance(data, (list, dict)):
        return [], []
    raw_subs = data if isinstance(data, list) else data.get("subs", [])
    ids = [] if isinstance(data, list) else data.get("exercises", [])
    by_id = {_chunk_id(d): d for d in docs}
    subs = []
    for item in raw_subs if isinstance(raw_subs, list) else []:
        if not isinstance(item, dict):
            continue
        text, cid, excerpt = item.get("text"), item.get("chunk_id"), item.get("excerpt")
        doc = by_id.get(cid) if isinstance(cid, str) else None
        if not (isinstance(text, str) and text.strip() and isinstance(excerpt, str)):
            continue
        excerpt = excerpt.strip()
        if doc is None or not excerpt or len(excerpt) > EXCERPT_MAX:
            continue
        if excerpt not in doc.page_content:
            continue
        subs.append({"text": text.strip(), "source": _source(doc), "excerpt": excerpt})
    ids = [i for i in ids if isinstance(i, str)] if isinstance(ids, list) else []
    return subs[:MAX_SUBS], ids


def _exercises(exercises_fn: Callable, pillar: str) -> list[dict]:
    try:
        return list(exercises_fn(pillar, limit=2))[:2]
    except Exception:
        return []  # catálogo ausente/inválido não derruba a sessão (AC-9)


def build_guided(
    analysis: dict,
    occurrences: list[dict],
    retriever,
    chat=None,
    exercises_fn: Callable[..., list[dict]] = exercises_for,
) -> list[dict]:
    """Recomendações guiadas da sessão (spec 006, AC-1 a AC-9)."""
    recommendations = []
    for target in _targets(analysis, occurrences or []):
        pillar = target["pillar"]
        title, text = _title_text(target)
        exercises = _exercises(exercises_fn, pillar)
        docs, available = [], retriever is not None
        if retriever is not None:
            try:
                docs = list(retriever.search(_query(target), k=SEARCH_K))[:SEARCH_K]
            except Exception:
                docs, available = [], False  # GoldUnavailable e afins (AC-7)
        subs = []
        if chat is not None and docs:
            subs, chosen = _llm_choice(chat, target, docs, exercises)
            known = {e["id"]: e for e in exercises}
            picked = [known[i] for i in dict.fromkeys(chosen) if i in known]
            exercises = picked or exercises
        if not subs:
            subs = _deterministic_subs(docs)
        rid = f"{pillar}-{_slug(target['term'])}" if target["term"] else pillar
        recommendations.append(
            {
                "id": rid,
                "pillar": pillar,
                "target": {
                    "kind": "occurrence" if target["kind"] == "occurrence" else "pillar",
                    "term": target["term"],
                },
                "title": title,
                "text": text,
                "priority": _priority(target["score"]),
                "subs": subs,
                "exercises": exercises,
                "sources_available": available,
                "pillar_score": round(target["score"]),  # spec 008 AC-8
                "maintain": target["kind"] == "keep",
            }
        )
    return recommendations
