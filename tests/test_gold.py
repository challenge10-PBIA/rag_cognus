import json
from types import SimpleNamespace as NS

import pytest

from rag_cognus.config import Settings, qualified_name
from rag_cognus.gold import _documents, load_from_databricks, load_snapshot, save_snapshot


def test_snapshot_detects_tampering(documents, tmp_path):
    path = tmp_path / "gold.jsonl"
    save_snapshot(documents, path, Settings.gold_view)
    assert [d.id for d in load_snapshot(path)] == ["a", "b", "c"]
    path.write_text(path.read_text() + "\n")
    with pytest.raises(ValueError, match="hash"):
        load_snapshot(path)


def test_rejects_duplicate_or_ineligible(documents):
    d = documents[0]
    row = {
        "chunk_id": d.id,
        "page_content": d.page_content,
        "metadata_json": json.dumps(d.metadata),
    }
    with pytest.raises(ValueError, match="duplicado"):
        _documents([row, row])
    row["metadata_json"] = json.dumps({**d.metadata, "retrieval_eligible": False})
    with pytest.raises(ValueError, match="não elegível"):
        _documents([row])


def test_sql_name_is_validated():
    with pytest.raises(ValueError):
        qualified_name("cognus.gold.x; DROP TABLE x")


def test_sql_pagination(monkeypatch, documents):
    import databricks.sdk

    def data(d):
        return [d.id, d.page_content, json.dumps(d.metadata)]

    chunks = [
        NS(data_array=[data(documents[0])], next_chunk_index=1),
        NS(data_array=[data(d) for d in documents[1:]], next_chunk_index=None),
    ]
    manifest = NS(
        schema=NS(columns=[NS(name=n) for n in ["chunk_id", "page_content", "metadata_json"]]),
        truncated=False,
    )
    service = NS(
        execute_statement=lambda **kwargs: NS(
            status=NS(state="SUCCEEDED"), manifest=manifest, result=chunks[0]
        ),
        get_statement_result_chunk_n=lambda statement, index: chunks[index],
    )
    # A resposta mantém o statement_id entre as páginas.
    service.execute_statement = lambda **kwargs: NS(
        status=NS(state="SUCCEEDED"), manifest=manifest, result=chunks[0], statement_id="s1"
    )
    monkeypatch.setattr(
        databricks.sdk, "WorkspaceClient", lambda **kwargs: NS(statement_execution=service)
    )
    actual = load_from_databricks(Settings(warehouse_id="example"))
    assert [d.id for d in actual] == ["a", "b", "c"]
