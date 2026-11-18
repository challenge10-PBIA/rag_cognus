import pytest
from fastapi.testclient import TestClient
from langchain_core.documents import Document

from rag_cognus.api.app import Services, create_app
from rag_cognus.config import Settings
from rag_cognus.gold import save_snapshot


def demonstration(phoneme="r_tap"):
    stages_map = {
        "r_tap": [
            {
                "index": 0,
                "title": "1. Preparação",
                "shortLabel": "1. Preparação",
                "caption": "Preparar ápice",
                "segmentLabel": "ca-",
                "targetWord": "caro",
                "durationMs": 1000,
                "gesture": "neutral_prep",
                "contactRegion": "none",
                "airflow": "oral_central",
                "velum": "raised",
                "voicingState": "voiced",
            },
            {
                "index": 1,
                "title": "2. Toque breve",
                "shortLabel": "2. Toque /ɾ/",
                "caption": "Toque alveolar único",
                "segmentLabel": "-r-",
                "targetWord": "caro",
                "durationMs": 1000,
                "gesture": "alveolar_tap",
                "contactRegion": "alveolar",
                "airflow": "oral_central",
                "velum": "raised",
                "voicingState": "voiced",
            },
            {
                "index": 2,
                "title": "3. Soltura",
                "shortLabel": "3. Soltura",
                "caption": "Soltura para a vogal",
                "segmentLabel": "-o",
                "targetWord": "caro",
                "durationMs": 1000,
                "gesture": "release_vowel",
                "contactRegion": "none",
                "airflow": "oral_central",
                "velum": "raised",
                "voicingState": "voiced",
            },
        ],
        "l_lateral": [
            {
                "index": 0,
                "title": "1. Preparação",
                "shortLabel": "1. Preparação",
                "caption": "Elevar ponta",
                "segmentLabel": "ca-",
                "targetWord": "calo",
                "durationMs": 1000,
                "gesture": "neutral_prep",
                "contactRegion": "none",
                "airflow": "oral_central",
                "velum": "raised",
                "voicingState": "voiced",
            },
            {
                "index": 1,
                "title": "2. Apoio lateral",
                "shortLabel": "2. Lateral /l/",
                "caption": "Contato sustentado e ar lateral",
                "segmentLabel": "-l-",
                "targetWord": "calo",
                "durationMs": 1800,
                "gesture": "alveolar_lateral_hold",
                "contactRegion": "dental_alveolar",
                "airflow": "oral_lateral",
                "velum": "raised",
                "voicingState": "voiced",
            },
            {
                "index": 2,
                "title": "3. Soltura",
                "shortLabel": "3. Soltura",
                "caption": "Soltura suave",
                "segmentLabel": "-o",
                "targetWord": "calo",
                "durationMs": 1000,
                "gesture": "release_vowel",
                "contactRegion": "none",
                "airflow": "oral_central",
                "velum": "raised",
                "voicingState": "voiced",
            },
        ],
    }
    return {
        "schemaVersion": 2,
        "contractVersion": "2026-11-18.v2",
        "profileId": phoneme,
        "summary": "Demonstração articulatória estruturada",
        "targetSequence": [
            {
                "word": "caro" if phoneme == "r_tap" else "calo",
                "ipa": "[ˈka.ɾu]" if phoneme == "r_tap" else "[ˈka.lu]",
                "focus": "Alvo principal",
            }
        ],
        "regionalVariants": [],
        "stages": stages_map.get(phoneme, stages_map["r_tap"]),
    }


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
        "demonstration": demonstration(phoneme),
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


def test_demonstration_contract_supports_all_ten_profiles_and_rejects_mismatches():
    import copy
    import json
    from pathlib import Path

    from rag_cognus.phonetics import PhoneticExercise, catalog_from_documents

    catalog_path = (
        Path(__file__).resolve().parents[2]
        / "medallion_cognus/conhecimento/catalogos/exercicios_foneticos.json"
    )
    raw = json.loads(catalog_path.read_text(encoding="utf-8"))
    docs = [document(item) for item in raw["exercises"]]
    catalog = catalog_from_documents(docs)
    assert len(catalog.exercises) == 10
    by_pid = {ex.phonemeId: ex for ex in catalog.exercises}
    assert set(by_pid) == {
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
    }
    for pid, ex in by_pid.items():
        assert ex.animationKey == pid
        assert ex.demonstration is not None
        assert ex.demonstration.schemaVersion == 2
        assert ex.demonstration.contractVersion == "2026-11-18.v2"
        assert ex.demonstration.profileId == pid
        assert len(ex.demonstration.stages) >= 3
        assert len(ex.demonstration.targetSequence) >= 1

    # AC-2: multi-sound sequences and regional variants
    assert len(by_pid["r_strong"].demonstration.regionalVariants) >= 2
    assert {s.voicingState for s in by_pid["fricatives_postalveolar"].demonstration.stages} >= {
        "voiced",
        "voiceless",
    }
    assert {s.gesture for s in by_pid["contrast_r_l"].demonstration.stages} >= {
        "alveolar_tap",
        "alveolar_lateral_hold",
    }
    assert any(
        s.airflow == "nasal" and s.velum == "lowered"
        for s in by_pid["nh_nasal"].demonstration.stages
    )

    # AC-3: incompatible profileId or missing required airflow/gesture rejected
    bad_profile = copy.deepcopy(raw["exercises"][0])
    bad_profile["demonstration"] = copy.deepcopy(raw["exercises"][1]["demonstration"])
    with pytest.raises(ValueError, match="profileId"):
        PhoneticExercise.model_validate(bad_profile)

    bad_nh = copy.deepcopy(raw["exercises"][4])
    for st in bad_nh["demonstration"]["stages"]:
        st["airflow"] = "oral_central"
    with pytest.raises(ValueError, match="nh_nasal"):
        PhoneticExercise.model_validate(bad_nh)

    bad_contrast = copy.deepcopy(raw["exercises"][8])
    for st in bad_contrast["demonstration"]["stages"]:
        if st["gesture"] == "alveolar_lateral_hold":
            st["gesture"] = "alveolar_tap"
    with pytest.raises(ValueError, match="contrast_r_l"):
        PhoneticExercise.model_validate(bad_contrast)
