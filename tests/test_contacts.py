"""Tests for the contacts address book (TGN-6).

Two layers: the pure `tg_notes.contacts` (de)serializer, and the Telegram-layer
`contacts_list/set/remove` with Telethon fully mocked.
"""
from __future__ import annotations

import pytest

from tg_notes import contacts, telegram
from tg_notes.config import Config

# --- pure module: parse / serialize ----------------------------------------------


def test_parse_full_block() -> None:
    text = (
        "#contact boss\n"
        "name: Alice\n"
        "chat_id: @alice\n"
        "topic_id: 42\n"
        "mention: @alice\n"
        "style: keep it short and non-technical"
    )
    c = contacts.parse(text)
    assert c == contacts.Contact(
        key="boss",
        name="Alice",
        chat_id="@alice",
        topic_id=42,
        mention="@alice",
        style="keep it short and non-technical",
    )


def test_parse_returns_none_for_non_contact_text() -> None:
    assert contacts.parse("just a normal note #daily") is None
    assert contacts.parse("") is None


def test_parse_empty_fields_become_none() -> None:
    text = "#contact lead\nname:\nchat_id: me\ntopic_id:\nmention:\nstyle:"
    c = contacts.parse(text)
    assert c.chat_id == "me"
    assert c.name is None and c.topic_id is None and c.mention is None and c.style is None


def test_parse_non_int_topic_id_is_none() -> None:
    assert contacts.parse("#contact x\ntopic_id: abc").topic_id is None


def test_parse_keeps_colon_in_style() -> None:
    c = contacts.parse("#contact x\nchat_id: me\nstyle: rule: be terse")
    assert c.style == "rule: be terse"


def test_serialize_round_trips() -> None:
    c = contacts.Contact("boss", "Alice", "-1001", 7, "@alice", "be brief")
    assert contacts.parse(contacts.serialize(c)) == c


def test_serialize_round_trips_with_none_fields() -> None:
    c = contacts.Contact("lead", chat_id="me")
    assert contacts.parse(contacts.serialize(c)) == c


def test_serialize_collapses_newlines_to_keep_block_parseable() -> None:
    c = contacts.Contact("x", chat_id="me", style="line one\nline two")
    assert "line one line two" in contacts.serialize(c)
    assert contacts.parse(contacts.serialize(c)).style == "line one line two"


# --- Telegram layer: contacts_list / set / remove --------------------------------


def configured(**over) -> Config:
    base = {"api_id": 42, "api_hash": "cafe", "storage_group_id": -1004432534270}
    base.update(over)
    return Config(**base)


def _authorized_client(mocker):
    fake_cls = mocker.patch("tg_notes.telegram.TelegramClient")
    instance = fake_cls.return_value
    instance.is_user_authorized.return_value = True
    return instance


def _contact_msg(mocker, mid, contact):
    return mocker.Mock(id=mid, text=contacts.serialize(contact))


def test_contacts_list_parses_and_sorts_by_key(mocker) -> None:
    instance = _authorized_client(mocker)
    entity = instance.get_entity.return_value
    mocker.patch("tg_notes.telegram._list_topics", return_value={"contacts": 4})
    boss = contacts.Contact("boss", chat_id="@boss")
    lead = contacts.Contact("lead", chat_id="me")
    instance.iter_messages.return_value = [
        _contact_msg(mocker, 20, lead),
        mocker.Mock(id=21, text="not a contact block"),
        _contact_msg(mocker, 19, boss),
    ]

    result = telegram.contacts_list(configured())

    instance.iter_messages.assert_called_once_with(entity, reply_to=4)
    assert [c["key"] for c in result] == ["boss", "lead"]  # sorted, non-contact skipped
    instance.disconnect.assert_called_once_with()


def test_contacts_list_empty_when_no_contacts_topic(mocker) -> None:
    instance = _authorized_client(mocker)
    mocker.patch("tg_notes.telegram._list_topics", return_value={"daily": 5})

    assert telegram.contacts_list(configured()) == []
    instance.iter_messages.assert_not_called()


def test_contacts_list_raises_when_not_set_up(mocker) -> None:
    fake_cls = mocker.patch("tg_notes.telegram.TelegramClient")
    with pytest.raises(telegram.NotSetUpError):
        telegram.contacts_list(configured(storage_group_id=None))
    fake_cls.assert_not_called()


def test_contacts_set_creates_new_contact(mocker) -> None:
    instance = _authorized_client(mocker)
    entity = instance.get_entity.return_value
    mocker.patch("tg_notes.telegram._ensure_topics", return_value={"contacts": 4})
    instance.iter_messages.return_value = []  # no existing contact with this key

    result = telegram.contacts_set(configured(), "boss", chat_id="@boss", name="Alice")

    assert result["created"] is True
    instance.send_message.assert_called_once()
    args = instance.send_message.call_args
    assert args.args[0] is entity
    assert args.kwargs["reply_to"] == 4
    posted = contacts.parse(args.args[1])
    assert posted == contacts.Contact("boss", name="Alice", chat_id="@boss")
    instance.edit_message.assert_not_called()


def test_contacts_set_new_without_chat_id_raises(mocker) -> None:
    instance = _authorized_client(mocker)
    mocker.patch("tg_notes.telegram._ensure_topics", return_value={"contacts": 4})
    instance.iter_messages.return_value = []

    with pytest.raises(ValueError):
        telegram.contacts_set(configured(), "boss", name="Alice")

    instance.send_message.assert_not_called()


def test_contacts_set_updates_existing_and_merges(mocker) -> None:
    instance = _authorized_client(mocker)
    entity = instance.get_entity.return_value
    mocker.patch("tg_notes.telegram._ensure_topics", return_value={"contacts": 4})
    existing = contacts.Contact("boss", name="Alice", chat_id="@boss", style="old")
    instance.iter_messages.return_value = [_contact_msg(mocker, 19, existing)]

    result = telegram.contacts_set(configured(), "boss", style="new style")

    assert result["created"] is False
    instance.edit_message.assert_called_once()
    args = instance.edit_message.call_args.args
    assert args[0] is entity and args[1] == 19
    merged = contacts.parse(args[2])
    # provided field overridden, others kept from the existing record
    assert merged == contacts.Contact("boss", name="Alice", chat_id="@boss", style="new style")
    instance.send_message.assert_not_called()


def test_contacts_remove_deletes_when_found(mocker) -> None:
    instance = _authorized_client(mocker)
    entity = instance.get_entity.return_value
    mocker.patch("tg_notes.telegram._list_topics", return_value={"contacts": 4})
    instance.iter_messages.return_value = [
        _contact_msg(mocker, 19, contacts.Contact("boss", chat_id="@boss"))
    ]

    result = telegram.contacts_remove(configured(), "boss")

    assert result == {"key": "boss", "removed": True}
    instance.delete_messages.assert_called_once_with(entity, [19])


def test_contacts_remove_missing_key_is_noop(mocker) -> None:
    instance = _authorized_client(mocker)
    mocker.patch("tg_notes.telegram._list_topics", return_value={"contacts": 4})
    instance.iter_messages.return_value = []

    result = telegram.contacts_remove(configured(), "ghost")

    assert result == {"key": "ghost", "removed": False}
    instance.delete_messages.assert_not_called()


def test_contacts_remove_no_contacts_topic_is_noop(mocker) -> None:
    instance = _authorized_client(mocker)
    mocker.patch("tg_notes.telegram._list_topics", return_value={"daily": 5})

    assert telegram.contacts_remove(configured(), "boss") == {"key": "boss", "removed": False}
    instance.delete_messages.assert_not_called()


def test_contacts_set_disconnects_on_error(mocker) -> None:
    instance = _authorized_client(mocker)
    mocker.patch("tg_notes.telegram._ensure_topics", side_effect=RuntimeError("boom"))

    with pytest.raises(RuntimeError):
        telegram.contacts_set(configured(), "boss", chat_id="@boss")

    instance.disconnect.assert_called_once_with()
