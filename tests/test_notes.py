"""Tests for `tg-notes note add` — appending notes to a notebook topic (TGN-4).

Telethon is fully mocked, so the suite is offline. `note_add` is tested against a mocked
client and a patched `_ensure_topics` (its create-on-demand behavior is covered in
`test_setup.py`); the note-composition helpers are tested on their own.
"""
from __future__ import annotations

import datetime

import pytest

from tg_notes import telegram
from tg_notes.config import Config

FIXED_DATE = datetime.datetime(2026, 7, 24, 12, 0, tzinfo=datetime.UTC)


def configured(**over) -> Config:
    base = {
        "api_id": 42,
        "api_hash": "cafe",
        "session_path": "/tmp/x.session",
        "storage_group_id": -1004432534270,
    }
    base.update(over)
    return Config(**base)


def _authorized_client(mocker):
    fake_cls = mocker.patch("tg_notes.telegram.TelegramClient")
    instance = fake_cls.return_value
    instance.is_user_authorized.return_value = True
    message = mocker.Mock(id=99, date=FIXED_DATE)
    instance.send_message.return_value = message
    return instance


# --- note_add() ------------------------------------------------------------------


def test_note_add_raises_when_not_set_up(mocker) -> None:
    fake_cls = mocker.patch("tg_notes.telegram.TelegramClient")

    with pytest.raises(telegram.NotSetUpError):
        telegram.note_add(configured(storage_group_id=None), notebook="daily", text="x")

    fake_cls.assert_not_called()  # fail fast, before any connection


def test_note_add_posts_into_notebook_topic(mocker) -> None:
    instance = _authorized_client(mocker)
    entity = instance.get_entity.return_value
    ensure = mocker.patch("tg_notes.telegram._ensure_topics", return_value={"daily": 5})

    result = telegram.note_add(configured(), notebook="daily", text="hello")

    instance.get_entity.assert_called_once_with(-1004432534270)
    ensure.assert_called_once_with(instance, entity, ["daily"])
    instance.send_message.assert_called_once_with(entity, "hello", reply_to=5)
    assert result == {
        "notebook": "daily",
        "topic_id": 5,
        "message_id": 99,
        "date": FIXED_DATE.isoformat(),
    }
    instance.disconnect.assert_called_once_with()


def test_note_add_appends_hashtags(mocker) -> None:
    instance = _authorized_client(mocker)
    mocker.patch("tg_notes.telegram._ensure_topics", return_value={"daily": 5})

    telegram.note_add(configured(), notebook="daily", text="hello", hashtags=["foo", "#bar"])

    body = instance.send_message.call_args.args[1]
    assert body == "hello\n\n#foo #bar"


def test_note_add_raises_on_empty_note(mocker) -> None:
    instance = _authorized_client(mocker)
    mocker.patch("tg_notes.telegram._ensure_topics", return_value={"daily": 5})

    with pytest.raises(ValueError):
        telegram.note_add(configured(), notebook="daily", text="   ")

    # fail fast: an empty note is rejected before any connection is opened
    instance.connect.assert_not_called()
    instance.send_message.assert_not_called()


def test_note_add_raises_when_group_unresolvable(mocker) -> None:
    instance = _authorized_client(mocker)
    instance.get_entity.side_effect = ValueError("gone")

    with pytest.raises(telegram.NotSetUpError):
        telegram.note_add(configured(), notebook="daily", text="hi")

    instance.disconnect.assert_called_once_with()


def test_note_add_disconnects_when_send_fails(mocker) -> None:
    instance = _authorized_client(mocker)
    mocker.patch("tg_notes.telegram._ensure_topics", return_value={"daily": 5})
    instance.send_message.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError):
        telegram.note_add(configured(), notebook="daily", text="hi")

    instance.disconnect.assert_called_once_with()


def test_note_add_propagates_not_authorized(mocker) -> None:
    fake_cls = mocker.patch("tg_notes.telegram.TelegramClient")
    fake_cls.return_value.is_user_authorized.return_value = False

    with pytest.raises(telegram.NotAuthorizedError):
        telegram.note_add(configured(), notebook="daily", text="hi")


# --- helpers: _compose_note / _normalize_hashtag ---------------------------------


def test_compose_note_plain_is_trimmed() -> None:
    assert telegram._compose_note("  hello  ", None) == "hello"


def test_compose_note_appends_tags_on_a_blank_line() -> None:
    assert telegram._compose_note("hello", ["a", "b"]) == "hello\n\n#a #b"


def test_compose_note_tags_only_has_no_leading_blank() -> None:
    assert telegram._compose_note("", ["a"]) == "#a"


def test_compose_note_ignores_blank_tags() -> None:
    assert telegram._compose_note("hi", ["", "  ", "x"]) == "hi\n\n#x"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("x", "#x"), ("#x", "#x"), ("  y ", "#y"), ("##z", "#z")],
)
def test_normalize_hashtag(raw: str, expected: str) -> None:
    assert telegram._normalize_hashtag(raw) == expected
