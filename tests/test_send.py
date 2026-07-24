"""Tests for `tg-notes send` — publishing to a contact (TGN-7). Telethon fully mocked."""
from __future__ import annotations

import datetime

import pytest

from tg_notes import contacts, telegram
from tg_notes.config import Config

FIXED = datetime.datetime(2026, 7, 24, 12, 0, tzinfo=datetime.UTC)


def configured(**over) -> Config:
    base = {"api_id": 42, "api_hash": "cafe", "storage_group_id": -1004432534270}
    base.update(over)
    return Config(**base)


def _client(mocker):
    fake = mocker.patch("tg_notes.telegram.TelegramClient")
    inst = fake.return_value
    inst.is_user_authorized.return_value = True
    inst.send_message.return_value = mocker.Mock(id=100, date=FIXED)
    return inst


def _with_contact(mocker, contact):
    mocker.patch("tg_notes.telegram._list_topics", return_value={"contacts": 4})
    mocker.patch(
        "tg_notes.telegram._find_contact", return_value=(mocker.Mock(id=9), contact)
    )


# --- send() ----------------------------------------------------------------------


def test_send_posts_to_plain_chat(mocker) -> None:
    inst = _client(mocker)
    _with_contact(mocker, contacts.Contact("boss", chat_id="@boss"))

    result = telegram.send(configured(), "boss", "hello")

    inst.get_entity.assert_any_call("@boss")  # target resolved from chat_id
    args = inst.send_message.call_args
    assert args.args[0] is inst.get_entity.return_value
    assert args.args[1] == "hello"
    assert args.kwargs["reply_to"] is None  # no topic → plain chat
    assert result["sent"] is True
    assert result["message_id"] == 100
    assert result["chat_id"] == "@boss" and result["topic_id"] is None
    inst.disconnect.assert_called_once_with()


def test_send_prepends_mention_and_targets_topic(mocker) -> None:
    inst = _client(mocker)
    _with_contact(
        mocker,
        contacts.Contact("team", chat_id="-1001112223334", topic_id=12, mention="@team"),
    )

    result = telegram.send(configured(), "team", "  status update  ")

    inst.get_entity.assert_any_call(-1001112223334)  # numeric chat_id coerced to int
    args = inst.send_message.call_args
    assert args.args[1] == "@team\n\nstatus update"  # mention prepended, body trimmed
    assert args.kwargs["reply_to"] == 12
    assert result["text"] == "@team\n\nstatus update"
    assert result["topic_id"] == 12


def test_send_dry_run_composes_without_sending(mocker) -> None:
    inst = _client(mocker)
    _with_contact(mocker, contacts.Contact("boss", chat_id="@boss", mention="@boss"))

    result = telegram.send(configured(), "boss", "hi", dry_run=True)

    assert result == {
        "contact": "boss",
        "chat_id": "@boss",
        "topic_id": None,
        "text": "@boss\n\nhi",
        "sent": False,
    }
    inst.send_message.assert_not_called()
    inst.disconnect.assert_called_once_with()


def test_send_unknown_contact_raises(mocker) -> None:
    inst = _client(mocker)
    mocker.patch("tg_notes.telegram._list_topics", return_value={"contacts": 4})
    mocker.patch("tg_notes.telegram._find_contact", return_value=(None, None))

    with pytest.raises(telegram.ContactNotFoundError):
        telegram.send(configured(), "ghost", "hi")

    inst.send_message.assert_not_called()
    inst.disconnect.assert_called_once_with()


def test_send_no_contacts_topic_raises_contact_not_found(mocker) -> None:
    inst = _client(mocker)
    mocker.patch("tg_notes.telegram._list_topics", return_value={"daily": 5})

    with pytest.raises(telegram.ContactNotFoundError):
        telegram.send(configured(), "boss", "hi")

    inst.send_message.assert_not_called()


def test_send_empty_text_raises_before_connecting(mocker) -> None:
    fake = mocker.patch("tg_notes.telegram.TelegramClient")

    with pytest.raises(ValueError):
        telegram.send(configured(), "boss", "   ")

    fake.assert_not_called()


def test_send_raises_when_not_set_up(mocker) -> None:
    fake = mocker.patch("tg_notes.telegram.TelegramClient")

    with pytest.raises(telegram.NotSetUpError):
        telegram.send(configured(storage_group_id=None), "boss", "hi")

    fake.assert_not_called()


def test_send_disconnects_on_error(mocker) -> None:
    inst = _client(mocker)
    _with_contact(mocker, contacts.Contact("boss", chat_id="@boss"))
    inst.send_message.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError):
        telegram.send(configured(), "boss", "hi")

    inst.disconnect.assert_called_once_with()


def test_send_propagates_not_authorized(mocker) -> None:
    fake = mocker.patch("tg_notes.telegram.TelegramClient")
    fake.return_value.is_user_authorized.return_value = False

    with pytest.raises(telegram.NotAuthorizedError):
        telegram.send(configured(), "boss", "hi")


# --- helpers ---------------------------------------------------------------------


def test_compose_outgoing_prepends_mention() -> None:
    assert telegram._compose_outgoing("  hi  ", "@x") == "@x\n\nhi"
    assert telegram._compose_outgoing("hi", None) == "hi"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("-1001112223334", -1001112223334), ("@user", "@user"), ("me", "me")],
)
def test_target_from_chat_id(raw, expected) -> None:
    assert telegram._target_from_chat_id(raw) == expected
