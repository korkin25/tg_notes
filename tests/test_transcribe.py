"""Tests for local audio transcription (media Phase 2).

Everything is FULLY MOCKED and offline: the whisper CLI backends run through a fake
``subprocess.run`` (which writes the transcript file the code then reads), and the
``faster_whisper`` package is injected as a fake module via ``sys.modules``. No engine is
installed, nothing is downloaded, and no network is touched.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from tg_notes import transcribe
from tg_notes.config import Config

# --- fakes ------------------------------------------------------------------------


def _fake_faster_whisper(record: dict | None = None, segments=(" Hello", " world")):
    """A stand-in ``faster_whisper`` module whose ``WhisperModel`` yields ``segments``."""
    mod = types.ModuleType("faster_whisper")

    class WhisperModel:
        def __init__(self, name):
            if record is not None:
                record["model"] = name

        def transcribe(self, path):
            if record is not None:
                record["path"] = path
            segs = (types.SimpleNamespace(text=t) for t in segments)
            return segs, types.SimpleNamespace(language="en")

    mod.WhisperModel = WhisperModel
    return mod


# --- is_audio ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("a.ogg", True),
        ("a.OGG", True),
        ("voice.opus", True),
        ("v.oga", True),
        ("x.mp3", True),
        ("y.m4a", True),
        ("z.wav", True),
        ("f.flac", True),
        ("a.aac", True),
        ("clip.webm", True),
        ("pic.png", False),
        ("doc.pdf", False),
        ("movie.mp4", False),
        ("noext", False),
    ],
)
def test_is_audio(name, expected) -> None:
    assert transcribe.is_audio(name) is expected
    assert transcribe.is_audio(Path("/tmp") / name) is expected


# --- available_transcriber: detection order ---------------------------------------


def test_available_prefers_configured_cmd(monkeypatch) -> None:
    monkeypatch.setattr(
        transcribe.shutil, "which", lambda name: "/opt/cfgw" if name == "cfgwhisper" else None
    )
    monkeypatch.setitem(sys.modules, "faster_whisper", None)  # not chosen
    assert transcribe.available_transcriber(Config(whisper_cmd="cfgwhisper")) == "/opt/cfgw"


def test_available_configured_cmd_wins_over_path(monkeypatch) -> None:
    table = {
        "cfgw": "/opt/cfgw",
        "whisper-cli": "/usr/bin/whisper-cli",
        "whisper": "/usr/bin/whisper",
        "main": "/usr/bin/main",
    }
    monkeypatch.setattr(transcribe.shutil, "which", table.get)
    assert transcribe.available_transcriber(Config(whisper_cmd="cfgw")) == "/opt/cfgw"


def test_available_path_cmd(monkeypatch) -> None:
    monkeypatch.setattr(
        transcribe.shutil,
        "which",
        lambda name: "/usr/bin/whisper-cli" if name == "whisper-cli" else None,
    )
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    assert transcribe.available_transcriber(Config()) == "/usr/bin/whisper-cli"


def test_available_path_cmd_falls_through_names(monkeypatch) -> None:
    # whisper-cli absent, openai `whisper` present → the second name wins.
    monkeypatch.setattr(
        transcribe.shutil,
        "which",
        lambda name: "/usr/bin/whisper" if name == "whisper" else None,
    )
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    assert transcribe.available_transcriber(Config()) == "/usr/bin/whisper"


def test_available_faster_whisper_when_no_cli(monkeypatch) -> None:
    monkeypatch.setattr(transcribe.shutil, "which", lambda name: None)
    monkeypatch.setitem(sys.modules, "faster_whisper", _fake_faster_whisper())
    assert transcribe.available_transcriber(Config()) == "faster-whisper"


def test_available_none_when_nothing(monkeypatch) -> None:
    monkeypatch.setattr(transcribe.shutil, "which", lambda name: None)
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    assert transcribe.available_transcriber(Config()) is None
    assert transcribe.available_transcriber(None) is None


# --- transcribe: faster-whisper backend -------------------------------------------


def test_transcribe_faster_whisper_joins_segments(monkeypatch) -> None:
    record: dict = {}
    monkeypatch.setattr(transcribe.shutil, "which", lambda name: None)
    monkeypatch.setitem(sys.modules, "faster_whisper", _fake_faster_whisper(record))

    out = transcribe.transcribe("/tmp/a.ogg", Config(whisper_model="small"))

    assert out == "Hello world"
    assert record["model"] == "small"
    assert record["path"] == "/tmp/a.ogg"


def test_transcribe_faster_whisper_default_model(monkeypatch) -> None:
    record: dict = {}
    monkeypatch.setattr(transcribe.shutil, "which", lambda name: None)
    monkeypatch.setitem(sys.modules, "faster_whisper", _fake_faster_whisper(record))

    transcribe.transcribe("/tmp/a.ogg", None)  # cfg=None → default model

    assert record["model"] == "base"


def test_transcribe_faster_whisper_engine_error_wrapped(monkeypatch) -> None:
    mod = types.ModuleType("faster_whisper")

    class WhisperModel:
        def __init__(self, name):
            pass

        def transcribe(self, path):
            raise RuntimeError("cuda kaboom")

    mod.WhisperModel = WhisperModel
    monkeypatch.setattr(transcribe.shutil, "which", lambda name: None)
    monkeypatch.setitem(sys.modules, "faster_whisper", mod)

    with pytest.raises(transcribe.TranscriptionError) as ei:
        transcribe.transcribe("/tmp/a.ogg", Config())
    assert "cuda kaboom" in str(ei.value)


# --- transcribe: CLI backends -----------------------------------------------------


def test_transcribe_cli_whisper_cpp_builds_args_and_reads_txt(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        transcribe.shutil,
        "which",
        lambda name: "/usr/bin/whisper-cli" if name == "whisper-cli" else None,
    )
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    calls: dict = {}

    def fake_run(argv, **kwargs):
        calls["argv"] = argv
        calls["kwargs"] = kwargs
        stem = argv[argv.index("-of") + 1]  # whisper.cpp writes <stem>.txt
        Path(stem + ".txt").write_text("hello from cpp\n", encoding="utf-8")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(transcribe.subprocess, "run", fake_run)

    src = str(tmp_path / "audio.wav")
    out = transcribe.transcribe(src, Config())

    assert out == "hello from cpp"
    argv = calls["argv"]
    assert argv[0] == "/usr/bin/whisper-cli"
    assert argv[argv.index("-f") + 1] == src
    assert "-otxt" in argv
    assert "-of" in argv
    assert calls["kwargs"]["capture_output"] is True
    assert calls["kwargs"]["text"] is True
    assert "timeout" in calls["kwargs"]


def test_transcribe_cli_openai_whisper_builds_args_and_reads_txt(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        transcribe.shutil,
        "which",
        lambda name: "/usr/bin/whisper" if name == "whisper" else None,
    )
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    calls: dict = {}

    def fake_run(argv, **kwargs):
        calls["argv"] = argv
        outdir = Path(argv[argv.index("--output_dir") + 1])
        inp = Path(argv[1])
        (outdir / (inp.stem + ".txt")).write_text("hello openai\n", encoding="utf-8")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(transcribe.subprocess, "run", fake_run)

    src = str(tmp_path / "clip.mp3")
    out = transcribe.transcribe(src, Config(whisper_model="tiny"))

    assert out == "hello openai"
    argv = calls["argv"]
    assert argv[0] == "/usr/bin/whisper"
    assert argv[1] == src
    assert argv[argv.index("--model") + 1] == "tiny"
    assert argv[argv.index("--output_format") + 1] == "txt"
    assert "--output_dir" in argv


def test_transcribe_cli_nonzero_exit_raises_with_stderr_tail(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        transcribe.shutil,
        "which",
        lambda name: "/usr/bin/whisper-cli" if name == "whisper-cli" else None,
    )
    monkeypatch.setitem(sys.modules, "faster_whisper", None)

    def fake_run(argv, **kwargs):
        return types.SimpleNamespace(returncode=2, stdout="", stderr="boom failure tail")

    monkeypatch.setattr(transcribe.subprocess, "run", fake_run)

    with pytest.raises(transcribe.TranscriptionError) as ei:
        transcribe.transcribe(str(tmp_path / "a.wav"), Config())
    assert "boom failure tail" in str(ei.value)


def test_transcribe_cli_run_oserror_raises(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        transcribe.shutil,
        "which",
        lambda name: "/usr/bin/whisper-cli" if name == "whisper-cli" else None,
    )
    monkeypatch.setitem(sys.modules, "faster_whisper", None)

    def fake_run(argv, **kwargs):
        raise OSError("exec format error")

    monkeypatch.setattr(transcribe.subprocess, "run", fake_run)

    with pytest.raises(transcribe.TranscriptionError):
        transcribe.transcribe(str(tmp_path / "a.wav"), Config())


# --- transcribe: no engine --------------------------------------------------------


def test_transcribe_unavailable_when_no_engine(monkeypatch) -> None:
    monkeypatch.setattr(transcribe.shutil, "which", lambda name: None)
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    with pytest.raises(transcribe.TranscriptionUnavailable):
        transcribe.transcribe("/tmp/a.ogg", Config())
