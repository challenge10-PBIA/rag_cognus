import pytest
from langchain_core.embeddings import Embeddings

from rag_cognus.config import Settings
from rag_cognus.retrieval import GoldRetriever, tokenize


def test_bm25_filter_and_no_matches(documents):
    retriever = GoldRetriever(documents, Settings())
    assert retriever.search("storytelling")[0].id == "a"
    assert not retriever.search("storytelling", niche="voz_saude_vocal")
    assert not retriever.search("zzzzdesconhecido")
    assert not retriever.search("como a o")
    with pytest.raises(ValueError):
        retriever.search("voz", niche="inventado")
    assert "nao" in tokenize("Não force a voz")


class TestEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [[1.0, 0.0] if "Storytelling" in t else [0.0, 1.0] for t in texts]

    def embed_query(self, text):
        return [1.0, 0.0]


def test_dense_filter_applied_before_top_k(documents):
    retriever = GoldRetriever(
        documents, Settings(backend="dense", dense_min_score=-1), TestEmbeddings()
    )
    assert retriever.search("apresentar", k=1)[0].id == "a"
    assert retriever.search("apresentar", niche="voz_saude_vocal", k=1)[0].id == "b"


def test_embedding_requests_are_bounded(documents):
    class LimitedEmbeddings(TestEmbeddings):
        def embed_documents(self, texts):
            if len(texts) > 16:
                raise ValueError("lote grande demais para o servidor")
            return super().embed_documents(texts)

    many = []
    for i in range(35):
        d = documents[i % 3].model_copy(deep=True)
        d.id = str(i)
        d.metadata["chunk_id"] = str(i)
        many.append(d)
    retriever = GoldRetriever(many, Settings(backend="dense"), LimitedEmbeddings())
    assert len(retriever.search("apresentação", k=30)) == 12


def test_retriever_span_documents_have_doc_uri(documents):  # 011 AC-3
    import mlflow
    from mlflow.genai.utils.trace_utils import extract_retrieval_context_from_trace

    docs = [d.model_copy(deep=True) for d in documents]
    del docs[1].metadata["source_url"]
    retriever = GoldRetriever(docs, Settings(top_k=3))
    found = retriever.retrieve("storytelling rouquidão escuta")
    mlflow.flush_trace_async_logging()
    trace = mlflow.get_trace(mlflow.get_last_active_trace_id())
    (items,) = extract_retrieval_context_from_trace(trace).values()
    assert len(items) == len(found) == 3
    assert all(item["content"] for item in items)
    uris = {item["doc_uri"] for item in items}
    assert uris == {"https://example.org/a", "gold://doc-b", "https://example.org/c"}
    assert all("doc_uri" not in d.metadata for d in retriever.documents)
