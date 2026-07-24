"""Gated live-functional tests — the full CLI surface against a real store (TGN-25).

SKIPPED unless ``TG_NOTES_LIVE`` is set. Drives **every** ``tg-notes`` command in-process
(via :func:`tg_notes.cli.main`) against a **dedicated test account + group** — the
``ci-functional`` secrets in CI, or the sandbox locally — so the whole data path is proven
end-to-end on every push: ``setup`` / ``secrets status`` / ``secrets doctor`` / ``whoami``,
text and media ``note add``, ``notes list``, ``notebooks list``, the ``contacts`` CRUD, and
``send`` (a dry run **and** a real self-send that is cleaned up afterwards).

Run them via the sandbox so a throwaway config is seeded and the real store is never
touched::

    scripts/sandbox.py pytest -- tests/test_live_functional.py -v

MCP-tool coverage lives in ``test_live_mcp.py``; media round-trips via the core layer in
``test_live_media.py``; the secure-store (keyring) flow — which needs a Secret Service and
so cannot run in CI — in ``test_live_secure_store.py``.
"""
from __future__ import annotations

import json
import os
import struct
import zlib

import pytest

from tg_notes import cli, config, telegram

pytestmark = pytest.mark.skipif(
    not os.environ.get("TG_NOTES_LIVE"), reason="live store (set TG_NOTES_LIVE=1)"
)

#: The maintainer's real note store (see CLAUDE.md). Live-functional tests write notes and
#: contacts, so running them against it is forbidden — they must use a dedicated test group.
REAL_STORE_ID = -1004432534270

#: A throwaway notebook for the data round-trips (kept out of the real presets).
NOTEBOOK = "citest"


def _live_cfg() -> config.Config:
    """Load the seeded sandbox/CI config and refuse to touch the real store."""
    cfg = config.load()
    assert cfg.storage_group_id, "no storage group configured — run `tg-notes setup` first"
    assert cfg.storage_group_id != REAL_STORE_ID, (
        "refusing to run live-functional tests against the real store "
        f"({REAL_STORE_ID}) — use a dedicated test account + group"
    )
    return cfg


def _cli(capsys, argv: list[str], *, expect: int = 0):
    """Run ``tg-notes <argv>`` in-process; assert the exit code and return the capture."""
    code = cli.main(argv)
    captured = capsys.readouterr()
    assert code == expect, f"`tg-notes {' '.join(argv)}` -> {code}; stderr:\n{captured.err}"
    return captured


def _cli_json(capsys, argv: list[str]) -> dict | list:
    """Run a command and parse its last stdout line as JSON."""
    out = _cli(capsys, argv).out.strip().splitlines()
    assert out, f"`tg-notes {' '.join(argv)}` printed nothing on stdout"
    return json.loads(out[-1])


def _write(tmp_path, name: str, text: str) -> str:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def _solid_png(width: int = 160, height: int = 160) -> bytes:
    """A valid 8-bit truecolor solid-color PNG built in-process (Telegram rejects 1x1)."""

    def _chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + bytes((30, 144, 255)) * width
    idat = zlib.compress(row * height, 9)
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


# --- onboarding / diagnostics commands -------------------------------------------


def test_cli_whoami(capsys) -> None:
    _live_cfg()
    identity = _cli_json(capsys, ["whoami"])
    assert isinstance(identity.get("id"), int), identity


@pytest.mark.parametrize("argv", [["secrets", "status"], ["secrets", "doctor", "--json"]])
def test_cli_secrets_report_file_backend(capsys, mocker, argv) -> None:
    """`secrets status` / `secrets doctor --json` report the seeded file backend as
    configured + authorized. The vault probe is stubbed so the diagnosis never blocks on a
    real Secret Service prompt on a developer machine — the file-backend facts asserted here
    do not depend on it (and CI has no Secret Service anyway)."""
    _live_cfg()
    mocker.patch("tg_notes.secrets.keyring_probe", return_value=(False, "not-installed"))
    state = _cli_json(capsys, argv)
    assert state["backend"] == "file", state
    assert state["configured"] is True, state
    assert state["has_session"] is True, state


def test_cli_setup_idempotent(capsys) -> None:
    """Re-running ``setup`` attaches to the existing store: same id, no re-creation."""
    cfg = _live_cfg()
    result = _cli_json(capsys, ["setup"])
    assert result["created"] is False, result
    assert result["group_id"] == cfg.storage_group_id, result
    assert telegram.CONTACTS_TOPIC in result["topics"], result


# --- notes: text + media, via the CLI --------------------------------------------


def test_cli_note_text_roundtrip(capsys, tmp_path) -> None:
    _live_cfg()
    marker = f"ci-cli-note-{os.getpid()}"
    text_file = _write(tmp_path, "note.txt", marker)

    posted = _cli_json(
        capsys,
        ["note", "add", "--notebook", NOTEBOOK, "--text-file", text_file, "--hashtag", "citest"],
    )
    assert posted["message_id"], posted

    notes = _cli_json(capsys, ["notes", "list", "--notebook", NOTEBOOK])
    match = [n for n in notes if n["message_id"] == posted["message_id"]]
    assert match, f"posted note {posted['message_id']} not read back"
    assert marker in match[0]["text"] and "#citest" in match[0]["text"], match[0]


def test_cli_note_media_document(capsys, tmp_path) -> None:
    _live_cfg()
    marker = f"ci-cli-doc-{os.getpid()}"
    doc = _write(tmp_path, "note.txt", f"{marker}\n")

    posted = _cli_json(
        capsys,
        ["note", "add", "--notebook", NOTEBOOK, "--file", doc, "--caption", marker, "--no-transcribe"],
    )
    assert posted["media_type"] == "document", posted

    notes = _cli_json(capsys, ["notes", "list", "--notebook", NOTEBOOK])
    match = [n for n in notes if n["message_id"] == posted["message_id"]]
    assert match and match[0]["media"] == "document", match


def test_cli_note_media_photo(capsys, tmp_path) -> None:
    _live_cfg()
    marker = f"ci-cli-photo-{os.getpid()}"
    png = tmp_path / "pixel.png"
    png.write_bytes(_solid_png())

    posted = _cli_json(
        capsys,
        ["note", "add", "--notebook", NOTEBOOK, "--file", str(png), "--caption", marker],
    )
    assert posted["media_type"] == "photo", posted

    notes = _cli_json(capsys, ["notes", "list", "--notebook", NOTEBOOK])
    match = [n for n in notes if n["message_id"] == posted["message_id"]]
    assert match and match[0]["media"] == "photo", match


def test_cli_notes_list_since_filter(capsys, tmp_path) -> None:
    """`notes list --since today` returns a well-formed list (time-bounded query path)."""
    _live_cfg()
    notes = _cli_json(capsys, ["notes", "list", "--notebook", NOTEBOOK, "--since", "today"])
    assert isinstance(notes, list), notes


def test_cli_notebooks_list(capsys) -> None:
    _live_cfg()
    notebooks = _cli_json(capsys, ["notebooks", "list"])
    assert isinstance(notebooks, list), notebooks
    names = {nb["name"] for nb in notebooks}
    assert names.isdisjoint(telegram.RESERVED_TOPICS), names


# --- contacts CRUD ----------------------------------------------------------------


def test_cli_contacts_crud(capsys) -> None:
    _live_cfg()
    key = f"ci-cli-contact-{os.getpid()}"
    try:
        created = _cli_json(
            capsys,
            ["contacts", "set", key, "--chat-id", "me", "--name", "CI selftest",
             "--style", "verbatim", "--mention", "@ci"],
        )
        assert created["created"] is True, created

        listed = _cli_json(capsys, ["contacts", "list"])
        entry = [c for c in listed if c["key"] == key]
        assert entry, f"{key} missing from contacts list"
        assert entry[0]["style"] == "verbatim", entry[0]
    finally:
        removed = _cli_json(capsys, ["contacts", "remove", key])
        assert removed["removed"] is True, removed
    assert all(c["key"] != key for c in _cli_json(capsys, ["contacts", "list"]))


# --- send: dry run + a real self-send (cleaned up) --------------------------------


def test_cli_send_dry_run(capsys, tmp_path) -> None:
    _live_cfg()
    key = f"ci-cli-send-dry-{os.getpid()}"
    body = _write(tmp_path, "msg.txt", "ci dry-run body")
    try:
        _cli(capsys, ["contacts", "set", key, "--chat-id", "me", "--mention", "@ci"])
        result = _cli_json(
            capsys, ["send", "--contact", key, "--text-file", body, "--dry-run"]
        )
        assert result["sent"] is False, result
        assert "ci dry-run body" in result["text"] and "@ci" in result["text"], result
    finally:
        _cli(capsys, ["contacts", "remove", key])


def test_cli_send_real_self(capsys, tmp_path) -> None:
    """A real ``send`` publishes to the account's own Saved Messages, then cleans up."""
    cfg = _live_cfg()
    key = f"ci-cli-send-real-{os.getpid()}"
    body = _write(tmp_path, "msg.txt", f"ci real self-send {os.getpid()}")
    sent = None
    try:
        _cli(capsys, ["contacts", "set", key, "--chat-id", "me", "--name", "CI self"])
        sent = _cli_json(capsys, ["send", "--contact", key, "--text-file", body])
        assert sent["sent"] is True, sent
        assert isinstance(sent["message_id"], int), sent
    finally:
        if sent and sent.get("message_id"):
            client = telegram.connect_authorized(cfg)
            try:
                client.delete_messages("me", [sent["message_id"]])
            finally:
                client.disconnect()
        _cli(capsys, ["contacts", "remove", key])
