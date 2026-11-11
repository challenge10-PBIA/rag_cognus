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


def test_token_auth_uses_host_and_ignores_profile_env(monkeypatch):
    import os

    import databricks.sdk

    from rag_cognus.gold import workspace_client

    calls = []

    def fake_client(**kwargs):
        calls.append((kwargs, os.environ.get("DATABRICKS_CONFIG_PROFILE")))
        return NS()

    monkeypatch.setattr(databricks.sdk, "WorkspaceClient", fake_client)
    monkeypatch.setenv("DATABRICKS_CONFIG_PROFILE", "perfil-inexistente")
    settings = Settings(host="adb-123.azuredatabricks.net/", token="dapi-secreto")
    workspace_client(settings)
    kwargs, profile_during_call = calls[0]
    assert kwargs == {
        "host": "https://adb-123.azuredatabricks.net",
        "token": "dapi-secreto",
        "auth_type": "pat",
    }
    assert profile_during_call is None
    assert os.environ["DATABRICKS_CONFIG_PROFILE"] == "perfil-inexistente"
    assert "dapi-secreto" not in repr(settings)


def test_profile_auth_when_no_token(monkeypatch):
    import databricks.sdk

    from rag_cognus.gold import workspace_client

    calls = []
    monkeypatch.setattr(databricks.sdk, "WorkspaceClient", lambda **kw: calls.append(kw))
    workspace_client(Settings(profile="serviceUser"))
    assert calls == [{"profile": "serviceUser"}]


def test_host_without_token_is_rejected():
    with pytest.raises(ValueError, match="juntos"):
        load_from_databricks(Settings(host="https://x", warehouse_id="w"))


def test_settings_read_token_from_env(monkeypatch):
    monkeypatch.setenv("DATABRICKS_HOST", "https://x.cloud.databricks.com")
    monkeypatch.setenv("DATABRICKS_TOKEN", "dapi-1")
    settings = Settings.from_env()
    assert settings.databricks_auth == "token" and settings.token == "dapi-1"
