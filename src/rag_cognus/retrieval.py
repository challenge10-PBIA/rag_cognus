from __future__ import annotations

import json
import re
import time
import unicodedata

import mlflow
from langchain_core.documents import Document
from mlflow.entities import Document as TraceDocument

from rag_cognus.config import NICHOS, Settings

STOP_WORDS = set(
    [
        "a",
        "o",
        "as",
        "os",
        "um",
        "uma",
        "uns",
        "umas",
        "de",
        "do",
        "da",
        "dos",
        "das",
        "em",
        "no",
        "na",
        "nos",
        "nas",
        "e",
        "ou",
        "para",
        "por",
        "com",
        "que",
        "qual",
        "quais",
        "como",
        "se",
        "ao",
        "aos",
        "sobre",
        "ser",
        "ter",
        "esse",
        "essa",
        "isso",
    ]
)


def tokenize(text: str) -> list[str]:
    plain = "".join(
        c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c)
    )
    return [t for t in re.findall(r"\b\w+\b", plain) if t not in STOP_WORDS]


def has_niche(document: Document, niche: str | None) -> bool:
    return niche is None or niche in json.loads(document.metadata.get("nichos_json", "[]"))


class GoldRetriever:
    """Pré-filtro de nicho; BM25 ou similaridade cosseno via Ollama/LangChain."""

    def __init__(self, documents: list[Document], settings: Settings, embeddings=None):
        started = time.perf_counter()
        if not documents:
            raise ValueError("Índice vazio.")
        self.documents = sorted(documents, key=lambda d: d.metadata["chunk_id"])
        self.settings = settings
        self._store = None
        self._bm25 = None
        if settings.backend == "dense":
            from langchain_core.vectorstores import InMemoryVectorStore
            from langchain_ollama import OllamaEmbeddings

            embedder = embeddings or OllamaEmbeddings(
                model=settings.embed_model,
                base_url=settings.ollama_url,
            )
            self._store = InMemoryVectorStore(embedding=embedder)
            # O tokenizer do servidor local pode falhar em requisições muito grandes.
            for start in range(0, len(self.documents), 16):
                batch = self.documents[start : start + 16]
                self._store.add_documents(batch, ids=[d.metadata["chunk_id"] for d in batch])
        else:
            from rank_bm25 import BM25Okapi

            self._bm25 = BM25Okapi(
                [tokenize(d.page_content) or ["__vazio__"] for d in self.documents]
            )
        self.build_seconds = time.perf_counter() - started

    def search(self, query: str, niche: str | None = None, k: int | None = None) -> list[Document]:
        if niche is not None and niche not in NICHOS:
            raise ValueError("Nicho desconhecido.")
        k = self.settings.top_k if k is None else k
        if k < 1:
            raise ValueError("k deve ser positivo.")
        if not query.strip() or not tokenize(query):
            return []
        if self._store is not None:
            hits = self._store.similarity_search_with_score(
                query,
                k=k,
                filter=lambda d: has_niche(d, niche),
            )
            return [doc for doc, score in hits if score >= self.settings.dense_min_score]
        scores = self._bm25.get_scores(tokenize(query))
        ranked = sorted(
            zip(self.documents, scores, strict=True),
            key=lambda pair: (-float(pair[1]), pair[0].metadata["chunk_id"]),
        )
        return [doc for doc, score in ranked if score > 0 and has_niche(doc, niche)][:k]

    @mlflow.trace(name="retrieve_gold", span_type="RETRIEVER")
    def retrieve(self, query: str, niche: str | None = None) -> list[TraceDocument]:
        return [
            TraceDocument(
                id=d.metadata["chunk_id"], page_content=d.page_content, metadata=d.metadata
            )
            for d in self.search(query, niche)
        ]
