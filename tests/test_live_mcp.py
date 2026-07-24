"""Gated live tests for the MCP tool surface (TGN-25).

SKIPPED unless ``TG_NOTES_LIVE`` is set. Exercises the MCP server's tools
(``note_add`` / ``note_add_file`` / ``notes_list`` / ``contacts_list`` / ``send``) in-process
against a **dedicated test account + group**, so the second frontend over the core is proven
end-to-end alongside the CLI. The tool functions are importable without the optional ``mcp``
dependency; each is an async coroutine that offloads the synchronous Telethon core to a
worker thread, so we drive them with :func:`asyncio.run`.

Run via the sandbox::

    scripts/sandbox.py pytest -- tests/test_live_mcp.py -v
"""
from __future__ import annotations

import asyncio
import os

import pytest

from tg_notes import config, mcp_server, telegram

pytestmark = pytest.mark.skipif(
    not os.environ.get("TG_NOTES_LIVE"), reason="live store (set TG_NOTES_LIVE=1)"
)

REAL_STORE_ID = -1004432534270
NOTEBOOK = "citest"


def _live_cfg() -> config.Config:
    cfg = config.load()
    assert cfg.storage_group_id, "no storage group configured — run `tg-notes setup` first"
    assert cfg.storage_group_id != REAL_STORE_ID, (
        f"refusing to run against the real store ({REAL_STORE_ID}) — use a test group"
    )
    return cfg


def test_mcp_note_roundtrip() -> None:
    _live_cfg()
    marker = f"ci-mcp-note-{os.getpid()}"

    posted = asyncio.run(mcp_server.note_add(marker, notebook=NOTEBOOK, hashtags=["citest"]))
    assert posted["message_id"], posted

    notes = asyncio.run(mcp_server.notes_list(notebook=NOTEBOOK))
    match = [n for n in notes if n["message_id"] == posted["message_id"]]
    assert match, f"MCP-posted note {posted['message_id']} not read back via notes_list"
    assert marker in match[0]["text"], match[0]


def test_mcp_notes_list_since() -> None:
    """`notes_list(since=...)` parses the time bound and returns a list."""
    _live_cfg()
    notes = asyncio.run(mcp_server.notes_list(notebook=NOTEBOOK, since="today"))
    assert isinstance(notes, list), notes


def test_mcp_note_file_document(tmp_path) -> None:
    _live_cfg()
    marker = f"ci-mcp-doc-{os.getpid()}"
    doc = tmp_path / "note.txt"
    doc.write_text(f"{marker}\n", encoding="utf-8")

    posted = asyncio.run(
        mcp_server.note_add_file(
            str(doc), notebook=NOTEBOOK, caption=marker, transcribe=False
        )
    )
    assert posted["media_type"] == "document", posted
    assert marker in posted["caption"], posted


def test_mcp_contacts_list() -> None:
    cfg = _live_cfg()
    key = f"ci-mcp-contact-{os.getpid()}"
    try:
        telegram.contacts_set(cfg, key, chat_id="me", name="CI mcp")
        listed = asyncio.run(mcp_server.contacts_list())
        assert any(c["key"] == key for c in listed), f"{key} missing from MCP contacts_list"
    finally:
        telegram.contacts_remove(cfg, key)


def test_mcp_send_dry_run() -> None:
    cfg = _live_cfg()
    key = f"ci-mcp-send-{os.getpid()}"
    try:
        telegram.contacts_set(cfg, key, chat_id="me", name="CI mcp send")
        result = asyncio.run(mcp_server.send(key, "ci mcp dry-run", dry_run=True))
        assert result["sent"] is False, result
        assert "ci mcp dry-run" in result["text"], result
    finally:
        telegram.contacts_remove(cfg, key)
