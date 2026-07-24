"""Gated live-functional tests — the real Telegram flow, run under CI (TGN-25).

SKIPPED unless ``TG_NOTES_LIVE`` is set. They exercise the end-to-end path against a
**dedicated test account + group** (the ``ci-functional`` secrets in CI, or the sandbox
locally), covering the commands the maintainer wants proven on every push: ``setup`` /
``secrets doctor`` / ``whoami`` plus data round-trips (note add→list, contacts set→list,
notebooks list, ``send --dry-run``).

Run them via the sandbox so a throwaway config is seeded and the real store is never
touched::

    scripts/sandbox.py pytest -- tests/test_live_functional.py -v

In CI the ``live-functional`` job seeds config from the environment secrets and runs the
same command. A hard guard refuses to run against the real store id, so an accidental
personal-account session can never write test data into it.
"""
from __future__ import annotations

import json
import os

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


def _cli_json(capsys, argv: list[str]) -> dict:
    """Run ``tg-notes <argv>`` in-process and parse the last stdout line as JSON."""
    assert cli.main(argv) == 0, f"`tg-notes {' '.join(argv)}` exited non-zero"
    out = capsys.readouterr().out.strip().splitlines()
    assert out, f"`tg-notes {' '.join(argv)}` printed nothing on stdout"
    return json.loads(out[-1])


# --- named commands: whoami / secrets doctor / setup -----------------------------


def test_live_whoami(capsys) -> None:
    _live_cfg()
    identity = _cli_json(capsys, ["whoami"])
    assert isinstance(identity.get("id"), int), identity


def test_live_secrets_doctor(capsys, mocker) -> None:
    """`secrets doctor --json` reports the seeded file backend as configured + authorized.

    The vault probe is stubbed so the diagnosis never blocks on a real Secret Service
    prompt on a developer machine; the file-backend ``configured`` / ``has_session`` facts
    (what this test asserts) do not depend on it.
    """
    _live_cfg()
    mocker.patch("tg_notes.secrets.keyring_probe", return_value=(False, "not-installed"))
    state = _cli_json(capsys, ["secrets", "doctor", "--json"])
    assert state["backend"] == "file", state
    assert state["configured"] is True, state
    assert state["has_session"] is True, state


def test_live_setup_idempotent(capsys) -> None:
    """Re-running ``setup`` attaches to the existing store: same id, no re-creation."""
    cfg = _live_cfg()
    result = _cli_json(capsys, ["setup"])
    assert result["created"] is False, result
    assert result["group_id"] == cfg.storage_group_id, result
    assert telegram.CONTACTS_TOPIC in result["topics"], result


# --- data round-trips -------------------------------------------------------------


def test_live_note_roundtrip() -> None:
    cfg = _live_cfg()
    marker = f"ci-note-{os.getpid()}"

    posted = telegram.note_add(cfg, notebook=NOTEBOOK, text=marker, hashtags=["citest"])
    assert posted["message_id"], posted

    notes = telegram.notes_list(cfg, notebook=NOTEBOOK)
    match = [n for n in notes if n["message_id"] == posted["message_id"]]
    assert match, f"posted note {posted['message_id']} not read back ({len(notes)} notes)"
    assert marker in match[0]["text"], match[0]


def test_live_contacts_roundtrip() -> None:
    cfg = _live_cfg()
    key = f"ci-contact-{os.getpid()}"
    try:
        stored = telegram.contacts_set(
            cfg, key, chat_id="me", name="CI selftest", style="verbatim"
        )
        assert stored["created"] is True, stored

        listed = telegram.contacts_list(cfg)
        assert any(c["key"] == key for c in listed), f"{key} missing from {listed}"
    finally:
        removed = telegram.contacts_remove(cfg, key)
        assert removed["removed"] is True, removed
    assert all(c["key"] != key for c in telegram.contacts_list(cfg)), "contact not cleared"


def test_live_notebooks_list() -> None:
    cfg = _live_cfg()
    notebooks = telegram.notebooks_list(cfg)
    assert isinstance(notebooks, list), notebooks
    names = {nb["name"] for nb in notebooks}
    # Reserved topics are never reported as notebooks.
    assert names.isdisjoint(telegram.RESERVED_TOPICS), names


def test_live_send_dry_run() -> None:
    """`send --dry-run` composes the outgoing message but posts nothing (no target lookup)."""
    cfg = _live_cfg()
    key = f"ci-send-{os.getpid()}"
    try:
        telegram.contacts_set(cfg, key, chat_id="me", name="CI send target")
        result = telegram.send(cfg, key, "ci dry-run body", dry_run=True)
        assert result["sent"] is False, result
        assert "ci dry-run body" in result["text"], result
    finally:
        telegram.contacts_remove(cfg, key)
