"""Voz do avatar (spec 027): texto do mascote → áudio, com Piper local ou ElevenLabs.

- Piper (padrão, `TTS_PROVIDER`): roda no computador, nada sai da máquina; WAV.
- ElevenLabs (opcional, `TTS_PRESENTATION_PROVIDER` com `purpose="presentation"`): só o
  texto falado vai ao provedor, com o nome do perfil trocado por "você"; MP3.
- Cache em disco por provedor + parâmetros + texto; escrita atômica.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import logging
import os
import re
import tempfile
import wave
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import httpx

from rag_cognus import coach
from rag_cognus.config import Settings

log = logging.getLogger(__name__)

MAX_CHARS = 600
PURPOSES = ("tip", "explain", "presentation")
MEDIA = {"piper": ("audio/wav", ".wav"), "elevenlabs": ("audio/mpeg", ".mp3")}
UNAVAILABLE = "Voz indisponível agora: "
NOT_INSTALLED = "Voz local não instalada: rode `rag-cognus voice-download`."
NUMBERS_OUTSIDE = "Esse texto cita números que não estão nos fatos; não vou falar."

# A confirmar na doc oficial (https://elevenlabs.io/docs/api-reference/text-to-speech):
# rota, `output_format`, nome/faixa de `speed` e códigos de erro de cota.
ELEVEN_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
ELEVEN_FORMAT = "mp3_44100_128"


class VoiceUnavailable(RuntimeError):
    """Sem voz agora (provedor desligado, modelo ausente, erro do provedor) → 503."""


class InvalidText(ValueError):
    """Texto vazio, longo demais ou com número fora dos fatos → 422."""


@dataclass(frozen=True)
class VoiceResult:
    audio: bytes
    media_type: str
    provider: str
    cache_hit: bool


# ---------- texto ----------
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_LINE_MARK = re.compile(r"^\s*(?:#{1,6}|[-*+>]|\d+[.)])\s+", re.MULTILINE)
_INLINE_MARK = re.compile(r"[*_`~#>|]+")


def normalize_text(text: str) -> str:
    """Remove marcação (markdown) e normaliza espaços; valida 1..600 caracteres."""
    clean = _LINK.sub(r"\1", text or "")
    clean = _LINE_MARK.sub("", clean)
    clean = _INLINE_MARK.sub("", clean)
    clean = " ".join(clean.split())
    if not clean:
        raise InvalidText("O texto para falar está vazio.")
    if len(clean) > MAX_CHARS:
        raise InvalidText(f"O texto para falar passa de {MAX_CHARS} caracteres.")
    return clean


def anonymize(text: str, name: str | None) -> str:
    """Troca o nome do perfil (completo e primeiro nome) por "você" (spec 027 AC-4b)."""
    parts = [p for p in (name or "").split() if len(p) >= 3]
    candidates = [" ".join((name or "").split())] + parts[:1]
    for candidate in filter(None, dict.fromkeys(candidates)):
        pattern = re.compile(rf"(?<!\w){re.escape(candidate)}(?!\w)", re.IGNORECASE)
        text = pattern.sub(lambda m: _voce(m.string, m.start()), text)
    return text


def _voce(text: str, start: int) -> str:
    before = text[:start].rstrip()
    return "Você" if not before or before[-1] in ".!?" else "você"


# ---------- provedores ----------
def _chosen(settings: Settings, purpose: str) -> str:
    if purpose == "presentation":
        return settings.tts_presentation_provider
    return settings.tts_provider


def _eleven_ready(settings: Settings) -> bool:
    return bool(settings.elevenlabs_api_key and settings.elevenlabs_voice_id)


def provider_for(settings: Settings, purpose: str = "tip") -> str:
    """Provedor configurado para o propósito; ElevenLabs sem chave/voz cai para o Piper."""
    chosen = _chosen(settings, purpose)
    if chosen == "elevenlabs" and not _eleven_ready(settings):
        return "piper"
    return chosen


def piper_model_path(settings: Settings) -> Path:
    return Path(settings.piper_data_dir) / f"{settings.piper_voice}.onnx"


def _piper_model_ready(settings: Settings) -> bool:
    path = piper_model_path(settings)
    return path.is_file() and path.with_name(path.name + ".json").is_file()


def _piper_installed() -> bool:
    return importlib.util.find_spec("piper") is not None


def voice_status(settings: Settings) -> dict:
    """Campos de voz do /v1/health: só configuração e arquivos em disco, sem sintetizar."""
    piper_ok = _piper_model_ready(settings) and _piper_installed()

    def effective(purpose: str) -> str:
        provider = provider_for(settings, purpose)
        return "off" if provider == "piper" and not piper_ok else provider

    provider = effective("tip")
    return {
        "voice_available": provider != "off",
        "voice_provider": provider,
        "presentation_voice_provider": effective("presentation"),
    }


def _piper_config(settings: Settings) -> dict:
    return {
        "length_scale": settings.piper_length_scale,
        "noise_scale": settings.piper_noise_scale,
        "noise_w_scale": settings.piper_noise_w,
    }


def _eleven_body(settings: Settings, text: str) -> dict:
    return {
        "text": text,
        "model_id": settings.elevenlabs_model,
        "voice_settings": {
            "stability": settings.elevenlabs_stability,
            "similarity_boost": settings.elevenlabs_similarity,
            "style": settings.elevenlabs_style,
            "use_speaker_boost": True,
            "speed": settings.elevenlabs_speed,  # a confirmar na doc (nome e faixa)
        },
    }


@lru_cache(maxsize=2)
def _load_piper(model_path: str):
    from piper import PiperVoice  # import preguiçoso: extra `voice` opcional

    return PiperVoice.load(model_path)


def _piper_synthesize(model_path: Path, text: str, cfg: dict) -> bytes:
    """Adaptador fino do `piper-tts` (OHF-Voice/piper1-gpl): texto → WAV mono 16 bits."""
    try:
        from piper import SynthesisConfig
    except ImportError:
        raise VoiceUnavailable(
            "Voz local não instalada: instale o extra `voice` e rode `rag-cognus voice-download`."
        ) from None
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        _load_piper(str(model_path)).synthesize_wav(
            text, wav_file, syn_config=SynthesisConfig(**cfg)
        )
    return buffer.getvalue()


def _http_client(settings: Settings) -> httpx.Client:
    return httpx.Client(timeout=settings.tts_timeout)


def _eleven_synthesize(settings: Settings, body: dict) -> bytes:
    url = ELEVEN_URL.format(voice_id=settings.elevenlabs_voice_id)
    headers = {"xi-api-key": settings.elevenlabs_api_key, "Accept": "audio/mpeg"}
    try:
        with _http_client(settings) as client:
            response = client.post(
                url, params={"output_format": ELEVEN_FORMAT}, json=body, headers=headers
            )
    except httpx.TimeoutException:
        raise VoiceUnavailable(
            UNAVAILABLE + "o ElevenLabs demorou demais para responder."
        ) from None
    except httpx.HTTPError:
        raise VoiceUnavailable(UNAVAILABLE + "sem conexão com o ElevenLabs.") from None
    # A confirmar na doc: cota esgotada do plano gratuito pode vir como 401 "quota_exceeded".
    if response.status_code == 401:
        raise VoiceUnavailable(UNAVAILABLE + "chave do ElevenLabs recusada ou cota esgotada.")
    if response.status_code == 429:
        raise VoiceUnavailable(UNAVAILABLE + "limite do ElevenLabs atingido.")
    if response.status_code >= 400:
        raise VoiceUnavailable(UNAVAILABLE + f"o ElevenLabs respondeu erro {response.status_code}.")
    if not response.headers.get("content-type", "").startswith("audio/") or not response.content:
        raise VoiceUnavailable(UNAVAILABLE + "a resposta do ElevenLabs não é áudio.")
    return response.content


# ---------- cache ----------
def _cache_path(settings: Settings, provider: str, params: dict, text: str) -> Path:
    raw = f"{provider}|{json.dumps(params, sort_keys=True, ensure_ascii=False)}|{text}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return Path(settings.voice_cache_dir) / (digest + MEDIA[provider][1])


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


# ---------- entrada pública ----------
def synthesize(
    settings: Settings,
    text: str,
    *,
    purpose: str = "tip",
    facts: list[dict] | None = None,
    profile_name: str | None = None,
) -> VoiceResult:
    """Fala `text`. Levanta `InvalidText` (422) ou `VoiceUnavailable` (503)."""
    if purpose not in PURPOSES:
        raise InvalidText(f"purpose deve ser um de {', '.join(PURPOSES)}.")
    clean = normalize_text(text)
    if purpose == "explain":
        allowed = " ".join(f"{f.get('label', '')} {f.get('value', '')}" for f in facts or [])
        if not coach.grounded(clean, allowed):
            raise InvalidText(NUMBERS_OUTSIDE)
    provider = provider_for(settings, purpose)
    if provider == "off":
        raise VoiceUnavailable(UNAVAILABLE + "a voz está desligada na configuração.")
    if provider == "piper":
        params = {"voice": settings.piper_voice, **_piper_config(settings)}
        sent = clean
    else:
        sent = anonymize(clean, profile_name)
        body = _eleven_body(settings, sent)
        params = {"voice": settings.elevenlabs_voice_id, "model": body["model_id"]}
        params["voice_settings"] = body["voice_settings"]
    path = _cache_path(settings, provider, params, sent)
    media_type = MEDIA[provider][0]
    if path.is_file():
        return VoiceResult(path.read_bytes(), media_type, provider, True)
    if provider == "piper":
        if not _piper_model_ready(settings):
            raise VoiceUnavailable(NOT_INSTALLED)
        try:
            audio = _piper_synthesize(piper_model_path(settings), sent, _piper_config(settings))
        except VoiceUnavailable:
            raise
        except Exception as exc:
            log.warning("Piper falhou: %s", type(exc).__name__)
            raise VoiceUnavailable(UNAVAILABLE + "a voz local falhou ao gerar o áudio.") from exc
        if not audio:
            raise VoiceUnavailable(UNAVAILABLE + "a voz local não gerou áudio.")
    else:
        audio = _eleven_synthesize(settings, body)
    _write_atomic(path, audio)
    return VoiceResult(audio, media_type, provider, False)
