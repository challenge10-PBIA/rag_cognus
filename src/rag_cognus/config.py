from __future__ import annotations

import os
import re
from dataclasses import dataclass

NICHOS = (
    "apresentacoes_oratoria",
    "assertividade_escuta",
    "clareza_linguagem",
    "voz_saude_vocal",
    "fluencia_gagueira",
    "fono_contextos_profissionais",
)


def qualified_name(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_]\w*\.[A-Za-z_]\w*\.[A-Za-z_]\w*", value):
        raise ValueError("Informe um nome catalogo.schema.objeto, sem SQL adicional.")
    return value


@dataclass(frozen=True)
class Settings:
    gold_view: str = "cognus.gold.vw_rag_conhecimento"
    profile: str = "projeto"
    warehouse_id: str = ""
    ollama_url: str = "http://127.0.0.1:11434"
    chat_model: str = "qwen3.5:9b"
    embed_model: str = "embeddinggemma:latest"
    backend: str = "bm25"
    top_k: int = 5
    dense_min_score: float = 0.3
    tracking_uri: str = "sqlite:///mlflow.db"
    experiment: str = "rag-cognus"

    def __post_init__(self):
        qualified_name(self.gold_view)
        if self.backend not in {"bm25", "dense"} or self.top_k < 1:
            raise ValueError("Backend deve ser bm25/dense; top_k deve ser positivo.")

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            gold_view=os.getenv("GOLD_VIEW", cls.gold_view),
            profile=os.getenv("DATABRICKS_CONFIG_PROFILE", cls.profile),
            warehouse_id=os.getenv("DATABRICKS_WAREHOUSE_ID", ""),
            ollama_url=os.getenv("OLLAMA_BASE_URL", cls.ollama_url),
            chat_model=os.getenv("OLLAMA_CHAT_MODEL", cls.chat_model),
            embed_model=os.getenv("OLLAMA_EMBED_MODEL", cls.embed_model),
            backend=os.getenv("RAG_RETRIEVER", cls.backend),
            top_k=int(os.getenv("RAG_TOP_K", cls.top_k)),
            dense_min_score=float(os.getenv("RAG_DENSE_MIN_SCORE", cls.dense_min_score)),
            tracking_uri=os.getenv("MLFLOW_TRACKING_URI", cls.tracking_uri),
            experiment=os.getenv("MLFLOW_EXPERIMENT_NAME", cls.experiment),
        )
