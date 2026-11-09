from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Iterable
from pathlib import Path

from langchain_core.documents import Document

from rag_cognus.config import Settings, qualified_name


def _documents(rows: Iterable[dict]) -> list[Document]:
    docs, seen = [], set()
    for row in rows:
        metadata = json.loads(row["metadata_json"])
        cid = row["chunk_id"]
        if not row["page_content"] or not cid or cid in seen:
            raise ValueError("Gold contém texto vazio ou chunk_id ausente/duplicado.")
        if metadata.get("chunk_id") != cid or metadata.get("retrieval_eligible") is not True:
            raise ValueError("Metadados inconsistentes ou trecho não elegível na visão RAG.")
        seen.add(cid)
        docs.append(Document(id=cid, page_content=row["page_content"], metadata=metadata))
    if not docs:
        raise ValueError("A consulta à Gold não retornou trechos elegíveis.")
    return docs


def load_from_spark(spark, view: str = Settings.gold_view) -> list[Document]:
    view = qualified_name(view)
    rows = spark.table(view).select("chunk_id", "page_content", "metadata_json").orderBy("chunk_id")
    return _documents(r.asDict() for r in rows.toLocalIterator())


def load_from_databricks(settings: Settings, timeout: int = 300) -> list[Document]:
    """OAuth pelo perfil; lê todas as páginas da Statement Execution API."""
    from databricks.sdk import WorkspaceClient

    if not settings.warehouse_id:
        raise ValueError("Configure DATABRICKS_WAREHOUSE_ID para leitura fora do notebook.")
    client = WorkspaceClient(profile=settings.profile)
    query = (
        f"SELECT chunk_id, page_content, metadata_json FROM "
        f"{qualified_name(settings.gold_view)} ORDER BY chunk_id"
    )
    response = client.statement_execution.execute_statement(
        warehouse_id=settings.warehouse_id,
        statement=query,
        wait_timeout="0s",
    )
    deadline = time.monotonic() + timeout
    while True:
        state = getattr(response.status.state, "value", response.status.state)
        if state == "SUCCEEDED":
            break
        if state in {"FAILED", "CANCELED", "CLOSED"}:
            raise RuntimeError(f"Consulta Gold falhou: {response.status.error}")
        if time.monotonic() >= deadline:
            client.statement_execution.cancel_execution(response.statement_id)
            raise TimeoutError("Tempo limite ao consultar a Gold.")
        time.sleep(1)
        response = client.statement_execution.get_statement(response.statement_id)
    if response.manifest is None or response.result is None:
        raise RuntimeError("Resposta SQL sem manifesto ou resultado.")
    names = [column.name for column in response.manifest.schema.columns]
    rows = []
    chunk = response.result
    while chunk is not None:
        rows.extend(dict(zip(names, row, strict=True)) for row in (chunk.data_array or []))
        if chunk.next_chunk_index is None:
            break
        chunk = client.statement_execution.get_statement_result_chunk_n(
            response.statement_id,
            chunk.next_chunk_index,
        )
    if response.manifest.truncated:
        raise RuntimeError("Gold truncada pela API; não usar snapshot parcial.")
    return _documents(rows)


def save_snapshot(documents: list[Document], path: str | Path, view: str) -> dict:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(
            {
                "chunk_id": d.metadata["chunk_id"],
                "page_content": d.page_content,
                "metadata_json": json.dumps(d.metadata, ensure_ascii=False),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        for d in sorted(documents, key=lambda d: d.metadata["chunk_id"])
    ]
    content = "\n".join(lines) + "\n"
    path.write_text(content, encoding="utf-8")
    manifest = {
        "gold_view": view,
        "chunk_count": len(documents),
        "snapshot_sha256": hashlib.sha256(content.encode()).hexdigest(),
        "gold_versions": sorted({d.metadata.get("gold_version", "") for d in documents}),
        "source_silver_versions": sorted(
            {d.metadata.get("source_table_version", -1) for d in documents}
        ),
    }
    path.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def load_snapshot(path: str | Path) -> list[Document]:
    path = Path(path)
    raw = path.read_bytes()
    manifest = json.loads(path.with_suffix(".manifest.json").read_text())
    if hashlib.sha256(raw).hexdigest() != manifest["snapshot_sha256"]:
        raise ValueError("Snapshot alterado: hash diferente do manifesto.")
    docs = _documents(json.loads(line) for line in raw.decode().splitlines() if line.strip())
    if len(docs) != manifest["chunk_count"]:
        raise ValueError("Contagem diferente do manifesto.")
    return docs
