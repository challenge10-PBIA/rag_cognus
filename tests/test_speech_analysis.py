import numpy as np
import pytest

from rag_cognus.speech_analysis import analyze_words, energy_contour, is_filler


def words_at(texts, gaps, duration=0.3, probability=0.9):
    """Palavras com `duration` s cada; gaps[i] = silêncio antes da palavra i."""
    out, t = [], 0.0
    for text, gap in zip(texts, gaps, strict=True):
        t += gap
        out.append({"word": text, "start": t, "end": t + duration, "probability": probability})
        t += duration
    return out


def steady(n, ppm):
    """n palavras ditas a `ppm` palavras por minuto, sem pausas longas."""
    step = 60 / ppm
    return words_at(["palavra"] * n, [0.0] + [step - 0.3] * (n - 1))


@pytest.mark.parametrize(
    "word,expected",
    [
        ("éé", True),
        ("Ééh,", True),
        ("eh", True),
        ("hum", True),
        ("tipo", True),
        ("né?", True),
        ("é", False),
        ("então", False),
        ("tipografia", False),
    ],
)
def test_filler_detection(word, expected):  # AC-3
    assert is_filler(word) is expected


def test_pace_ideal_and_slow():  # AC-1
    ideal = analyze_words(steady(140, 140))["pillars"]["pace"]
    assert ideal["value"] == pytest.approx(140, abs=2)
    assert (ideal["score"], ideal["label"]) == (100, "ideal")
    slow = analyze_words(steady(100, 100))["pillars"]["pace"]
    assert slow["score"] == pytest.approx(60, abs=3)
    assert slow["label"] == "lento"


def test_pace_ignores_fillers():  # AC-1
    words = steady(140, 140)
    for i in range(0, 140, 10):
        words[i]["word"] = "tipo"
    assert analyze_words(words)["pillars"]["pace"]["value"] < 130


def test_pauses_and_long_silences():  # AC-2
    gaps = [0.0] + [0.1] * 99
    for i in (10, 30, 50, 70):
        gaps[i] = 1.0  # pausas conscientes
    gaps[90] = 4.0  # silêncio longo
    pauses = analyze_words(words_at(["palavra"] * 100, gaps))["pillars"]["pauses"]
    assert pauses["value"] == 4 and pauses["long_silences"] == 1
    assert pauses["score"] < 100
    no_long = list(gaps)
    no_long[90] = 0.1
    better = analyze_words(words_at(["palavra"] * 100, no_long))["pillars"]["pauses"]
    assert better["score"] > pauses["score"]


def test_fillers_value_and_score():  # AC-3
    texts = ["palavra"] * 95 + ["tipo", "né", "éé", "hum", "tipo"]
    result = analyze_words(words_at(texts, [0.0] + [0.1] * 99))
    fillers = result["pillars"]["fillers"]
    assert fillers["value"] == 95.0
    assert fillers["score"] == 75
    assert fillers["counts"] == {"tipo": 2, "né": 1, "éé": 1, "hum": 1}


def test_clarity_and_index():  # AC-4
    words = steady(140, 140)
    base = analyze_words(words)
    judged = analyze_words(words, clarity_judge=5)
    assert judged["pillars"]["clarity"]["score"] > base["pillars"]["clarity"]["score"]
    scores = [p["score"] for p in judged["pillars"].values()]
    assert judged["index"] == round(sum(scores) / 4)


def test_diction_is_mean_probability():  # AC-5
    words = steady(10, 140)
    for w, p in zip(words, [0.8, 1.0] * 5, strict=True):
        w["probability"] = p
    assert analyze_words(words)["diction"] == 90


def test_empty_speech_is_rejected():
    with pytest.raises(ValueError, match="fala"):
        analyze_words([])


def test_energy_contour_bins_and_stability():
    rate = 16000
    t = np.linspace(0, 4, rate * 4, endpoint=False)
    steady_audio = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    flow = energy_contour(steady_audio, bins=20)
    assert len(flow["contour"]) == 20 and max(flow["contour"]) == 1.0
    assert flow["stability"] == "estavel"
    bursty = steady_audio * np.repeat([1.0, 0.05] * 10, len(t) // 20)
    assert energy_contour(bursty, bins=20)["stability"] == "variavel"
