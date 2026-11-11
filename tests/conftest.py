import json

import mlflow
import pytest
from langchain_core.documents import Document


@pytest.fixture(scope="session", autouse=True)
def isolated_tracking(tmp_path_factory):
    uri = "sqlite:///" + str(tmp_path_factory.mktemp("tracking") / "mlflow.db")
    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment("tests")
    return uri


@pytest.fixture
def documents():
    values = [
        ("a", "Storytelling e oratória para uma apresentação clara.", "apresentacoes_oratoria"),
        ("b", "Rouquidão e saúde vocal: orientações para professores.", "voz_saude_vocal"),
        ("c", "Escuta ativa e feedback em comunicação assertiva.", "assertividade_escuta"),
    ]
    return [
        Document(
            id=cid,
            page_content=text,
            metadata={
                "chunk_id": cid,
                "doc_id": "doc-" + cid,
                "doc_version": "v1",
                "gold_version": "test",
                "retrieval_eligible": True,
                "source_url": "https://example.org/" + cid,
                "title": cid,
                "audience": "teste",
                "nichos_json": json.dumps([niche]),
            },
        )
        for cid, text, niche in values
    ]
