import io
import wave
from types import SimpleNamespace as NS

import numpy as np
import pytest

from rag_cognus import speech


def make_wav(rate=16000, seconds=0.5, channels=1):
    frames = (np.sin(np.linspace(0, 200, int(rate * seconds))) * 10000).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(np.repeat(frames, channels).tobytes())
    return buffer.getvalue()


class FakeWhisper:
    def __init__(self, texts):
        self.texts = texts
        self.audio = None
        self.kwargs = None

    def transcribe(self, audio, **kwargs):
        self.audio, self.kwargs = audio, kwargs
        return (NS(text=t) for t in self.texts), NS(language="pt")


def test_transcription_joins_segments_in_portuguese():
    model = FakeWhisper(["  Como falar ", "em público? "])
    assert speech.transcribe(model, make_wav()) == "Como falar em público?"
    assert model.kwargs["language"] == "pt"
    assert model.audio.dtype == np.float32 and len(model.audio) == 8000


def test_stereo_44khz_is_converted_to_mono_16khz():
    audio = speech.wav_to_array(make_wav(rate=44100, seconds=1, channels=2))
    assert audio.ndim == 1 and abs(len(audio) - 16000) <= 1
    assert np.abs(audio).max() <= 1


def test_empty_invalid_or_silent_audio_gives_clear_error():
    with pytest.raises(ValueError, match="vazio"):
        speech.transcribe(FakeWhisper(["x"]), b"")
    with pytest.raises(ValueError, match="inválido"):
        speech.transcribe(FakeWhisper(["x"]), b"nao-e-wav")
    with pytest.raises(ValueError, match="Não entendi"):
        speech.transcribe(FakeWhisper(["  "]), make_wav())
