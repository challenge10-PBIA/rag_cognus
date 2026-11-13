"""Transcrição local de perguntas faladas (faster-whisper, sem enviar áudio para fora)."""

from __future__ import annotations

import importlib.util
import io
import wave

import numpy as np

from rag_cognus.config import Settings

INSTALL_HINT = "Para perguntar por voz, instale: pip install -e '.[audio]'"


def available() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


def load_transcriber(settings: Settings):
    """Carrega o Whisper local. O modelo é baixado na primeira vez."""
    from faster_whisper import WhisperModel

    return WhisperModel(settings.whisper_model, device="cpu", compute_type="int8")


WHISPER_RATE = 16000


def wav_to_array(wav_bytes: bytes) -> np.ndarray:
    """WAV PCM 16-bit -> float32 mono 16 kHz, sem depender do decodificador `av`."""
    with wave.open(io.BytesIO(wav_bytes)) as wav:
        if wav.getsampwidth() != 2:
            raise ValueError("Formato de áudio não suportado: use WAV PCM 16-bit.")
        rate, channels = wav.getframerate(), wav.getnchannels()
        samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")
    audio = samples.reshape(-1, channels).mean(axis=1).astype(np.float32) / 32768
    if rate != WHISPER_RATE and len(audio):
        positions = np.linspace(0, len(audio) - 1, int(len(audio) * WHISPER_RATE / rate))
        audio = np.interp(positions, np.arange(len(audio)), audio).astype(np.float32)
    return audio


def transcribe(model, wav_bytes: bytes) -> str:
    if not wav_bytes:
        raise ValueError("Áudio vazio: grave a pergunta novamente.")
    try:
        audio = wav_to_array(wav_bytes)
    except (wave.Error, EOFError) as exc:
        raise ValueError(f"Áudio inválido: {exc}") from exc
    segments, _ = model.transcribe(audio, language="pt", vad_filter=True)
    text = " ".join(s.text.strip() for s in segments).strip()
    if not text:
        raise ValueError("Não entendi o áudio. Fale mais perto do microfone e tente de novo.")
    return text
