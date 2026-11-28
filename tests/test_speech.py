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


def test_install_hint_points_to_project_venv():
    assert ".venv" in speech.INSTALL_HINT
    assert "source .venv/bin/activate" in speech.INSTALL_HINT
    assert "python -m pip install -e '.[audio]'" in speech.INSTALL_HINT


# ---------- spec 032: áudio comprimido do app mobile ----------
def make_m4a(seconds=1.0, rate=44100):
    av = pytest.importorskip("av")
    buffer = io.BytesIO()
    with av.open(buffer, "w", format="ipod") as out:  # "ipod" = contêiner .m4a
        stream = out.add_stream("aac", rate=rate)
        stream.layout = "mono"
        t = np.arange(int(rate * seconds)) / rate
        samples = (np.sin(2 * np.pi * 220 * t) * 0.3).astype(np.float32).reshape(1, -1)
        frame = av.AudioFrame.from_ndarray(samples, format="fltp", layout="mono")
        frame.sample_rate = rate
        for packet in stream.encode(frame):
            out.mux(packet)
        for packet in stream.encode(None):
            out.mux(packet)
    return buffer.getvalue()


def test_to_wav_keeps_wav_untouched():  # spec 032 AC-6
    original = make_wav(rate=44100, channels=2)
    assert speech.to_wav(original) == original
    assert speech.to_wav(b"") == b""


def test_to_wav_decodes_m4a_to_pcm16_mono_16k():  # spec 032 AC-5
    converted = speech.to_wav(make_m4a(seconds=1.0))
    with wave.open(io.BytesIO(converted)) as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (1, 2, 16000)
        assert 0.9 < wav.getnframes() / 16000 < 1.2


def test_to_wav_rejects_garbage_in_portuguese():  # spec 032 AC-6
    with pytest.raises(ValueError, match="formato não suportado"):
        speech.to_wav(b"isto nao e audio" * 50)
