"""Gated live transcription test (media Phase 2).

SKIPPED unless ``TG_NOTES_LIVE`` is set, and additionally skipped when no local
transcription engine is available on the machine (so CI and engineless dev boxes never run
it). It touches no network and no Telegram — it only generates a tiny silent WAV in-process
and runs the real local transcriber, asserting the result is a string (not its content: a
silent clip may transcribe to empty text)::

    TG_NOTES_LIVE=1 .venv/bin/pytest tests/test_live_transcribe.py -v
"""
from __future__ import annotations

import os
import wave

import pytest

from tg_notes import config, transcribe

pytestmark = pytest.mark.skipif(
    not os.environ.get("TG_NOTES_LIVE"), reason="live engine (set TG_NOTES_LIVE=1)"
)


def _write_silent_wav(path, seconds: int = 1, rate: int = 16000) -> None:
    """Write a mono 16-bit PCM WAV of ``seconds`` of silence (stdlib only, no ffmpeg)."""
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * (rate * seconds))


def test_live_transcribe_generated_wav(tmp_path) -> None:
    cfg = config.load()
    backend = transcribe.available_transcriber(cfg)
    if backend is None:
        pytest.skip("no local transcription engine available on this machine")

    wav = tmp_path / "silence.wav"
    _write_silent_wav(wav)

    result = transcribe.transcribe(str(wav), cfg)

    assert isinstance(result, str), (backend, result)
