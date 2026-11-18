"""Spec 006 — feedback guiado (AC-1 a AC-9). Retriever, chat e catálogo são fakes."""

import json
import socket
from types import SimpleNamespace

import pytest

from rag_cognus import feedback, progress

CHUNKS = {
    "c1": "Respire antes de cada frase. Isso dá ritmo à fala e evita atropelos.",
    "c2": "Pausas curtas reforçam a mensagem! O público precisa de tempo para absorver.",
    "c3": "Evite vícios de linguagem trocando-os por silêncio. A fluência melhora com treino.",
}


class Doc:
    def __init__(self, cid):
        self.id = cid
        self.page_content = CHUNKS[cid]
        self.metadata = {"chunk_id": cid, "title": f"Título {cid}", "source_url": f"u/{cid}"}


class FakeRetriever:
    def __init__(self, ids=("c1", "c2", "c3")):
        self.ids = ids
        self.calls = []

    def search(self, query, niche=None, k=None):
        self.calls.append((query, k))
        return [Doc(c) for c in self.ids][:k]


class BrokenRetriever:
    def search(self, query, niche=None, k=None):
        raise RuntimeError("Base de conhecimento não carregada")


class FakeChat:
    def __init__(self, payload):
        self.payload = payload
        self.prompts = []

    def invoke(self, messages):
        self.prompts.append(messages)
        if isinstance(self.payload, Exception):
            raise self.payload
        content = self.payload if isinstance(self.payload, str) else json.dumps(self.payload)
        return SimpleNamespace(content=content)


def ex(eid, pillar):
    return {
        "id": eid,
        "titulo": f"Exercício {eid}",
        "categoria": "respiracao",
        "pilares": [pillar],
        "passos": ["a", "b"],
        "duracao_min": 3,
        "nivel": "iniciante",
        "fonte": {"titulo": "T", "autor": "A", "ano": 2020, "url": "https://x", "tipo": "livro"},
        "verificado_em": "2026-11-16",
    }


CATALOG = {p: [ex(f"{p}-1", p), ex(f"{p}-2", p)] for p in ("pace", "pauses", "fillers")}
CATALOG["clarity"] = [ex("clarity-1", "clarity")]


def fake_exercises(pillar, limit=2):
    return [dict(e) for e in CATALOG.get(pillar, [])][:limit]


def analysis(pace=90, pauses=90, fillers=90, clarity=90, diction=95):
    scores = {"pace": pace, "pauses": pauses, "fillers": fillers, "clarity": clarity}
    return {"pillars": {k: {"score": v} for k, v in scores.items()}, "diction": diction}


def occ(term, kind="vicio_fixo"):
    return {"term": term, "kind": kind, "excerpt": f"... {term} ...", "start": 0.0, "end": 1.0}


def build(an, occurrences=(), retriever=None, chat=None, exercises_fn=fake_exercises):
    return feedback.build_guided(
        an, list(occurrences), retriever, chat=chat, exercises_fn=exercises_fn
    )


def test_ac1_pure_without_chat_and_accepts_none_retriever(monkeypatch):  # AC-1
    def no_network(*args, **kwargs):
        raise AssertionError("rede acessada")

    monkeypatch.setattr(socket, "socket", no_network)
    recs = build(analysis(pace=40), retriever=None)
    assert recs and recs[0]["pillar"] == "pace"
    assert build(analysis(pace=40), retriever=FakeRetriever())[0]["subs"]


def test_ac2_selection_order_and_limits():  # AC-2
    an = analysis(pace=75, pauses=30, fillers=60, clarity=50, diction=65)
    occurrences = [occ("tipo"), occ("né"), occ("tipo"), occ("subir pra cima", "pleonasmo")]
    recs = build(an, occurrences)
    targets = [(r["pillar"], r["target"]["kind"], r["target"]["term"]) for r in recs]
    # 5 pilares fracos → só os 3 piores; depois o termo mais frequente; total 4
    assert targets == [
        ("pauses", "pillar", None),
        ("clarity", "pillar", None),
        ("fillers", "pillar", None),
        ("fillers", "occurrence", "tipo"),
    ]
    # diction entra se < 70; pleonasmo → clarity
    recs = build(analysis(diction=60), [occ("subir pra cima", "pleonasmo"), occ("aí")])
    targets = [(r["pillar"], r["target"]["kind"], r["target"]["term"]) for r in recs]
    assert targets == [
        ("diction", "pillar", None),
        ("clarity", "occurrence", "subir pra cima"),
        ("fillers", "occurrence", "aí"),
    ]
    # nada selecionado → "Manter" para o pilar de menor score
    recs = build(analysis(pace=95, pauses=85, fillers=99, clarity=88, diction=90))
    assert len(recs) == 1
    assert recs[0]["pillar"] == "pauses" and recs[0]["title"].startswith("Manter")


def test_ac3_shape_and_priority():  # AC-3
    recs = build(analysis(pace=40, pauses=55, fillers=72, diction=69), [occ("tipo")])
    for r in recs:
        assert set(r) == {
            "id",
            "pillar",
            "target",
            "title",
            "text",
            "priority",
            "subs",
            "exercises",
            "sources_available",
            "pillar_score",  # spec 008 AC-8
            "maintain",
        }
        assert set(r["target"]) == {"kind", "term"}
        assert r["title"] and r["text"]
    by = {(r["pillar"], r["target"]["kind"]): r["priority"] for r in recs}
    assert by[("pace", "pillar")] == "alta"
    assert by[("pauses", "pillar")] == "media"
    assert by[("diction", "pillar")] == "media"
    assert by[("fillers", "occurrence")] == "baixa"
    assert len({r["id"] for r in recs}) == len(recs)


def test_ac4_gold_query_and_anchored_subs():  # AC-4
    retriever = FakeRetriever()
    recs = build(analysis(pace=40, diction=60), [occ("tipo")], retriever=retriever)
    assert retriever.calls == [
        (progress.CHALLENGES["pace"]["query"], 3),
        (feedback.DICTION_QUERY, 3),
        (progress.CHALLENGES["fillers"]["query"] + " tipo", 3),
    ]
    for r in recs:
        assert 1 <= len(r["subs"]) <= 3 and r["sources_available"] is True
        for sub in r["subs"]:
            assert set(sub) == {"text", "source", "excerpt"}
            cid = sub["source"]["chunk_id"]
            assert sub["source"] == {"chunk_id": cid, "title": f"Título {cid}", "url": f"u/{cid}"}
            assert sub["excerpt"] in CHUNKS[cid] and len(sub["excerpt"]) <= 240


def test_ac5_deterministic_subs_without_chat():  # AC-5
    long = "a" * 300 + ". fim."
    CHUNKS["c9"] = long
    try:
        recs = build(analysis(pace=40), retriever=FakeRetriever(("c1", "c2", "c9")))
    finally:
        del CHUNKS["c9"]
    subs = recs[0]["subs"]
    assert [s["text"] for s in subs] == [
        "Respire antes de cada frase.",
        "Pausas curtas reforçam a mensagem!",
        "a" * 200,
    ]
    assert all(s["excerpt"] == s["text"] for s in subs)
    assert [s["source"]["chunk_id"] for s in subs] == ["c1", "c2", "c9"]


def test_ac6_llm_output_validated_and_fallback():  # AC-6
    good = {"text": "Inspire antes de falar.", "chunk_id": "c1", "excerpt": "Respire antes"}
    payload = [
        good,
        {"text": "Inventado", "chunk_id": "c99", "excerpt": "Respire antes"},
        {"text": "Paráfrase", "chunk_id": "c2", "excerpt": "pausas reforçam"},
    ]
    chat = FakeChat(payload)
    recs = build(analysis(pace=40), retriever=FakeRetriever(), chat=chat)
    assert recs[0]["subs"] == [
        {
            "text": "Inspire antes de falar.",
            "source": {"chunk_id": "c1", "title": "Título c1", "url": "u/c1"},
            "excerpt": "Respire antes",
        }
    ]
    assert CHUNKS["c1"] in str(chat.prompts[0])  # o LLM recebeu os trechos
    deterministic = build(analysis(pace=40), retriever=FakeRetriever())[0]["subs"]
    bad = FakeChat([{"text": "x", "chunk_id": "c99", "excerpt": "nada"}])
    assert build(analysis(pace=40), retriever=FakeRetriever(), chat=bad)[0]["subs"] == (
        deterministic
    )
    for broken in (FakeChat(RuntimeError("ollama fora")), FakeChat("não é json")):
        recs = build(analysis(pace=40), retriever=FakeRetriever(), chat=broken)
        assert recs[0]["subs"] == deterministic


@pytest.mark.parametrize("retriever", [None, BrokenRetriever()])
def test_ac7_gold_unavailable(retriever):  # AC-7
    recs = build(analysis(pace=40), [occ("tipo")], retriever=retriever)
    assert len(recs) == 2
    for r in recs:
        assert r["subs"] == [] and r["sources_available"] is False
        assert r["exercises"] and r["title"] and r["text"]


def test_ac8_exercises_only_from_catalog():  # AC-8
    recs = build(analysis(pace=40, clarity=50, diction=60))
    by = {r["pillar"]: r["exercises"] for r in recs}
    assert by["pace"] == CATALOG["pace"]  # sem alteração de campos
    assert by["clarity"] == CATALOG["clarity"]
    assert by["diction"] == []  # catálogo sem exercício para o pilar
    chat = FakeChat({"subs": [], "exercises": ["inventado", "pace-2"]})
    recs = build(analysis(pace=40), retriever=FakeRetriever(), chat=chat)
    assert [e["id"] for e in recs[0]["exercises"]] == ["pace-2"]
    assert recs[0]["exercises"][0] == CATALOG["pace"][1]
    chat = FakeChat({"subs": [], "exercises": ["inventado"]})
    recs = build(analysis(pace=40), retriever=FakeRetriever(), chat=chat)
    assert recs[0]["exercises"] == CATALOG["pace"]


def test_ac9_catalog_missing_or_invalid():  # AC-9
    def broken(pillar, limit=2):
        raise FileNotFoundError("data/exercicios.json")

    recs = build(analysis(pace=40, fillers=50), [occ("tipo")], FakeRetriever(), exercises_fn=broken)
    assert len(recs) == 3
    assert all(r["exercises"] == [] for r in recs)
    assert all(r["subs"] for r in recs)


def test_spec008_ac8_pillar_score_and_maintain():  # spec 008 AC-8
    an = analysis(pace=40.6, fillers=85, diction=60)
    recs = build(an, [occ("tipo"), occ("subir pra cima", "pleonasmo")])
    by = {(r["pillar"], r["target"]["kind"]): r for r in recs}
    assert by[("pace", "pillar")]["pillar_score"] == 41
    assert by[("diction", "pillar")]["pillar_score"] == 60  # dicção usa analysis["diction"]
    assert by[("fillers", "occurrence")]["pillar_score"] == 85
    assert by[("clarity", "occurrence")]["pillar_score"] == 90
    assert all(r["maintain"] is False for r in recs)
    assert all(isinstance(r["pillar_score"], int) for r in recs)
    keep = build(analysis(pace=95, pauses=85, fillers=99, clarity=88, diction=90))
    assert [(r["title"].startswith("Manter"), r["maintain"]) for r in keep] == [(True, True)]
    assert keep[0]["pillar_score"] == 85
