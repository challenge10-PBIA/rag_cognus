"""`rag-cognus voice-pregen` (spec 028 AC-2/AC-7): síntese falsa, sem rede, em tmp_path."""

import json
import sys

import pytest

from rag_cognus import cli
from rag_cognus.cli import voice_pregen
from rag_cognus.config import Settings
from rag_cognus.voice import VoiceResult, VoiceUnavailable


class FakeSynth:
    def __init__(self, media_type="audio/mpeg", provider="elevenlabs", fail=()):
        self.calls = []
        self.media_type, self.provider, self.fail = media_type, provider, set(fail)

    def __call__(self, settings, text, *, purpose):
        assert purpose == "presentation"
        self.calls.append(text)
        if text in self.fail:
            raise VoiceUnavailable("Voz indisponível agora: cota esgotada.")
        return VoiceResult(f"audio:{text}".encode(), self.media_type, self.provider, False)


def eleven():
    return Settings(elevenlabs_api_key="k", elevenlabs_voice_id="voz-1")


def write_roteiro(tmp_path, texts):
    steps = [
        {"id": sid, "route": "/", "anchor": None, "mood": "feliz", "text": t, "audio": sid + ".mp3"}
        for sid, t in texts.items()
    ]
    path = tmp_path / "roteiro.json"
    path.write_text(json.dumps({"version": 1, "voice_note": "", "steps": steps}), "utf-8")
    return path


def run(tmp_path, synth, settings=None, **kw):
    kw.setdefault("yes", True)
    roteiro = kw.pop("roteiro", None) or tmp_path / "roteiro.json"
    return voice_pregen(settings or eleven(), roteiro, tmp_path / "audio", synth=synth, **kw)


def manifest(tmp_path):
    return json.loads((tmp_path / "audio" / "manifest.json").read_text("utf-8"))


def test_generates_all_steps_and_manifest(tmp_path, capsys):
    write_roteiro(tmp_path, {"abertura": "Olá.", "fim": "Tchau."})
    synth = FakeSynth()
    assert run(tmp_path, synth) == 0
    assert (tmp_path / "audio" / "abertura.mp3").read_bytes() == b"audio:Ol\xc3\xa1."
    m = manifest(tmp_path)
    assert set(m) == {"abertura", "fim"}
    assert m["fim"]["file"] == "fim.mp3" and m["fim"]["provider"] == "elevenlabs"
    assert len(m["fim"]["sha256"]) == 64
    out = capsys.readouterr().out
    assert "2 passo(s)" in out and "elevenlabs" in out and "10 caracteres" in out


def test_skips_unchanged_and_regenerates_changed(tmp_path):
    write_roteiro(tmp_path, {"abertura": "Olá.", "fim": "Tchau."})
    run(tmp_path, FakeSynth())
    write_roteiro(tmp_path, {"abertura": "Olá.", "fim": "Até logo."})
    synth = FakeSynth()
    assert run(tmp_path, synth) == 0
    assert synth.calls == ["Até logo."]


def test_missing_file_is_regenerated_even_with_same_sha(tmp_path):
    write_roteiro(tmp_path, {"abertura": "Olá."})
    run(tmp_path, FakeSynth())
    (tmp_path / "audio" / "abertura.mp3").unlink()
    synth = FakeSynth()
    run(tmp_path, synth)
    assert synth.calls == ["Olá."]


def test_force_regenerates_everything(tmp_path):
    write_roteiro(tmp_path, {"abertura": "Olá.", "fim": "Tchau."})
    run(tmp_path, FakeSynth())
    synth = FakeSynth()
    assert run(tmp_path, synth, force=True) == 0
    assert synth.calls == ["Olá.", "Tchau."]


def test_only_limits_steps_and_keeps_other_entries(tmp_path):
    write_roteiro(tmp_path, {"abertura": "Olá.", "meio": "Veja.", "fim": "Tchau."})
    run(tmp_path, FakeSynth(), only=["abertura"])
    synth = FakeSynth()
    assert run(tmp_path, synth, only=["fim"]) == 0
    assert synth.calls == ["Tchau."]
    assert set(manifest(tmp_path)) == {"abertura", "fim"}


def test_unknown_only_id_fails_without_synth(tmp_path, capsys):
    write_roteiro(tmp_path, {"abertura": "Olá."})
    synth = FakeSynth()
    assert run(tmp_path, synth, only=["nao-existe"]) != 0
    assert synth.calls == [] and "nao-existe" in capsys.readouterr().out


def test_piper_result_is_saved_as_wav(tmp_path):
    write_roteiro(tmp_path, {"abertura": "Olá."})
    synth = FakeSynth(media_type="audio/wav", provider="piper")
    assert run(tmp_path, synth, settings=Settings()) == 0
    assert (tmp_path / "audio" / "abertura.wav").is_file()
    m = manifest(tmp_path)["abertura"]
    assert m == {"file": "abertura.wav", "sha256": m["sha256"], "provider": "piper"}


def test_partial_failure_keeps_generated_and_exits_nonzero(tmp_path, capsys):
    write_roteiro(tmp_path, {"abertura": "Olá.", "meio": "Falha.", "fim": "Tchau."})
    code = run(tmp_path, FakeSynth(fail={"Falha."}))
    assert code != 0
    assert (tmp_path / "audio" / "abertura.mp3").is_file()
    assert (tmp_path / "audio" / "fim.mp3").is_file()
    assert not (tmp_path / "audio" / "meio.mp3").exists()
    assert set(manifest(tmp_path)) == {"abertura", "fim"}
    assert "Faltaram: meio" in capsys.readouterr().out


def test_denied_confirmation_generates_nothing(tmp_path, capsys):
    write_roteiro(tmp_path, {"abertura": "Olá."})
    synth = FakeSynth()
    code = run(tmp_path, synth, yes=False, ask=lambda prompt: "n")
    assert code != 0 and synth.calls == []
    assert not (tmp_path / "audio").exists()
    assert "Gerar? [s/N]" not in capsys.readouterr().out  # o prompt vai pelo ask


def test_accepted_confirmation_generates(tmp_path):
    write_roteiro(tmp_path, {"abertura": "Olá."})
    prompts = []
    synth = FakeSynth()
    code = run(tmp_path, synth, yes=False, ask=lambda p: prompts.append(p) or "s")
    assert code == 0 and synth.calls == ["Olá."] and prompts == ["Gerar? [s/N] "]


def test_nothing_to_do_does_not_ask(tmp_path):
    write_roteiro(tmp_path, {"abertura": "Olá."})
    run(tmp_path, FakeSynth())

    def never(prompt):
        raise AssertionError("não deve perguntar sem passos a gerar")

    assert run(tmp_path, FakeSynth(), yes=False, ask=never) == 0


def test_subcommand_is_wired(monkeypatch, tmp_path):
    seen = {}

    def fake(settings, roteiro, out, force=False, only=None, yes=False):
        seen.update(roteiro=roteiro, out=out, force=force, only=only, yes=yes)
        return 0

    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    monkeypatch.setattr(cli, "voice_pregen", fake)
    argv = ["rag-cognus", "voice-pregen", "--only", "a", "--only", "b", "--yes", "--force"]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0
    assert seen["only"] == ["a", "b"] and seen["yes"] and seen["force"]
    assert str(seen["roteiro"]).endswith("frontend_UI/public/presentation/roteiro.json")
    assert str(seen["out"]).endswith("frontend_UI/public/presentation/audio")


def test_missing_roteiro_explains(tmp_path, capsys):
    synth = FakeSynth()
    assert run(tmp_path, synth, roteiro=tmp_path / "nao.json") == 2
    assert synth.calls == [] and "Roteiro não encontrado" in capsys.readouterr().out
