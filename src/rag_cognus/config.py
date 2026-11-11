from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

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
    host: str = ""
    token: str = field(default="", repr=False)  # nunca aparece em logs/repr
    warehouse_id: str = ""
    ollama_url: str = "http://127.0.0.1:11434"
    chat_model: str = "qwen3.5:9b"
    embed_model: str = "embeddinggemma:latest"
    backend: str = "bm25"
    top_k: int = 5
    dense_min_score: float = 0.3
    judge_model: str = ""
    # Porta 5001: no macOS a 5000 é ocupada pelo AirPlay Receiver.
    tracking_uri: str = "http://127.0.0.1:5001"
    experiment: str = "rag-cognus"

    def __post_init__(self):
        qualified_name(self.gold_view)
        if self.backend not in {"bm25", "dense"} or self.top_k < 1:
            raise ValueError("Backend deve ser bm25/dense; top_k deve ser positivo.")
        ensure_local_tracking(self.tracking_uri)

    @property
    def databricks_auth(self) -> str:
        """'token' quando host e token estão no .env; senão o perfil OAuth."""
        if bool(self.host) != bool(self.token):
            raise ValueError("Preencha DATABRICKS_HOST e DATABRICKS_TOKEN juntos (ou nenhum).")
        return "token" if self.host else "profile"

    @property
    def judge(self) -> str:
        return self.judge_model or self.chat_model

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            gold_view=os.getenv("GOLD_VIEW", cls.gold_view),
            profile=os.getenv("DATABRICKS_CONFIG_PROFILE", cls.profile),
            host=os.getenv("DATABRICKS_HOST", ""),
            token=os.getenv("DATABRICKS_TOKEN", ""),
            warehouse_id=os.getenv("DATABRICKS_WAREHOUSE_ID", ""),
            ollama_url=os.getenv("OLLAMA_BASE_URL", cls.ollama_url),
            chat_model=os.getenv("OLLAMA_CHAT_MODEL", cls.chat_model),
            embed_model=os.getenv("OLLAMA_EMBED_MODEL", cls.embed_model),
            backend=os.getenv("RAG_RETRIEVER", cls.backend),
            top_k=int(os.getenv("RAG_TOP_K", cls.top_k)),
            dense_min_score=float(os.getenv("RAG_DENSE_MIN_SCORE", cls.dense_min_score)),
            judge_model=os.getenv("OLLAMA_JUDGE_MODEL", ""),
            tracking_uri=os.getenv("MLFLOW_TRACKING_URI") or cls.tracking_uri,
            experiment=os.getenv("MLFLOW_EXPERIMENT_NAME", cls.experiment),
        )


def ensure_local_tracking(uri: str) -> str:
    """Aceita só o MLflow open source local (servidor em loopback, sqlite ou pasta)."""
    parsed = urlparse(uri)
    local_server = parsed.scheme in {"http", "https"} and parsed.hostname in {
        "127.0.0.1",
        "localhost",
        "::1",
    }
    if local_server or parsed.scheme in {"sqlite", "file", ""}:
        return uri
    raise ValueError(
        f"MLFLOW_TRACKING_URI={uri!r} não é um MLflow local. Este projeto usa o MLflow "
        "open source: rode `rag-cognus mlflow-local` e use http://127.0.0.1:5001."
    )
