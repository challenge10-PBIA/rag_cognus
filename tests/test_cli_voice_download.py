"""`rag-cognus voice-download` (spec 027): sem rede, subprocess e pacote falsos."""

import subprocess
import sys
from pathlib import Path

import pytest

from rag_cognus import cli
from rag_cognus.cli import voice_download
from rag_cognus.config import Settings


class FakeRun:
    def __init__(self, stdout=""):
        self.calls = []
        self.stdout = stdout

    def __call__(self, command, **kwargs):
        self.calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout=self.stdout, stderr="")


def make_settings(tmp_path):
    return Settings(piper_data_dir=str(tmp_path / "piper"), voice_cache_dir=str(tmp_path / "v"))


def put_model(settings, name):
    folder = Path(settings.piper_data_dir)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.onnx").write_bytes(b"x")
    (folder / f"{name}.onnx.json").write_text("{}")


def test_without_package_exits_1_with_hint(tmp_path, capsys):
    run = FakeRun()
    code = voice_download(make_settings(tmp_path), run=run, installed=lambda: False)
    assert code == 1 and run.calls == []
    assert "Instale o extra de voz: pip install -e '.[voice]'" in capsys.readouterr().out


def test_downloads_configured_voice_with_package_module(tmp_path, capsys):
    s = make_settings(tmp_path)
    run = FakeRun()
    code = voice_download(s, run=run, installed=lambda: True)
    assert code == 0
    assert run.calls == [
        [
            sys.executable,
            "-m",
            "piper.download_voices",
            "pt_BR-faber-medium",
            "--data-dir",
            s.piper_data_dir,
        ]
    ]
    assert "voice_provider" in capsys.readouterr().out


def test_existing_model_is_not_downloaded_again(tmp_path, capsys):
    s = make_settings(tmp_path)
    put_model(s, "pt_BR-faber-medium")
    run = FakeRun()
    assert voice_download(s, run=run, installed=lambda: True) == 0
    assert run.calls == []
    assert "já existe" in capsys.readouterr().out


def test_force_and_repeated_voices(tmp_path):
    s = make_settings(tmp_path)
    put_model(s, "pt_BR-faber-medium")
    run = FakeRun()
    voices = ["pt_BR-faber-medium", "pt_BR-cadu-medium"]
    assert voice_download(s, voices=voices, force=True, run=run, installed=lambda: True) == 0
    assert [c[3] for c in run.calls] == voices
    assert all(c[-1] == "--force-redownload" for c in run.calls)


def test_list_shows_only_pt_br(tmp_path, capsys):
    run = FakeRun(stdout="en_US-lessac-medium\npt_BR-cadu-medium\npt_BR-faber-medium\n")
    code = voice_download(make_settings(tmp_path), list_only=True, run=run, installed=lambda: True)
    out = capsys.readouterr().out
    assert code == 0
    assert run.calls == [[sys.executable, "-m", "piper.download_voices"]]
    assert "pt_BR-cadu-medium" in out and "en_US" not in out


def test_failed_download_exits_nonzero(tmp_path):
    def failing(command, **kwargs):
        return subprocess.CompletedProcess(command, 2, stdout="", stderr="erro")

    assert voice_download(make_settings(tmp_path), run=failing, installed=lambda: True) == 1


def test_subcommand_is_wired(monkeypatch, tmp_path):
    seen = {}

    def fake(settings, voices=None, force=False, list_only=False):
        seen.update(voices=voices, force=force, list_only=list_only)
        return 0

    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    monkeypatch.setattr(cli, "voice_download", fake)
    argv = ["rag-cognus", "voice-download", "--voice", "a", "--voice", "b", "--force"]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0
    assert seen == {"voices": ["a", "b"], "force": True, "list_only": False}
