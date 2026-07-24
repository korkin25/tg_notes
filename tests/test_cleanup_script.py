"""Mocked, CI-safe tests for ``scripts/cleanup_live.py``.

The cleanup helper lives under ``scripts/`` (not a package), so it is loaded from its path
with ``importlib``. These tests never touch Telegram: the Telethon client and the store
resolver are mocked. They pin the critical safety property — the cleanup **refuses to run
against the real store** — plus the purge/teardown mechanics and argument wiring.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from tg_notes.config import Config

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "cleanup_live.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("cleanup_live", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cleanup = _load_module()


# --- the real-store guard (the whole point) --------------------------------------


def test_guard_rejects_the_real_store() -> None:
    with pytest.raises(cleanup.CleanupError):
        cleanup._assert_safe_store(Config(storage_group_id=cleanup.REAL_STORE_ID))


def test_guard_rejects_missing_group() -> None:
    with pytest.raises(cleanup.CleanupError):
        cleanup._assert_safe_store(Config(storage_group_id=None))


def test_guard_allows_a_dedicated_group() -> None:
    cleanup._assert_safe_store(Config(storage_group_id=-1004422788484))  # no raise


# --- purge: delete every note but the topic opener -------------------------------


def _fake_client(mocker, messages):
    client = mocker.Mock()
    client.iter_messages.return_value = iter(messages)
    return client


def test_purge_deletes_non_opener_messages(mocker) -> None:
    cfg = Config(storage_group_id=-100_777)
    # topic id 10 == the opener message id; 11/12 are notes to remove.
    msgs = [mocker.Mock(id=10), mocker.Mock(id=11), mocker.Mock(id=12)]
    client = _fake_client(mocker, msgs)
    mocker.patch.object(cleanup.telegram, "connect_authorized", return_value=client)
    mocker.patch.object(cleanup.telegram, "_resolve_store", return_value="ENTITY")
    mocker.patch.object(cleanup.telegram, "_list_topics", return_value={"citest": 10})

    removed = cleanup.purge(cfg, ["citest"])

    assert removed == 2
    client.delete_messages.assert_called_once_with("ENTITY", [11, 12])
    client.disconnect.assert_called_once()


def test_purge_skips_unknown_notebook(mocker) -> None:
    cfg = Config(storage_group_id=-100_777)
    client = _fake_client(mocker, [])
    mocker.patch.object(cleanup.telegram, "connect_authorized", return_value=client)
    mocker.patch.object(cleanup.telegram, "_resolve_store", return_value="ENTITY")
    mocker.patch.object(cleanup.telegram, "_list_topics", return_value={})

    assert cleanup.purge(cfg, ["citest", "mediatest"]) == 0
    client.delete_messages.assert_not_called()


# --- group teardown --------------------------------------------------------------


def test_delete_group_calls_delete_channel(mocker) -> None:
    cfg = Config(storage_group_id=-100_777)
    client = mocker.Mock()
    mocker.patch.object(cleanup.telegram, "connect_authorized", return_value=client)
    mocker.patch.object(cleanup.telegram, "_resolve_store", return_value="ENTITY")

    cleanup.delete_group(cfg)

    assert client.call_count == 1  # invoked the DeleteChannelRequest
    client.disconnect.assert_called_once()


# --- main: guard + dispatch ------------------------------------------------------


def test_main_purge_dispatch(mocker) -> None:
    mocker.patch.object(cleanup.config, "load", return_value=Config(storage_group_id=-100_9))
    purge = mocker.patch.object(cleanup, "purge", return_value=3)
    assert cleanup.main(["purge", "--notebook", "citest"]) == 0
    purge.assert_called_once()
    assert purge.call_args[0][1] == ["citest"]


def test_main_aborts_on_real_store(mocker, capsys) -> None:
    mocker.patch.object(
        cleanup.config, "load", return_value=Config(storage_group_id=cleanup.REAL_STORE_ID)
    )
    delete_group = mocker.patch.object(cleanup, "delete_group")
    assert cleanup.main(["group"]) == 1
    delete_group.assert_not_called()
    assert "real store" in capsys.readouterr().err.lower()


def test_main_defaults_to_test_notebooks(mocker) -> None:
    mocker.patch.object(cleanup.config, "load", return_value=Config(storage_group_id=-100_9))
    purge = mocker.patch.object(cleanup, "purge", return_value=0)
    assert cleanup.main(["purge"]) == 0
    assert purge.call_args[0][1] == cleanup.DEFAULT_TEST_NOTEBOOKS
