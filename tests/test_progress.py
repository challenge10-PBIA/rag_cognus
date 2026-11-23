from datetime import date, datetime, timedelta

import pytest

from rag_cognus import progress

TODAY = date(2026, 11, 16)  # segunda-feira


def session(days_ago=0, minutes=3.0, index=80, pillars=None, challenge_id=None, **extra):
    when = datetime.combine(TODAY - timedelta(days=days_ago), datetime.min.time()).replace(hour=9)
    return {
        "id": f"s{days_ago}-{index}",
        "created_at": when.isoformat(),
        "mode": "daily_pitch",
        "duration_seconds": minutes * 60,
        "index": index,
        "pillars": pillars or {"pace": 80, "pauses": 80, "fillers": 80, "clarity": 80},
        "challenge_id": challenge_id,
        **extra,
    }


def test_streak_counts_consecutive_days():  # AC-6
    assert progress.streak([session(0), session(1), session(2), session(4)], TODAY) == 3
    assert progress.streak([session(1), session(2)], TODAY) == 2  # ainda vale até hoje acabar
    assert progress.streak([session(2)], TODAY) == 0
    assert progress.streak([], TODAY) == 0


def test_daily_goal_percent():  # AC-6
    goal = progress.daily_goal([session(0, 3), session(0, 3), session(1, 30)], TODAY, 10)
    assert goal == {"minutes_today": 6.0, "goal_minutes": 10, "percent": 60}


@pytest.mark.parametrize(
    "period,bars,last", [("week", 7, 6.0), ("month", 4, 11.0), ("quarter", 12, 11.0)]
)
def test_period_bars(period, bars, last):  # AC-6 — mês/trimestre: barras de 7 dias
    data = progress.summary([session(0, 4), session(0, 2), session(3, 5)], period, TODAY)
    assert len(data["bars"]) == bars
    assert data["bars"][-1]["minutes"] == last


def test_week_labels_end_today():  # AC-6
    labels = [b["label"] for b in progress.summary([], "week", TODAY)["bars"]]
    assert labels == ["TER", "QUA", "QUI", "SEX", "SÁB", "DOM", "SEG"]


def test_index_change_and_level():  # AC-6
    sessions = [session(1, index=88), session(2, index=88), session(9, index=80)]
    data = progress.summary(sessions, "week", TODAY)
    assert data["index"] == 88 and data["index_change_pct"] == 10.0
    assert data["level"] == {"number": 4, "name": "Avançado"}


def test_calm_comes_from_self_report():  # AC-6 (ansiedade só autoavaliada)
    data = progress.summary(
        [session(0, anxiety_before=4, anxiety_after=2), session(1)], "week", TODAY
    )
    assert data["bars"][-1]["calm"] == 75  # ansiedade 2 de 5 depois da sessão
    assert data["bars"][-2]["calm"] is None
    assert data["anxiety_change_pct"] == -50.0


def test_challenges_prioritize_weakest_pillar():  # AC-7
    weak_pauses = {"pace": 90, "pauses": 40, "fillers": 85, "clarity": 80}
    items = progress.challenges([session(1, pillars=weak_pauses)], TODAY)
    assert items[0]["pillar"] == "pauses" and items[0]["priority"] == "alta"
    assert not any(c["done"] for c in items)
    done = progress.challenges(
        [session(1, pillars=weak_pauses), session(0, challenge_id=items[0]["id"])], TODAY
    )
    assert next(c for c in done if c["id"] == items[0]["id"])["done"]


def test_achievements():  # AC-6
    week = [session(d) for d in range(7)]
    unlocked = {a["id"] for a in progress.achievements(week, TODAY) if a["unlocked"]}
    assert {"first_session", "streak_7"} <= unlocked
    assert "streak_7" not in {
        a["id"] for a in progress.achievements(week[:3], TODAY) if a["unlocked"]
    }


# ---------- spec 029 AC-8: pilares do período anterior, variação, pilares por barra, meta ----------
def pillars(pace, pauses, fillers, clarity):
    return {"pace": pace, "pauses": pauses, "fillers": fillers, "clarity": clarity}


def test_pillars_previous_uses_previous_window():  # 029 AC-8
    sessions = [
        session(0, pillars=pillars(80, 70, 60, 50)),
        session(9, pillars=pillars(70, 70, 50, 41)),  # período anterior de week (7–13 dias)
        session(15, pillars=pillars(10, 10, 10, 10)),  # fora das duas janelas
    ]
    data = progress.summary(sessions, "week", TODAY)
    assert data["pillars_previous"] == {"pace": 70, "pauses": 70, "fillers": 50, "clarity": 41}
    assert data["pillars_change"] == {"pace": 10, "pauses": 0, "fillers": 10, "clarity": 9}
    assert data["pillars"] == {"pace": 80, "pauses": 70, "fillers": 60, "clarity": 50}


def test_pillars_change_uses_unrounded_means():  # 029 AC-8
    sessions = [
        session(0, pillars=pillars(80, 80, 80, 80)),
        session(1, pillars=pillars(81, 80, 80, 80)),  # agora pace = 80,5 → 80 (arred. par)
        session(8, pillars=pillars(79, 80, 80, 80)),
        session(9, pillars=pillars(80, 80, 80, 80)),  # antes pace = 79,5 → 80
    ]
    data = progress.summary(sessions, "week", TODAY)
    assert data["pillars"]["pace"] == data["pillars_previous"]["pace"] == 80
    assert data["pillars_change"]["pace"] == 1  # 80,5 − 79,5, não 80 − 80


def test_pillars_change_none_when_a_side_is_missing():  # 029 AC-8
    only_now = progress.summary([session(0)], "week", TODAY)
    assert only_now["pillars_previous"] == dict.fromkeys(progress.PILLARS)
    assert only_now["pillars_change"] == dict.fromkeys(progress.PILLARS)
    only_before = progress.summary([session(9)], "week", TODAY)
    assert only_before["pillars_previous"]["pace"] == 80
    assert only_before["pillars_change"] == dict.fromkeys(progress.PILLARS)
    partial = progress.summary(
        [session(0, pillars={"pace": 90}), session(9, pillars={"pace": 70, "pauses": 60})],
        "week",
        TODAY,
    )
    assert partial["pillars_change"] == {
        "pace": 20,
        "pauses": None,
        "fillers": None,
        "clarity": None,
    }


def test_bar_pillars_per_bucket_and_none_when_empty():  # 029 AC-8
    sessions = [
        session(0, pillars=pillars(90, 80, 70, 60)),
        session(0, pillars=pillars(70, 60, 50, 41)),
        session(3, pillars={"pace": 50}),
    ]
    bars = progress.summary(sessions, "week", TODAY)["bars"]
    assert bars[-1]["pillars"] == {"pace": 80, "pauses": 70, "fillers": 60, "clarity": 50}
    assert bars[3]["pillars"] == {"pace": 50, "pauses": None, "fillers": None, "clarity": None}
    assert all(b["pillars"] is None for i, b in enumerate(bars) if i not in (3, 6))


@pytest.mark.parametrize(
    "period, goal, expected",
    [("week", 10, 10.0), ("month", 10, 70.0), ("quarter", 15, 105.0), ("week", None, None)],
)
def test_bar_goal_minutes(period, goal, expected):  # 029 AC-8
    data = progress.summary([], period, TODAY, goal_minutes=goal)
    assert data["bar_goal_minutes"] == expected
    assert progress.summary([], period, TODAY)["bar_goal_minutes"] is None
