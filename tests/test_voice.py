"""Spec 027 — voz do avatar (Piper local + ElevenLabs opcional). Sem rede e sem Piper real."""

import json
from dataclasses import replace

import httpx
import pytest

from rag_cognus import voice
from rag_cognus.config import Settings

ELEVEN_HOST = "api.elevenlabs.io"


def settings(tmp_path, **kw):
    base = Settings(voice_cache_dir=str(tmp_path / "voice"), piper_data_dir=str(tmp_path / "piper"))
    return replace(base, **kw)


def install_model(s):
    path = voice.piper_model_path(s)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"onnx")
    path.with_name(path.name + ".json").write_text("{}")
    return path


class FakePiper:
    def __init__(self, fail=None):
        self.calls, self.fail = [], fail

    def __call__(self, model_path, text, cfg):
        if self.fail:
            raise self.fail
        self.calls.append((model_path, text, cfg))
        return b"RIFF....WAVEfake"


@pytest.fixture
def piper(monkeypatch):
    fake = FakePiper()
    monkeypatch.setattr(voice, "_piper_synthesize", fake)
    return fake


class FakeEleven:
    """Transporte httpx falso: falha o teste se receber URL fora do ElevenLabs/voz esperada."""

    def __init__(self, voice_id="voz-calma", status=200, content_type="audio/mpeg", exc=None):
        self.requests, self.voice_id = [], voice_id
        self.status, self.content_type, self.exc = status, content_type, exc

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.url.host == ELEVEN_HOST, f"URL inesperada: {request.url}"
        assert request.url.path == f"/v1/text-to-speech/{self.voice_id}", request.url
        self.requests.append(request)
        if self.exc:
            raise self.exc
        return httpx.Response(
            self.status, content=b"ID3mp3", headers={"content-type": self.content_type}
        )


@pytest.fixture
def eleven(monkeypatch):
    fake = FakeEleven()

    def client(s):
        return httpx.Client(transport=httpx.MockTransport(fake.handler), timeout=s.tts_timeout)

    monkeypatch.setattr(voice, "_http_client", client)
    return fake


def eleven_settings(tmp_path, **kw):
    return settings(
        tmp_path, elevenlabs_api_key="segredo-123", elevenlabs_voice_id="voz-calma", **kw
    )


# ---------- AC-1: configuração ----------
def test_defaults_are_hybrid():
    s = Settings()
    assert s.tts_provider == "piper" and s.tts_presentation_provider == "elevenlabs"
    assert s.piper_voice == "pt_BR-faber-medium" and s.piper_data_dir == ".cache/piper"
    assert s.piper_length_scale == 1.1
    assert s.piper_noise_scale is None and s.piper_noise_w is None  # padrão da lib
    assert s.elevenlabs_model == "eleven_multilingual_v2"


def test_api_key_never_in_repr():
    s = Settings(elevenlabs_api_key="segredo-123")
    assert "segredo-123" not in repr(s)


@pytest.mark.parametrize(
    "kw",
    [
        {"tts_provider": "openai"},
        {"tts_presentation_provider": "xpto"},
        {"piper_length_scale": 0.1},
        {"piper_noise_scale": 2.0},
        {"piper_noise_w": -0.1},
        {"elevenlabs_stability": 1.5},
        {"elevenlabs_similarity": -0.1},
        {"elevenlabs_style": 2.0},
        {"elevenlabs_speed": 1.5},
        {"tts_timeout": 0},
    ],
)
def test_invalid_voice_settings_raise_in_portuguese(kw):
    with pytest.raises(ValueError, match="deve"):
        Settings(**kw)


def test_from_env_reads_voice_variables(monkeypatch):
    monkeypatch.setenv("TTS_PROVIDER", "off")
    monkeypatch.setenv("TTS_PRESENTATION_PROVIDER", "piper")
    monkeypatch.setenv("PIPER_LENGTH_SCALE", "1.3")
    monkeypatch.setenv("PIPER_NOISE_W", "0.5")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    monkeypatch.setenv("ELEVENLABS_SPEED", "0.9")
    s = Settings.from_env()
    assert (s.tts_provider, s.tts_presentation_provider) == ("off", "piper")
    assert (s.piper_length_scale, s.piper_noise_w, s.piper_noise_scale) == (1.3, 0.5, None)
    assert (s.elevenlabs_api_key, s.elevenlabs_speed) == ("k", 0.9)


def test_from_env_bad_number_is_clear(monkeypatch):
    monkeypatch.setenv("PIPER_LENGTH_SCALE", "devagar")
    with pytest.raises(ValueError, match="PIPER_LENGTH_SCALE"):
        Settings.from_env()


# ---------- AC-1: síntese ----------
def test_piper_tip_returns_wav_with_settings(tmp_path, piper):
    s = settings(tmp_path, piper_noise_scale=0.5)
    model = install_model(s)
    result = voice.synthesize(s, "  Respire   **fundo** antes de começar. ", purpose="tip")
    assert result == voice.VoiceResult(b"RIFF....WAVEfake", "audio/wav", "piper", False)
    path, text, cfg = piper.calls[0]
    assert path == model and text == "Respire fundo antes de começar."
    assert cfg == {"length_scale": 1.1, "noise_scale": 0.5, "noise_w_scale": None}


def test_presentation_uses_elevenlabs(tmp_path, eleven, piper):
    s = eleven_settings(tmp_path)
    result = voice.synthesize(s, "Olá, plateia.", purpose="presentation")
    assert (result.media_type, result.provider, result.audio) == (
        "audio/mpeg",
        "elevenlabs",
        b"ID3mp3",
    )
    req = eleven.requests[0]
    assert req.method == "POST" and req.headers["xi-api-key"] == "segredo-123"
    body = json.loads(req.content)
    assert body["model_id"] == "eleven_multilingual_v2"
    assert body["voice_settings"] == {
        "stability": 0.65,
        "similarity_boost": 0.75,
        "style": 0.0,
        "use_speaker_boost": True,
        "speed": 0.95,
    }
    assert piper.calls == []


def test_presentation_without_key_falls_back_to_piper(tmp_path, eleven, piper):
    s = settings(tmp_path)  # sem chave nem voz
    install_model(s)
    result = voice.synthesize(s, "Olá.", purpose="presentation")
    assert result.provider == "piper" and eleven.requests == []


def test_tip_never_goes_to_elevenlabs_by_default(tmp_path, eleven, piper):
    s = eleven_settings(tmp_path)
    install_model(s)
    assert voice.synthesize(s, "Dica.", purpose="tip").provider == "piper"
    assert voice.synthesize(s, "Outra dica.", purpose="explain").provider == "piper"
    assert eleven.requests == []


@pytest.mark.parametrize("text", ["", "   ", "**", "a" * 601])
def test_invalid_text_raises(tmp_path, piper, text):
    s = settings(tmp_path)
    install_model(s)
    with pytest.raises(voice.InvalidText):
        voice.synthesize(s, text)
    assert piper.calls == []


def test_markup_is_removed(tmp_path, piper):
    s = settings(tmp_path)
    install_model(s)
    voice.synthesize(s, "# Título\n- veja [o guia](https://x.org) e `isso`")
    assert piper.calls[0][1] == "Título veja o guia e isso"


# ---------- AC-2: cache ----------
def test_cache_hit_skips_provider(tmp_path, piper):
    s = settings(tmp_path)
    install_model(s)
    first = voice.synthesize(s, "Fale devagar.")
    second = voice.synthesize(s, "Fale   devagar.", purpose="explain")  # purpose fora da chave
    assert (first.cache_hit, second.cache_hit) == (False, True)
    assert second.audio == first.audio and len(piper.calls) == 1
    files = list((tmp_path / "voice").iterdir())
    assert len(files) == 1 and files[0].suffix == ".wav" and len(files[0].stem) == 64


def test_cache_key_changes_with_parameters(tmp_path, piper):
    s = settings(tmp_path)
    install_model(s)
    voice.synthesize(s, "Fale devagar.")
    voice.synthesize(replace(s, piper_length_scale=1.2), "Fale devagar.")
    voice.synthesize(replace(s, piper_noise_w=0.3), "Fale devagar.")
    assert len(piper.calls) == 3


def test_elevenlabs_cache_uses_mp3(tmp_path, eleven):
    s = eleven_settings(tmp_path)
    voice.synthesize(s, "Olá.", purpose="presentation")
    assert voice.synthesize(s, "Olá.", purpose="presentation").cache_hit
    voice.synthesize(replace(s, elevenlabs_stability=0.5), "Olá.", purpose="presentation")
    assert len(eleven.requests) == 2
    assert {p.suffix for p in (tmp_path / "voice").iterdir()} == {".mp3"}


# ---------- AC-3: falhas ----------
def test_missing_piper_model_is_unavailable(tmp_path, piper):
    with pytest.raises(voice.VoiceUnavailable, match="rag-cognus voice-download"):
        voice.synthesize(settings(tmp_path), "Olá.")
    assert piper.calls == []


def test_provider_off_is_unavailable(tmp_path, piper):
    with pytest.raises(voice.VoiceUnavailable, match="desligada"):
        voice.synthesize(settings(tmp_path, tts_provider="off"), "Olá.")


def test_piper_error_is_unavailable_and_no_cache(tmp_path, monkeypatch):
    s = settings(tmp_path)
    install_model(s)
    monkeypatch.setattr(voice, "_piper_synthesize", FakePiper(fail=RuntimeError("onnx")))
    with pytest.raises(voice.VoiceUnavailable, match="Voz indisponível agora"):
        voice.synthesize(s, "Olá.")
    assert not (tmp_path / "voice").exists() or not list((tmp_path / "voice").iterdir())


@pytest.mark.parametrize(
    "status, content_type, exc, reason",
    [
        (401, "application/json", None, "chave"),
        (429, "application/json", None, "limite"),
        (503, "application/json", None, "erro"),
        (200, "application/json", None, "áudio"),
        (200, "audio/mpeg", httpx.ReadTimeout("lento"), "demorou"),
        (200, "audio/mpeg", httpx.ConnectError("sem rede"), "conexão"),
    ],
)
def test_elevenlabs_failures(tmp_path, eleven, status, content_type, exc, reason):
    eleven.status, eleven.content_type, eleven.exc = status, content_type, exc
    s = eleven_settings(tmp_path)
    with pytest.raises(voice.VoiceUnavailable, match=reason) as info:
        voice.synthesize(s, "Olá.", purpose="presentation")
    assert "segredo-123" not in str(info.value)
    assert str(info.value).startswith("Voz indisponível agora:")
    cache = tmp_path / "voice"
    assert not cache.exists() or not list(cache.iterdir())


# ---------- AC-4 / AC-4b: privacidade ----------
def test_only_text_goes_to_elevenlabs_and_name_becomes_voce(tmp_path, eleven):
    s = eleven_settings(tmp_path)
    voice.synthesize(
        s,
        "Ana Souza, você foi ótima. Parabéns, ana!",
        purpose="presentation",
        profile_name="Ana Souza",
    )
    body = json.loads(eleven.requests[0].content)
    assert set(body) == {"text", "model_id", "voice_settings"}
    assert "ana" not in body["text"].lower()
    assert body["text"] == "Você, você foi ótima. Parabéns, você!"


def test_piper_keeps_profile_name(tmp_path, piper):
    s = settings(tmp_path)
    install_model(s)
    voice.synthesize(s, "Boa, Ana!", profile_name="Ana")
    assert piper.calls[0][1] == "Boa, Ana!"


def test_explain_number_outside_facts_is_rejected(tmp_path, piper):
    s = settings(tmp_path)
    install_model(s)
    facts = [{"label": "Ritmo", "value": "140 ppm"}]
    with pytest.raises(voice.InvalidText, match="números"):
        voice.synthesize(s, "Seu ritmo foi 180 ppm.", purpose="explain", facts=facts)
    assert piper.calls == []
    assert voice.synthesize(s, "Seu ritmo foi 140 ppm.", purpose="explain", facts=facts)


def test_tip_skips_number_guard(tmp_path, piper):
    s = settings(tmp_path)
    install_model(s)
    assert voice.synthesize(s, "Faça 3 respirações.", purpose="tip").provider == "piper"


# ---------- health ----------
def test_voice_status_reflects_model_on_disk(tmp_path, monkeypatch):
    monkeypatch.setattr(voice, "_piper_installed", lambda: True)
    s = settings(tmp_path)
    assert voice.voice_status(s) == {
        "voice_available": False,
        "voice_provider": "off",
        "presentation_voice_provider": "off",
    }
    install_model(s)
    assert voice.voice_status(s) == {
        "voice_available": True,
        "voice_provider": "piper",
        "presentation_voice_provider": "piper",  # ElevenLabs sem chave → Piper
    }
    assert voice.voice_status(eleven_settings(tmp_path))["presentation_voice_provider"] == (
        "elevenlabs"
    )


def test_voice_status_without_piper_package(tmp_path, monkeypatch):
    monkeypatch.setattr(voice, "_piper_installed", lambda: False)
    s = settings(tmp_path)
    install_model(s)
    assert voice.voice_status(s)["voice_provider"] == "off"
