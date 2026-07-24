"""Gated live integration tests for media notes (media Phase 1).

SKIPPED unless ``TG_NOTES_LIVE`` is set — CI never runs these. To exercise them against
the real store, first `tg-notes setup`, then::

    TG_NOTES_LIVE=1 .venv/bin/pytest tests/test_live_media.py -v

Each test generates its fixture in-process (no external files), uploads it to the
``mediatest`` notebook, asserts the returned ``media_type``, then reads it back with
``notes_list`` and checks the new message is present with the expected media type and
caption. Self-contained and deterministic; the per-run marker keeps assertions unambiguous.
"""
from __future__ import annotations

import os
import struct
import zlib

import pytest

from tg_notes import config, telegram

pytestmark = pytest.mark.skipif(
    not os.environ.get("TG_NOTES_LIVE"), reason="live store (set TG_NOTES_LIVE=1)"
)

NOTEBOOK = "mediatest"


def _solid_png(width: int = 160, height: int = 160, rgb: tuple[int, int, int] = (30, 144, 255)) -> bytes:
    """Build a valid 8-bit truecolor solid-color PNG in-process (no external file, no PIL).

    A 1x1 PNG is too small for Telegram's server-side image pipeline (it rejects it with
    ``ImageProcessFailedError``); a real 160x160 image round-trips cleanly. Structure:
    signature + IHDR + a single zlib-compressed IDAT (each row prefixed with a 0 filter
    byte) + IEND.
    """

    def _chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit, colortype 2 (RGB)
    row = b"\x00" + bytes(rgb) * width  # filter byte 0, then width RGB pixels
    idat = zlib.compress(row * height, 9)
    return signature + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


def _live_cfg() -> config.Config:
    cfg = config.load()
    assert cfg.storage_group_id, "no storage group configured — run `tg-notes setup` first"
    return cfg


def _find(cfg: config.Config, message_id: int) -> dict:
    notes = telegram.notes_list(cfg, notebook=NOTEBOOK)
    matches = [n for n in notes if n["message_id"] == message_id]
    assert matches, (
        f"uploaded message {message_id} not found in notebook {NOTEBOOK!r} "
        f"(read back {len(notes)} notes)"
    )
    return matches[0]


def test_live_upload_document_roundtrip(tmp_path) -> None:
    cfg = _live_cfg()
    marker = f"live-doc-{os.getpid()}"
    f = tmp_path / "note.txt"
    f.write_text(f"{marker}\n", encoding="utf-8")

    posted = telegram.note_add_file(
        cfg, notebook=NOTEBOOK, file_path=str(f), caption=marker, hashtags=["mediatest"]
    )
    assert posted["media_type"] == "document", posted
    assert posted["caption"] == f"{marker}\n\n#mediatest", posted
    assert posted["message_id"], posted

    note = _find(cfg, posted["message_id"])
    assert note["media"] == "document", note
    assert marker in note["text"], note


def test_live_upload_photo_roundtrip(tmp_path) -> None:
    cfg = _live_cfg()
    marker = f"live-photo-{os.getpid()}"
    f = tmp_path / "pixel.png"
    f.write_bytes(_solid_png())

    posted = telegram.note_add_file(
        cfg, notebook=NOTEBOOK, file_path=str(f), caption=marker
    )
    assert posted["media_type"] == "photo", posted
    assert posted["message_id"], posted

    note = _find(cfg, posted["message_id"])
    assert note["media"] == "photo", note
    assert note["text"] == marker, note
