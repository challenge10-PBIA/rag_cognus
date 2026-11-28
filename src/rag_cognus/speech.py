"""Transcrição local de perguntas faladas (faster-whisper, sem enviar áudio para fora)."""

from __future__ import annotations

import io
import wave

import numpy as np

from rag_cognus.config import Settings

INSTALL_HINT = (
    "Para perguntar por voz, ative o venv do projeto e rode: "
    "source .venv/bin/activate && python -m pip install -e '.[audio]'"
)


def available() -> bool:
    try:
        import faster_whisper  # noqa: F401
    except Exception:
        return False
    return True


def load_transcriber(settings: Settings):
    """Carrega o Whisper local. O modelo é baixado na primeira vez."""
    try:
        from faster_whisper import WhisperModel
    except ModuleNotFoundError as exc:
        raise RuntimeError(INSTALL_HINT) from exc
    return WhisperModel(settings.whisper_model, device="cpu", compute_type="int8")


WHISPER_RATE = 16000


UNSUPPORTED = "Áudio inválido ou formato não suportado: envie WAV, M4A/AAC, WebM ou 3GP."


def to_wav(data: bytes) -> bytes:
    """Áudio comprimido (M4A/AAC, WebM, 3GP...) -> WAV PCM 16-bit mono 16 kHz (spec 032).

    WAV passa intacto; vazio continua vazio para as mensagens de "Áudio vazio".
    """
    if not data or data[:4] == b"RIFF":
        return data
    try:
        import av
    except ModuleNotFoundError as exc:
        raise ValueError(UNSUPPORTED) from exc
    chunks = []
    try:
        with av.open(io.BytesIO(data)) as container:
            if not container.streams.audio:
                raise ValueError(UNSUPPORTED)
            resampler = av.AudioResampler(format="s16", layout="mono", rate=WHISPER_RATE)
            for frame in container.decode(audio=0):
                chunks += [f.to_ndarray().tobytes() for f in resampler.resample(frame)]
            chunks += [f.to_ndarray().tobytes() for f in resampler.resample(None)]
    except av.FFmpegError as exc:
        raise ValueError(UNSUPPORTED) from exc
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(WHISPER_RATE)
        wav.writeframes(b"".join(chunks))
    return buffer.getvalue()


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


# Sem contexto, o Whisper "limpa" hesitações; um prompt com vícios o leva a transcrevê-los.
VERBATIM_PROMPT = "Ééé, então, tipo, né, hum... é que, hã, eu acho que, tipo assim."


def transcribe_words(model, wav_bytes: bytes) -> dict:
    """Transcrição literal com timestamps por palavra (para as métricas da sessão)."""
    if not wav_bytes:
        raise ValueError("Áudio vazio: grave novamente.")
    try:
        audio = wav_to_array(wav_bytes)
    except (wave.Error, EOFError) as exc:
        raise ValueError(f"Áudio inválido: {exc}") from exc
    segments, _ = model.transcribe(
        audio,
        language="pt",
        vad_filter=True,
        word_timestamps=True,
        initial_prompt=VERBATIM_PROMPT,
        condition_on_previous_text=False,
    )
    words, texts = [], []
    for segment in segments:
        texts.append(segment.text.strip())
        for w in segment.words or []:
            if w.word.strip():
                words.append(
                    {
                        "word": w.word.strip(),
                        "start": float(w.start),
                        "end": float(w.end),
                        "probability": float(w.probability),
                    }
                )
    return {
        "text": " ".join(t for t in texts if t),
        "words": words,
        "audio": audio,
        "duration": len(audio) / WHISPER_RATE,
    }
