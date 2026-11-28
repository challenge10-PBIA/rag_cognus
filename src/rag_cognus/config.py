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
    chat_model: str = "eriktonon/deepseek-v4.1-flash-1017:latest"
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
    # ID do experimento (spec 036): preenchido, tem precedência sobre o nome.
    experiment_id: str = ""
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
    # Voz do avatar (spec 027): Piper local no dia a dia, ElevenLabs opcional na apresentação.
    tts_provider: str = "piper"
    tts_presentation_provider: str = "elevenlabs"
    piper_voice: str = "pt_BR-faber-medium"
    piper_data_dir: str = ".cache/piper"
    piper_length_scale: float = 1.1  # > 1 = mais lento e calmo
    piper_noise_scale: float | None = None  # None = padrão do modelo/lib
    piper_noise_w: float | None = None
    elevenlabs_api_key: str = field(default="", repr=False)  # nunca aparece em logs/repr
    elevenlabs_voice_id: str = ""
    elevenlabs_model: str = "eleven_multilingual_v2"
    elevenlabs_stability: float = 0.65
    elevenlabs_similarity: float = 0.75
    elevenlabs_style: float = 0.0
    elevenlabs_speed: float = 0.95
    tts_timeout: float = 20.0
    voice_cache_dir: str = ".cache/voice"

    def __post_init__(self):
        qualified_name(self.gold_view)
        if self.backend not in {"bm25", "dense"} or self.top_k < 1:
            raise ValueError("Backend deve ser bm25/dense; top_k deve ser positivo.")
        if self.num_ctx < 2048:
            raise ValueError("num_ctx (OLLAMA_NUM_CTX) deve ser pelo menos 2048.")
        _validate_llm(self)
        _validate_voice(self)
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
            experiment_id=os.getenv("MLFLOW_EXPERIMENT_ID", "").strip(),
            online_experiment=os.getenv("MLFLOW_ONLINE_EXPERIMENT") or cls.online_experiment,
            online_eval=env_flag("RAG_ONLINE_EVAL", cls.online_eval),
            speech_pleonasm_llm=env_flag("SPEECH_PLEONASM_LLM", cls.speech_pleonasm_llm),
            **{name: value for name in LLM_ENV if (value := _env_llm(name)) is not None},
            **_voice_from_env(),
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


TTS_PROVIDERS = ("piper", "elevenlabs", "off")
# Campo do Settings -> (variável do .env, mínimo, máximo); vazio = padrão do Settings.
VOICE_RANGES = {
    "piper_length_scale": ("PIPER_LENGTH_SCALE", 0.5, 2.0),
    "piper_noise_scale": ("PIPER_NOISE_SCALE", 0.0, 1.5),
    "piper_noise_w": ("PIPER_NOISE_W", 0.0, 1.5),
    "elevenlabs_stability": ("ELEVENLABS_STABILITY", 0.0, 1.0),
    "elevenlabs_similarity": ("ELEVENLABS_SIMILARITY", 0.0, 1.0),
    "elevenlabs_style": ("ELEVENLABS_STYLE", 0.0, 1.0),
    # Faixa de `speed` a confirmar na doc do ElevenLabs (spec 027).
    "elevenlabs_speed": ("ELEVENLABS_SPEED", 0.7, 1.2),
}
VOICE_TEXT_ENV = {
    "tts_provider": "TTS_PROVIDER",
    "tts_presentation_provider": "TTS_PRESENTATION_PROVIDER",
    "piper_voice": "PIPER_VOICE",
    "piper_data_dir": "PIPER_DATA_DIR",
    "elevenlabs_api_key": "ELEVENLABS_API_KEY",
    "elevenlabs_voice_id": "ELEVENLABS_VOICE_ID",
    "elevenlabs_model": "ELEVENLABS_MODEL",
    "voice_cache_dir": "VOICE_CACHE_DIR",
}


def _voice_from_env() -> dict:
    values = {}
    for name, env in VOICE_TEXT_ENV.items():
        if raw := (os.getenv(env) or "").strip():
            values[name] = raw.lower() if name.startswith("tts_") else raw
    for name, env in {
        **{k: v[0] for k, v in VOICE_RANGES.items()},
        "tts_timeout": "TTS_TIMEOUT",
    }.items():
        if raw := (os.getenv(env) or "").strip():
            try:
                values[name] = float(raw)
            except ValueError:
                raise ValueError(f"{env} deve ser um número (recebido {raw!r}).") from None
    return values


def _validate_voice(s: Settings) -> None:
    for name, env in (
        ("tts_provider", "TTS_PROVIDER"),
        ("tts_presentation_provider", "TTS_PRESENTATION_PROVIDER"),
    ):
        if getattr(s, name) not in TTS_PROVIDERS:
            raise ValueError(
                f"{env} deve ser piper, elevenlabs ou off (recebido {getattr(s, name)!r})."
            )
    for name, (env, low, high) in VOICE_RANGES.items():
        value = getattr(s, name)
        if value is not None and not low <= value <= high:
            raise ValueError(f"{env} deve estar entre {low:g} e {high:g}.")
    if s.tts_timeout <= 0:
        raise ValueError("TTS_TIMEOUT deve ser maior que 0 (segundos).")


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
