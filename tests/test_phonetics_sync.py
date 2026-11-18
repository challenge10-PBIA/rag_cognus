import pytest
from langchain_core.documents import Document

from rag_cognus import phonetics_sync


def test_sync_preserves_existing_snapshot_when_catalog_schema_is_invalid(tmp_path, monkeypatch):
    snapshot = tmp_path / "phonetics.jsonl"
    manifest = snapshot.with_suffix(".manifest.json")
    snapshot.write_text("existing valid snapshot", encoding="utf-8")
    manifest.write_text("existing valid manifest", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["phonetics_sync", "--snapshot", str(snapshot)])
    monkeypatch.setattr(phonetics_sync, "load_dotenv", lambda *args: None)
    monkeypatch.setattr(
        phonetics_sync,
        "load_exercises_from_databricks",
        lambda settings: [
            Document(
                id="phonetics:invalid",
                page_content="Registro incompleto",
                metadata={
                    "chunk_id": "phonetics:invalid",
                    "retrieval_eligible": True,
                    "document_type": "phonetic_exercise",
                    "exercise": {"id": "invalid", "schemaVersion": 1},
                },
            )
        ],
    )

    with pytest.raises(ValueError):
        phonetics_sync.main()

    assert snapshot.read_text(encoding="utf-8") == "existing valid snapshot"
    assert manifest.read_text(encoding="utf-8") == "existing valid manifest"
