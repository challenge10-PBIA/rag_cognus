"""Progresso do usuário a partir das sessões salvas: streak, meta, períodos, conquistas, desafios.

Funções puras sobre registros de sessão:
{'created_at': iso, 'duration_seconds', 'index', 'pillars': {nome: nota}, 'challenge_id',
 'anxiety_before', 'anxiety_after'} — ansiedade é autoavaliação 1–5, nunca medida.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

WEEKDAYS = ["SEG", "TER", "QUA", "QUI", "SEX", "SÁB", "DOM"]
PERIODS = {"week": (7, 1), "month": (4, 7), "quarter": (12, 7)}  # (barras, dias por barra)
LEVELS = [
    (90, 5, "Mestre"),
    (80, 4, "Avançado"),
    (65, 3, "Intermediário"),
    (50, 2, "Em evolução"),
    (0, 1, "Iniciante"),
]
PILLARS = ("pace", "pauses", "fillers", "clarity")

CHALLENGES = {
    "pace": {
        "title": "Aquecimento Vocal & Ritmo",
        "description": "Respiração diafragmática, pausas conscientes e projeção.",
        "minutes": 3,
        "mode": "espontanea",
        "query": "ritmo de fala respiração diafragmática aquecimento vocal",
    },
    "pauses": {
        "title": "Pausas Estratégicas",
        "description": "Faça uma pausa de 1 segundo a cada mudança de tópico.",
        "minutes": 3,
        "mode": "daily_pitch",
        "query": "pausas na fala apresentação ênfase",
    },
    "fillers": {
        "title": "Fala Sem Vícios",
        "description": "Troque “tipo” e “ééé” por um silêncio curto e respire.",
        "minutes": 3,
        "mode": "espontanea",
        "query": "vícios de linguagem hesitação fluência",
    },
    "clarity": {
        "title": "Simulação de Alinhamento Técnico",
        "description": "Treine respostas assertivas para perguntas de arquitetura e prazos.",
        "minutes": 5,
        "mode": "apresentacao_tecnica",
        "query": "clareza linguagem objetiva estrutura da mensagem",
    },
}
GUIDANCE = {
    "pace": (
        "FOCO: RITMO",
        "Desaceleração do Pacing",
        "Fale um pouco mais devagar nos pontos-chave para o público acompanhar.",
    ),
    "pauses": (
        "FOCO: PAUSAS",
        "Pausas que Dão Peso à Mensagem",
        "Pausar antes de um número ou conclusão reforça o impacto no ouvinte.",
    ),
    "fillers": (
        "FOCO: FLUÊNCIA",
        "Silêncio no Lugar dos Vícios",
        "Quando sentir o “éé” chegando, feche a boca e respire: o silêncio soa seguro.",
    ),
    "clarity": (
        "FOCO: CLAREZA",
        "Uma Ideia por Frase",
        "Frases curtas e conclusão primeiro deixam a mensagem fácil de seguir.",
    ),
}


def _day(record: dict) -> date:
    return datetime.fromisoformat(record["created_at"]).date()


def _mean(values) -> float | None:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _calm(record: dict) -> float | None:
    after = record.get("anxiety_after")
    return None if after is None else (5 - after) / 4 * 100


def streak(sessions: list[dict], today: date) -> int:
    days = {_day(s) for s in sessions}
    current = today if today in days else today - timedelta(days=1)
    count = 0
    while current in days:
        count += 1
        current -= timedelta(days=1)
    return count


def longest_streak(sessions: list[dict]) -> int:
    days = sorted({_day(s) for s in sessions})
    best = run = 0
    for i, day in enumerate(days):
        run = run + 1 if i and day - days[i - 1] == timedelta(days=1) else 1
        best = max(best, run)
    return best


def daily_goal(sessions: list[dict], today: date, goal_minutes: int) -> dict:
    minutes = sum(s["duration_seconds"] for s in sessions if _day(s) == today) / 60
    percent = min(100, round(100 * minutes / goal_minutes)) if goal_minutes else 0
    return {"minutes_today": round(minutes, 1), "goal_minutes": goal_minutes, "percent": percent}


def level(index: float | None) -> dict:
    for threshold, number, name in LEVELS:
        if index is not None and index >= threshold:
            return {"number": number, "name": name}
    return {"number": 1, "name": "Iniciante"}


def pillar_means(sessions: list[dict]) -> dict:
    return {p: _mean(s["pillars"].get(p) for s in sessions) for p in PILLARS}


def summary(sessions: list[dict], period: str, today: date) -> dict:
    if period not in PERIODS:
        raise ValueError("Período deve ser week, month ou quarter.")
    count, size = PERIODS[period]
    span = count * size
    start = today - timedelta(days=span - 1)
    bars = []
    for i in range(count):
        first = start + timedelta(days=i * size)
        bucket = [s for s in sessions if first <= _day(s) < first + timedelta(days=size)]
        bars.append(
            {
                "label": WEEKDAYS[first.weekday()] if size == 1 else first.strftime("%d/%m"),
                "minutes": round(sum(s["duration_seconds"] for s in bucket) / 60, 1),
                "index": _round(_mean(s["index"] for s in bucket)),
                "calm": _round(_mean(_calm(s) for s in bucket)),
            }
        )
    current = [s for s in sessions if start <= _day(s) <= today]
    previous = [s for s in sessions if start - timedelta(days=span) <= _day(s) < start]
    index, before = _mean(s["index"] for s in current), _mean(s["index"] for s in previous)
    anxious = [s for s in current if s.get("anxiety_before") and s.get("anxiety_after")]
    anx_before = _mean(s["anxiety_before"] for s in anxious)
    anx_after = _mean(s["anxiety_after"] for s in anxious)
    return {
        "period": period,
        "bars": bars,
        "index": _round(index),
        "index_change_pct": _pct(index, before),
        "level": level(index),
        "sessions": len(current),
        "avg_daily_minutes": round(sum(s["duration_seconds"] for s in current) / 60 / span, 1),
        "anxiety_change_pct": _pct(anx_after, anx_before),
        "pillars": {k: _round(v) for k, v in pillar_means(current).items()},
    }


def _round(value: float | None) -> int | None:
    return None if value is None else round(value)


def _pct(now: float | None, before: float | None) -> float | None:
    return None if now is None or not before else round(100 * (now - before) / before, 1)


def weakest_pillars(sessions: list[dict]) -> list[str]:
    """Pilares do mais fraco ao mais forte nas últimas 5 sessões (padrão sem histórico)."""
    recent = sorted(sessions, key=lambda s: s["created_at"])[-5:]
    means = pillar_means(recent)
    if all(v is None for v in means.values()):
        return ["pace", "clarity", "fillers", "pauses"]
    return sorted(PILLARS, key=lambda p: means[p] if means[p] is not None else 101)


def challenges(sessions: list[dict], today: date, limit: int = 3) -> list[dict]:
    # A lista do dia usa só sessões até ontem: cumprir um desafio não o tira da tela.
    done_today = {s.get("challenge_id") for s in sessions if _day(s) == today}
    before_today = [s for s in sessions if _day(s) < today]
    items = []
    for pillar, priority in zip(weakest_pillars(before_today), ["alta", "media", "baixa"]):
        item = {k: v for k, v in CHALLENGES[pillar].items() if k != "query"}
        items.append(
            {
                "id": pillar,
                "pillar": pillar,
                "priority": priority,
                "done": pillar in done_today,
                **item,
            }
        )
    return items[:limit]


def guidance(sessions: list[dict], limit: int = 2) -> list[dict]:
    items = []
    for pillar in weakest_pillars(sessions)[:limit]:
        focus, title, description = GUIDANCE[pillar]
        challenge = CHALLENGES[pillar]
        items.append(
            {
                "pillar": pillar,
                "focus": focus,
                "title": title,
                "description": description,
                "minutes": challenge["minutes"],
                "mode": challenge["mode"],
                "query": challenge["query"],
            }
        )
    return items


def achievements(sessions: list[dict], today: date) -> list[dict]:
    ideal_pace = sum(s["pillars"].get("pace", 0) >= 100 for s in sessions)
    clean = any(
        s["pillars"].get("fillers", 0) >= 95 and s["pillars"].get("pauses", 0) >= 85
        for s in sessions
    )
    current = streak(sessions, today)
    return [
        {
            "id": "first_session",
            "title": "Primeira Sessão",
            "badge": "INÍCIO",
            "description": "Você gravou sua primeira prática.",
            "unlocked": bool(sessions),
        },
        {
            "id": "streak_7",
            "title": "Streak de 7 Dias de Prática",
            "badge": "ATIVO" if current >= 7 else f"{min(current, 7)}/7",
            "description": "Consistência diária para calibrar o tom e o ritmo.",
            "unlocked": longest_streak(sessions) >= 7,
        },
        {
            "id": "concise",
            "title": "Mestre da Concisão",
            "badge": f"{min(ideal_pace, 3)}/3",
            "description": "Três sessões com ritmo na faixa ideal.",
            "unlocked": ideal_pace >= 3,
        },
        {
            "id": "pauses_master",
            "title": "Domínio de Pausas Estratégicas",
            "badge": "0 VÍCIOS",
            "description": "Pausas equilibradas e fala sem vícios na mesma sessão.",
            "unlocked": clean,
        },
    ]
