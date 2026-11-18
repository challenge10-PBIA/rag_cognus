import pytest
from fastapi.testclient import TestClient
from langchain_core.documents import Document

from rag_cognus.api.app import Services, create_app
from rag_cognus.config import Settings
from rag_cognus.gold import save_snapshot


def exercise(phoneme="r_tap", eid="fonema-r-tepe"):
    return {
        "schemaVersion": 1,
        "id": eid,
        "phonemeId": phoneme,
        "title": "Tepe" if phoneme == "r_tap" else "Lateral",
        "phoneme": phoneme,
        "ipa": "/ɾ/" if phoneme == "r_tap" else "/l/",
        "category": "vibrantes",
        "categoryLabel": "Líquidas",
        "articulationPoint": "Alveolar",
        "articulationMode": "Toque breve" if phoneme == "r_tap" else "Contato lateral",
        "voicing": "Sonoro",
        "clinicalTip": "Faça um toque" if phoneme == "r_tap" else "Ar lateral",
        "targetWords": ["caro" if phoneme == "r_tap" else "calo"],
        "practicePhrases": ["O caro colar" if phoneme == "r_tap" else "A lua ilumina"],
        "recommendedMode": "espontanea",
        "animationKey": phoneme,
        "steps": [
            {
                "title": "Pratique",
                "instruction": "Toque" if phoneme == "r_tap" else "Sustente",
                "repetitions": 3,
            }
        ],
        "commonMistakes": ["Não force"],
        "selfCheck": ["Compare a gravação"],
        "reviewStatus": "educational_review_required",
        "sources": [{"title": "Referência", "url": "https://example.org/reference"}],
    }


def document(item):
    cid = "phonetics:" + item["id"]
    return Document(
        id=cid,
        page_content=item["clinicalTip"],
        metadata={
            "chunk_id": cid,
            "retrieval_eligible": True,
            "document_type": "phonetic_exercise",
            "exercise": item,
        },
    )


def services(tmp_path):
    return Services(
        Settings(),
        data_dir=tmp_path / "app",
        snapshot=tmp_path / "gold.jsonl",
        phonetics_snapshot=tmp_path / "phonetics.jsonl",
    )


def test_catalog_preserves_distinct_targets(tmp_path):
    from rag_cognus.phonetics import catalog_from_documents

    items = catalog_from_documents([document(exercise()), document(exercise("l_lateral", "l"))])
    assert items.exercises[0].animationKey != items.exercises[1].animationKey
    assert items.exercises[0].steps != items.exercises[1].steps


@pytest.mark.parametrize("kind", ["animation", "duplicate", "incomplete"])
def test_catalog_rejects_invalid_records(kind):
    from rag_cognus.phonetics import catalog_from_documents

    item = exercise()
    docs = [document(item)]
    if kind == "animation":
        item["animationKey"] = "l_lateral"
    elif kind == "duplicate":
        docs.append(document(item))
    else:
        item["steps"] = []
    with pytest.raises(ValueError):
        catalog_from_documents(docs)


def test_catalog_api_list_detail_and_unknown(tmp_path):
    svc = services(tmp_path)
    save_snapshot([document(exercise())], svc.phonetics_snapshot, "cognus.gold.vw_rag_exercicios")
    client = TestClient(create_app(svc))
    result = client.get("/v1/phonetics/exercises")
    assert result.status_code == 200
    assert result.json()["schemaVersion"] == 1
    assert client.get("/v1/phonetics/exercises/fonema-r-tepe").json()["ipa"] == "/ɾ/"
    assert client.get("/v1/phonetics/exercises/unknown").status_code == 404


def test_catalog_missing_is_explicit(tmp_path):
    client = TestClient(create_app(services(tmp_path)))
    assert client.get("/v1/phonetics/exercises").status_code == 503


def test_retriever_uses_same_phonetics_snapshot(tmp_path):
    svc = services(tmp_path)
    general = Document(
        id="general",
        page_content="Apresentação",
        metadata={
            "chunk_id": "general",
            "retrieval_eligible": True,
        },
    )
    save_snapshot([general], svc.snapshot, "cognus.gold.vw_rag_conhecimento")
    save_snapshot(
        [document(exercise()), document(exercise("l_lateral", "fonema-l-lateral"))],
        svc.phonetics_snapshot,
        "cognus.gold.vw_rag_exercicios",
    )
    assert {d.id for d in svc.retriever().documents} == {
        "general",
        "phonetics:fonema-r-tepe",
        "phonetics:fonema-l-lateral",
    }


def test_corrupted_catalog_returns_503(tmp_path):
    svc = services(tmp_path)
    save_snapshot([document(exercise())], svc.phonetics_snapshot, "cognus.gold.vw_rag_exercicios")
    svc.phonetics_snapshot.write_text("corrupted")
    assert TestClient(create_app(svc)).get("/v1/phonetics/exercises").status_code == 503


def test_session_validates_explicit_exercise_before_audio(tmp_path):
    svc = services(tmp_path)
    save_snapshot([document(exercise())], svc.phonetics_snapshot, "cognus.gold.vw_rag_exercicios")
    client = TestClient(create_app(svc))
    response = client.post(
        "/v1/sessions",
        data={"exercise_id": "unknown"},
        files={"audio": ("test.wav", b"invalid", "audio/wav")},
    )
    assert response.status_code == 422
    assert "Exercício fonético" in response.json()["detail"]


def test_session_persists_selected_target_without_diagnosing_it(tmp_path, documents):
    from test_api import FakeServices, wav_bytes

    svc = FakeServices(tmp_path, documents)
    save_snapshot([document(exercise())], svc.phonetics_snapshot, "cognus.gold.vw_rag_exercicios")
    client = TestClient(create_app(svc))
    response = client.post(
        "/v1/sessions",
        data={"exercise_id": "fonema-r-tepe"},
        files={"audio": ("test.wav", wav_bytes(), "audio/wav")},
    )
    assert response.status_code == 201
    result = response.json()
    assert result["exercise_id"] == "fonema-r-tepe"
    assert result["phoneme_id"] == "r_tap"
    saved = client.get("/v1/sessions/" + result["session_id"]).json()
    assert saved["exercise_id"] == "fonema-r-tepe"


def test_habit_accepts_gold_exercise(tmp_path):
    svc = services(tmp_path)
    svc.exercise_catalog = lambda: []
    save_snapshot([document(exercise())], svc.phonetics_snapshot, "cognus.gold.vw_rag_exercicios")
    response = TestClient(create_app(svc)).post(
        "/v1/habits",
        json={
            "text": "Pratiquei o tepe",
            "exercise_id": "fonema-r-tepe",
        },
    )
    assert response.status_code == 201
