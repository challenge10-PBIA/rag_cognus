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


# ---------- spec 003: vícios detectados e pleonasmos ----------
def unique_words(n):
    """n palavras de conteúdo distintas (nunca repetem, então nunca viram vício)."""
    letters = "bcdfghjlmnprstvz"
    return [f"assunto{letters[i // 16]}{letters[i % 16]}" for i in range(n)]


def speech(segments, gap_pause=0.6, gap_inner=0.05):
    """segments: listas de palavras; entre segmentos há uma pausa de `gap_pause` s."""
    texts, gaps = [], []
    for s_i, segment in enumerate(segments):
        for w_i, word in enumerate(segment):
            texts.append(word)
            gaps.append(0.0 if not texts[:-1] else gap_pause if w_i == 0 else gap_inner)
    return words_at(texts, gaps)


def with_marker(marker, times, filler_per_segment):
    """`times` segmentos que começam com `marker` (após pausa), com conteúdo único."""
    pool = iter(unique_words(times * filler_per_segment))
    return speech(
        [marker.split() + [next(pool) for _ in range(filler_per_segment)] for _ in range(times)]
    )


def of_kind(result, kind):
    return [o for o in result["occurrences"] if o["kind"] == kind]


def test_occurrences_shape_and_order():  # AC-1
    words = speech([["tipo", "assunto"], ["então", "vamos", "subir", "pra", "cima"]])
    result = analyze_words(words)
    occurrences = result["occurrences"]
    assert occurrences and occurrences == sorted(occurrences, key=lambda o: o["start"])
    for o in occurrences:
        assert {"term", "kind", "excerpt", "start", "end", "suggestion", "source"} <= set(o)
        assert o["kind"] in {"vicio_fixo", "vicio_detectado", "pleonasmo"}
        assert o["source"] in {"lexico", "estatistica", "llm"}
        assert isinstance(o["suggestion"], str) and o["suggestion"]
    pleonasm = of_kind(result, "pleonasmo")[0]
    assert pleonasm["start"] == words[4]["start"] and pleonasm["end"] == words[6]["end"]


def test_fixed_fillers_become_occurrences():  # AC-2
    texts = ["palavra"] * 10 + ["tipo", "né", "éé", "hum"]
    result = analyze_words(words_at(texts, [0.0] + [0.1] * 13))
    fixed = of_kind(result, "vicio_fixo")
    assert [o["term"] for o in fixed] == ["tipo", "né", "éé", "hum"]
    assert {o["source"] for o in fixed} == {"lexico"}
    assert {o["suggestion"] for o in fixed} == {"Troque por um silêncio curto e respire."}


def test_seed_marker_detected_above_rate_only():  # AC-3
    frequent = analyze_words(with_marker("então", 6, 20))  # ~6× em ~1 min
    detected = of_kind(frequent, "vicio_detectado")
    assert [o["term"] for o in detected] == ["então"] * 6
    assert {o["source"] for o in detected} == {"estatistica"}
    moderate = with_marker("então", 2, 20)
    stretched = [dict(w, start=w["start"] * 10, end=w["end"] * 10) for w in moderate]
    assert of_kind(analyze_words(stretched), "vicio_detectado") == []  # 2× em >2 min


def test_non_seed_needs_boundary_and_content():  # AC-4
    de_fato = analyze_words(with_marker("de fato", 6, 20))
    assert {o["term"] for o in of_kind(de_fato, "vicio_detectado")} == {"de fato"}
    pool = iter(unique_words(200))
    mid = speech([[next(pool), "projeto", next(pool)] for _ in range(8)], gap_pause=0.05)
    assert of_kind(analyze_words(mid), "vicio_detectado") == []
    stop = analyze_words(with_marker("de que", 8, 15))
    assert of_kind(stop, "vicio_detectado") == []


def test_longest_ngram_wins():  # AC-5
    result = analyze_words(with_marker("tipo assim", 6, 20))
    vices = [o for o in result["occurrences"] if o["kind"].startswith("vicio")]
    assert [o["term"] for o in vices] == ["tipo assim"] * 6
    spans = [(o["start"], o["end"]) for o in vices]
    assert len(set(spans)) == len(spans)


@pytest.mark.parametrize(
    "phrase,suggestion",
    [
        ("subir pra cima", "subir"),
        ("subimos para cima", "subimos"),
        ("descer para baixo", "descer"),
        ("elo de ligação", "elo"),
        ("surpresa inesperada", "surpresa"),
        ("há dois anos atrás", "há dois anos"),
        ("há anos atrás", "há anos"),
        ("encarar de frente", "encarar"),
        ("entrar pra dentro", "entrar"),
        ("sair pra fora", "sair"),
        ("repetir de novo", "repetir"),
        ("planejar antecipadamente", "planejar"),
        ("fato real", "fato"),
        ("consenso geral", "consenso"),
    ],
)
def test_pleonasm_lexicon(phrase, suggestion):  # AC-6
    words = speech([["hoje", "vamos"] + phrase.split() + ["juntos"]])
    found = of_kind(analyze_words(words), "pleonasmo")
    assert [(o["term"], o["suggestion"]) for o in found] == [(phrase, suggestion)]


def test_pleonasm_occurrence_fields():  # AC-7
    words = speech([["a", "equipe", "Subiu", "pra", "cima,", "rápido"]])
    [o] = of_kind(analyze_words(words), "pleonasmo")
    assert (o["term"], o["source"], o["suggestion"]) == ("Subiu pra cima,", "lexico", "Subiu")
    assert (o["start"], o["end"]) == (words[2]["start"], words[4]["end"])
    assert o["confirmed_by_llm"] is None
    assert analyze_words(words)["pillars"]["fillers"]["counts"] == {}


def test_excerpt_is_copied_from_transcript():  # AC-8
    texts = "um dois três quatro cinco elo de ligação seis sete oito nove dez".split()
    [o] = of_kind(analyze_words(speech([texts])), "pleonasmo")
    assert o["excerpt"] == "dois três quatro cinco elo de ligação seis sete oito nove"
    [edge] = of_kind(analyze_words(speech([["elo", "de", "ligação", "fim"]])), "pleonasmo")
    assert edge["excerpt"] == "elo de ligação fim"


PLEONASM_WORDS = ["hoje", "vamos", "subir", "pra", "cima", "e", "o", "elo", "de", "ligação"]


def test_checker_is_optional_and_receives_candidates():  # AC-9
    calls = []

    def checker(text, candidates):
        calls.append((text, [c["term"] for c in candidates]))
        return {"confirmed": [], "suggested": []}

    words = speech([PLEONASM_WORDS])
    analyze_words(words)
    assert calls == []
    analyze_words(words, pleonasm_checker=checker)
    assert calls == [(" ".join(PLEONASM_WORDS), ["subir pra cima", "elo de ligação"])]


def test_checker_confirmation_flag():  # AC-10
    def checker(text, candidates):
        return {"confirmed": [1], "suggested": []}

    words = speech([PLEONASM_WORDS])
    found = of_kind(analyze_words(words, pleonasm_checker=checker), "pleonasmo")
    assert [(o["term"], o["confirmed_by_llm"]) for o in found] == [
        ("subir pra cima", False),
        ("elo de ligação", True),
    ]
    assert {o["confirmed_by_llm"] for o in of_kind(analyze_words(words), "pleonasmo")} == {None}


def test_checker_suggestions_must_exist_in_transcript():  # AC-11
    texts = ["o", "sorriso", "nos", "lábios", "ficou", "e", "subir", "pra", "cima", "foi"]

    def checker(text, candidates):
        return {
            "confirmed": [0],
            "suggested": [
                {"trecho": "Sorriso nos lábios", "sugestao": "sorriso"},
                {"trecho": "inventado pela IA", "sugestao": "x"},
                {"trecho": "subir pra cima", "sugestao": "subir"},
            ],
        }

    words = speech([texts])
    found = of_kind(analyze_words(words, pleonasm_checker=checker), "pleonasmo")
    assert [(o["term"], o["source"]) for o in found] == [
        ("sorriso nos lábios", "llm"),
        ("subir pra cima", "lexico"),
    ]
    assert found[0]["suggestion"] == "sorriso"
    assert (found[0]["start"], found[0]["end"]) == (words[1]["start"], words[3]["end"])


@pytest.mark.parametrize(
    "behavior",
    [
        lambda text, candidates: (_ for _ in ()).throw(RuntimeError("Ollama fora do ar")),
        lambda text, candidates: "não é json",
        lambda text, candidates: {"confirmed": ["x"], "suggested": [{"trecho": 3}]},
    ],
)
def test_checker_failure_falls_back_to_lexicon(behavior):  # AC-12
    words = speech([PLEONASM_WORDS])
    assert analyze_words(words, pleonasm_checker=behavior) == analyze_words(words)


def test_fillers_pillar_counts_detected_and_pleonasms():  # AC-13
    words = with_marker("então", 6, 20)  # 126 palavras, 6 vícios
    fillers = analyze_words(words)["pillars"]["fillers"]
    rate = 100 * 6 / len(words)
    assert fillers["counts"] == {"então": 6}
    assert fillers["value"] == round(100 - rate, 1)
    assert fillers["score"] == round(100 - 5 * rate)
    assert fillers["pleonasms"] == 0
    many = speech([[w, "subir", "pra", "cima", w + "x"] for w in unique_words(7)])
    pleo = analyze_words(many)["pillars"]["fillers"]
    assert pleo["pleonasms"] == 7 and pleo["score"] == 85  # parcela limitada a 15
    one = analyze_words(speech([["elo", "de", "ligação", "bom"]]))["pillars"]["fillers"]
    assert one["score"] == 97


def test_pace_ignores_only_fixed_fillers():  # AC-14
    words = with_marker("então", 6, 20)
    result = analyze_words(words)
    minutes = max(words[-1]["end"] - words[0]["start"], 1.0) / 60
    assert result["pillars"]["pace"]["value"] == round(len(words) / minutes)
    assert result["index"] == round(sum(p["score"] for p in result["pillars"].values()) / 4)
