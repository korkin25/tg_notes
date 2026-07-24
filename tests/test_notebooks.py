"""Tests for `tg-notes notebooks list` (TGN-8). Telethon fully mocked."""
from __future__ import annotations

import pytest

from tg_notes import telegram
from tg_notes.config import Config


def configured(**over) -> Config:
    base = {"api_id": 42, "api_hash": "cafe", "storage_group_id": -1004432534270}
    base.update(over)
    return Config(**base)


def _authorized(mocker):
    fake = mocker.patch("tg_notes.telegram.TelegramClient")
    inst = fake.return_value
    inst.is_user_authorized.return_value = True
    return inst


def test_notebooks_list_excludes_reserved_topics_and_sorts(mocker) -> None:
    inst = _authorized(mocker)
    mocker.patch(
        "tg_notes.telegram._list_topics",
        return_value={"General": 1, "contacts": 4, "weekly": 6, "daily": 5},
    )

    result = telegram.notebooks_list(configured())

    assert result == [
        {"name": "daily", "topic_id": 5},
        {"name": "weekly", "topic_id": 6},
    ]
    inst.disconnect.assert_called_once_with()


def test_notebooks_list_empty_when_only_reserved(mocker) -> None:
    _authorized(mocker)
    mocker.patch("tg_notes.telegram._list_topics", return_value={"General": 1, "contacts": 4})

    assert telegram.notebooks_list(configured()) == []


def test_notebooks_list_raises_when_not_set_up(mocker) -> None:
    fake = mocker.patch("tg_notes.telegram.TelegramClient")
    with pytest.raises(telegram.NotSetUpError):
        telegram.notebooks_list(configured(storage_group_id=None))
    fake.assert_not_called()


def test_notebooks_list_disconnects_on_error(mocker) -> None:
    inst = _authorized(mocker)
    mocker.patch("tg_notes.telegram._list_topics", side_effect=RuntimeError("boom"))

    with pytest.raises(RuntimeError):
        telegram.notebooks_list(configured())

    inst.disconnect.assert_called_once_with()


def test_notebooks_list_propagates_not_authorized(mocker) -> None:
    fake = mocker.patch("tg_notes.telegram.TelegramClient")
    fake.return_value.is_user_authorized.return_value = False

    with pytest.raises(telegram.NotAuthorizedError):
        telegram.notebooks_list(configured())
