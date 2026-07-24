"""Shared test fixtures.

The autouse session fixture below is a hard safety net: it pins the re-exec sentinel
so no test can ever trigger a real ``tg_notes.relaunch`` CLI re-exec (which would call
``os.execv`` and replace the pytest process). ``relaunch_as_named()`` returns early
whenever ``TG_NOTES_RELAUNCHED == "1"``. Tests that exercise the exec path clear the
sentinel locally with the function-scoped ``monkeypatch`` fixture, which restores it to
``"1"`` afterwards.
"""
from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def _guard_relaunch_sentinel():
    """Set ``TG_NOTES_RELAUNCHED=1`` for the whole session so no CLI test re-execs."""
    saved = os.environ.get("TG_NOTES_RELAUNCHED")
    os.environ["TG_NOTES_RELAUNCHED"] = "1"
    try:
        yield
    finally:
        if saved is None:
            os.environ.pop("TG_NOTES_RELAUNCHED", None)
        else:
            os.environ["TG_NOTES_RELAUNCHED"] = saved
