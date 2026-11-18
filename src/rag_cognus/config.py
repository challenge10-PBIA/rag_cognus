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
    whisper_model: str = "small"
    # Mesmo num_ctx em todas as chamadas de um modelo: valores diferentes recarregam o Ollama.
    num_ctx: int = 16384
    keep_alive: str = "30m"
    fast_model: str = ""  # etapas simples dos agentes; vazio = chat_model
    # Porta 5001: no macOS a 5000 é ocupada pelo AirPlay Receiver.
    tracking_uri: str = "http://127.0.0.1:5001"
    experiment: str = "rag-cognus"
    # Avaliação online de cada /v1/ask (spec 004): juiz em segundo plano → MLflow local.
    online_experiment: str = "rag-cognus-online"
    online_eval: bool = True
    # Pleonasmos com LLM além das regras (spec 003); desligado por padrão (latência).
    speech_pleonasm_llm: bool = False
    # Opções do LLM por papel (spec 010). None = não envia: vale o Modelfile do modelo.
    temperature: float = 0.0
    judge_temperature: float = 0.0
    fast_temperature: float = 0.0
    seed: int | None = None
    top_p: float | None = None
    llm_top_k: int | None = None  # top_k da amostragem (OLLAMA_TOP_K), não o RAG_TOP_K
    repeat_penalty: float | None = None
    presence_penalty: float | None = None
    judge_presence_penalty: float | None = None  # None = presence_penalty
    generator_num_predict: int | None = None  # None = padrão de cada chamada
    judge_num_predict: int | None = None
    fast_num_predict: int | None = None
    think: bool = False
    judge_think: bool = False
    judge_num_ctx: int | None = None  # só vale se o juiz usar outro modelo
    fast_num_ctx: int | None = None
    timeout: float = 300.0

    def __post_init__(self):
        qualified_name(self.gold_view)
        if self.backend not in {"bm25", "dense"} or self.top_k < 1:
            raise ValueError("Backend deve ser bm25/dense; top_k deve ser positivo.")
        if self.num_ctx < 2048:
            raise ValueError("num_ctx (OLLAMA_NUM_CTX) deve ser pelo menos 2048.")
        _validate_llm(self)
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

    @property
    def fast(self) -> str:
        return self.fast_model or self.chat_model

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
            whisper_model=os.getenv("WHISPER_MODEL") or cls.whisper_model,
            num_ctx=int(os.getenv("OLLAMA_NUM_CTX") or cls.num_ctx),
            keep_alive=os.getenv("OLLAMA_KEEP_ALIVE") or cls.keep_alive,
            fast_model=os.getenv("OLLAMA_FAST_MODEL", ""),
            tracking_uri=os.getenv("MLFLOW_TRACKING_URI") or cls.tracking_uri,
            experiment=os.getenv("MLFLOW_EXPERIMENT_NAME", cls.experiment),
            online_experiment=os.getenv("MLFLOW_ONLINE_EXPERIMENT") or cls.online_experiment,
            online_eval=env_flag("RAG_ONLINE_EVAL", cls.online_eval),
            speech_pleonasm_llm=env_flag("SPEECH_PLEONASM_LLM", cls.speech_pleonasm_llm),
            **{name: value for name in LLM_ENV if (value := _env_llm(name)) is not None},
        )


# Campo do Settings -> variável do .env (spec 010). Vazio = padrão do Settings.
LLM_ENV = {
    "temperature": "OLLAMA_TEMPERATURE",
    "judge_temperature": "OLLAMA_JUDGE_TEMPERATURE",
    "fast_temperature": "OLLAMA_FAST_TEMPERATURE",
    "seed": "OLLAMA_SEED",
    "top_p": "OLLAMA_TOP_P",
    "llm_top_k": "OLLAMA_TOP_K",
    "repeat_penalty": "OLLAMA_REPEAT_PENALTY",
    "presence_penalty": "OLLAMA_PRESENCE_PENALTY",
    "judge_presence_penalty": "OLLAMA_JUDGE_PRESENCE_PENALTY",
    "generator_num_predict": "OLLAMA_GENERATOR_NUM_PREDICT",
    "judge_num_predict": "OLLAMA_JUDGE_NUM_PREDICT",
    "fast_num_predict": "OLLAMA_FAST_NUM_PREDICT",
    "think": "OLLAMA_THINK",
    "judge_think": "OLLAMA_JUDGE_THINK",
    "judge_num_ctx": "OLLAMA_JUDGE_NUM_CTX",
    "fast_num_ctx": "OLLAMA_FAST_NUM_CTX",
    "timeout": "OLLAMA_TIMEOUT",
}
_INT_FIELDS = {
    "seed",
    "llm_top_k",
    "generator_num_predict",
    "judge_num_predict",
    "fast_num_predict",
}
_INT_FIELDS |= {"judge_num_ctx", "fast_num_ctx"}


def _env_llm(field_name: str):
    """Valor tipado de uma variável do LLM; None quando vazia."""
    name = LLM_ENV[field_name]
    raw = (os.getenv(name) or "").strip()
    if field_name in {"think", "judge_think"}:
        return env_flag(name, False) if raw else None
    if not raw:
        return None
    try:
        return int(raw) if field_name in _INT_FIELDS else float(raw)
    except ValueError:
        kind = "inteiro" if field_name in _INT_FIELDS else "número"
        raise ValueError(f"{name} deve ser um {kind} (recebido {raw!r}).") from None


def _validate_llm(s: Settings) -> None:
    for name in ("temperature", "judge_temperature", "fast_temperature"):
        if not 0 <= getattr(s, name) <= 2:
            raise ValueError(f"{LLM_ENV[name]} deve estar entre 0 e 2.")
    if s.top_p is not None and not 0 < s.top_p <= 1:
        raise ValueError("OLLAMA_TOP_P deve ser maior que 0 e no máximo 1.")
    for name in ("generator_num_predict", "judge_num_predict", "fast_num_predict"):
        value = getattr(s, name)
        if value is not None and value < 64:
            raise ValueError(f"{LLM_ENV[name]} deve ser pelo menos 64 (o JSON seria cortado).")
    for name in ("judge_num_ctx", "fast_num_ctx"):
        value = getattr(s, name)
        if value is not None and value < 2048:
            raise ValueError(f"{LLM_ENV[name]} deve ser pelo menos 2048.")
    if s.timeout <= 0:
        raise ValueError("OLLAMA_TIMEOUT deve ser maior que 0 (segundos).")


_TRUE = {"1", "true", "yes", "sim", "on"}
_FALSE = {"0", "false", "no", "nao", "não", "off"}


def env_flag(name: str, default: bool) -> bool:
    """Lê um booleano do ambiente; vazio = padrão, valor desconhecido = erro claro."""
    value = (os.getenv(name) or "").strip().lower()
    if not value:
        return default
    if value in _TRUE | _FALSE:
        return value in _TRUE
    raise ValueError(f"{name} deve ser true ou false (recebido {value!r}).")


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
