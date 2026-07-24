"""Tests for `tg-notes setup` — the storage-group provisioning layer (TGN-3).

Telethon is fully mocked (``tg_notes.telegram.TelegramClient`` and the raw request
classes are patched), so the suite is offline and needs no session. The orchestrator
(:func:`telegram.setup`) is tested against patched helpers; each helper is tested on its
own against the patched Telethon request classes.
"""
from __future__ import annotations

import pytest

from tg_notes import telegram
from tg_notes.config import Config


def configured(**over) -> Config:
    base = {"api_id": 42, "api_hash": "cafe", "session_path": "/tmp/x.session"}
    base.update(over)
    return Config(**base)


# --- orchestrator: setup() -------------------------------------------------------


def test_setup_creates_group_when_none_configured(mocker) -> None:
    fake_cls = mocker.patch("tg_notes.telegram.TelegramClient")
    instance = fake_cls.return_value
    instance.is_user_authorized.return_value = True

    channel = mocker.Mock(name="channel")
    mocker.patch("tg_notes.telegram._create_storage_group", return_value=channel)
    pin = mocker.patch("tg_notes.telegram._pin_marker")
    mocker.patch(
        "tg_notes.telegram._ensure_topics", return_value={"contacts": 2, "daily": 3}
    )
    mocker.patch("tg_notes.telegram.utils.get_peer_id", return_value=-1001234)

    result = telegram.setup(configured())

    assert result == {
        "group_id": -1001234,
        "created": True,
        "title": telegram.STORAGE_TITLE,
        "topics": {"contacts": 2, "daily": 3},
    }
    pin.assert_called_once_with(instance, channel)  # marker pinned on a fresh group
    instance.disconnect.assert_called_once_with()


def test_setup_attaches_to_existing_group(mocker) -> None:
    fake_cls = mocker.patch("tg_notes.telegram.TelegramClient")
    instance = fake_cls.return_value
    instance.is_user_authorized.return_value = True
    entity = mocker.Mock(name="entity")
    instance.get_entity.return_value = entity

    create = mocker.patch("tg_notes.telegram._create_storage_group")
    pin = mocker.patch("tg_notes.telegram._pin_marker")
    mocker.patch(
        "tg_notes.telegram._ensure_topics", return_value={"contacts": 2, "daily": 3}
    )
    mocker.patch("tg_notes.telegram.utils.get_peer_id", return_value=-1009999)

    result = telegram.setup(configured(storage_group_id=-1009999))

    assert result["created"] is False
    assert result["group_id"] == -1009999
    instance.get_entity.assert_called_once_with(-1009999)
    create.assert_not_called()
    pin.assert_not_called()  # never re-tag an existing store
    instance.disconnect.assert_called_once_with()


def test_setup_recreates_when_stored_group_unresolvable(mocker) -> None:
    fake_cls = mocker.patch("tg_notes.telegram.TelegramClient")
    instance = fake_cls.return_value
    instance.is_user_authorized.return_value = True
    instance.get_entity.side_effect = ValueError("no such entity")

    channel = mocker.Mock(name="channel")
    create = mocker.patch("tg_notes.telegram._create_storage_group", return_value=channel)
    pin = mocker.patch("tg_notes.telegram._pin_marker")
    mocker.patch(
        "tg_notes.telegram._ensure_topics", return_value={"contacts": 2, "daily": 3}
    )
    mocker.patch("tg_notes.telegram.utils.get_peer_id", return_value=-1005555)

    result = telegram.setup(configured(storage_group_id=-1000000))

    assert result["created"] is True
    create.assert_called_once_with(instance)
    pin.assert_called_once_with(instance, channel)


def test_setup_uses_custom_notebook_name(mocker) -> None:
    fake_cls = mocker.patch("tg_notes.telegram.TelegramClient")
    instance = fake_cls.return_value
    instance.is_user_authorized.return_value = True
    mocker.patch("tg_notes.telegram._create_storage_group", return_value=mocker.Mock())
    mocker.patch("tg_notes.telegram._pin_marker")
    ensure = mocker.patch(
        "tg_notes.telegram._ensure_topics", return_value={"contacts": 2, "weekly": 4}
    )
    mocker.patch("tg_notes.telegram.utils.get_peer_id", return_value=-100)

    telegram.setup(configured(), notebook="weekly")

    ensure.assert_called_once_with(instance, mocker.ANY, ["contacts", "weekly"])


def test_setup_raises_when_not_authorized(mocker) -> None:
    fake_cls = mocker.patch("tg_notes.telegram.TelegramClient")
    instance = fake_cls.return_value
    instance.is_user_authorized.return_value = False
    create = mocker.patch("tg_notes.telegram._create_storage_group")

    with pytest.raises(telegram.NotAuthorizedError):
        telegram.setup(configured())

    create.assert_not_called()
    instance.disconnect.assert_called_once_with()


def test_setup_disconnects_even_when_ensure_topics_fails(mocker) -> None:
    fake_cls = mocker.patch("tg_notes.telegram.TelegramClient")
    instance = fake_cls.return_value
    instance.is_user_authorized.return_value = True
    mocker.patch("tg_notes.telegram._create_storage_group", return_value=mocker.Mock())
    mocker.patch("tg_notes.telegram._pin_marker")
    mocker.patch("tg_notes.telegram._ensure_topics", side_effect=RuntimeError("boom"))

    with pytest.raises(RuntimeError):
        telegram.setup(configured())

    instance.disconnect.assert_called_once_with()


# --- helper: _create_storage_group -----------------------------------------------


def test_create_storage_group_requests_forum_megagroup(mocker) -> None:
    req = mocker.patch("tg_notes.telegram.CreateChannelRequest")
    client = mocker.Mock()
    channel = mocker.Mock()
    client.return_value.chats = [channel]

    result = telegram._create_storage_group(client)

    req.assert_called_once_with(
        title=telegram.STORAGE_TITLE,
        about=telegram.STORAGE_ABOUT,
        megagroup=True,
        forum=True,
    )
    client.assert_called_once_with(req.return_value)
    assert result is channel


# --- helper: _list_topics --------------------------------------------------------


def test_list_topics_maps_title_to_id(mocker) -> None:
    req = mocker.patch("tg_notes.telegram.GetForumTopicsRequest")
    client = mocker.Mock()
    general = mocker.Mock(id=1)
    general.title = "General"
    contacts = mocker.Mock(id=2)
    contacts.title = "contacts"
    client.return_value.topics = [general, contacts]
    entity = mocker.Mock()

    result = telegram._list_topics(client, entity)

    assert result == {"General": 1, "contacts": 2}
    req.assert_called_once_with(
        peer=entity, offset_date=None, offset_id=0, offset_topic=0, limit=100
    )
    client.assert_called_once_with(req.return_value)


# --- helper: _create_topic / _topic_id_from_updates ------------------------------


def test_create_topic_returns_new_topic_id(mocker) -> None:
    req = mocker.patch("tg_notes.telegram.CreateForumTopicRequest")
    parse = mocker.patch("tg_notes.telegram._topic_id_from_updates", return_value=7)
    client = mocker.Mock()
    entity = mocker.Mock()

    result = telegram._create_topic(client, entity, "daily")

    req.assert_called_once_with(peer=entity, title="daily")
    client.assert_called_once_with(req.return_value)
    parse.assert_called_once_with(client.return_value)
    assert result == 7


def test_topic_id_from_updates_reads_first_message_id(mocker) -> None:
    without_message = mocker.Mock(spec=[])  # accessing .message raises → treated as None
    message = mocker.Mock(id=42)
    with_message = mocker.Mock(message=message)
    updates = mocker.Mock(updates=[without_message, with_message])

    assert telegram._topic_id_from_updates(updates) == 42


def test_topic_id_from_updates_raises_when_absent(mocker) -> None:
    updates = mocker.Mock(updates=[])

    with pytest.raises(RuntimeError):
        telegram._topic_id_from_updates(updates)


# --- helper: _ensure_topics ------------------------------------------------------


def test_ensure_topics_creates_only_missing(mocker) -> None:
    list_topics = mocker.patch(
        "tg_notes.telegram._list_topics",
        side_effect=[
            {"General": 1, "contacts": 2},
            {"General": 1, "contacts": 2, "daily": 3},
        ],
    )
    create = mocker.patch("tg_notes.telegram._create_topic")
    client = mocker.Mock()
    entity = mocker.Mock()

    result = telegram._ensure_topics(client, entity, ["contacts", "daily"])

    create.assert_called_once_with(client, entity, "daily")
    assert result == {"contacts": 2, "daily": 3}
    assert list_topics.call_count == 2  # re-listed to pick up the new topic id


def test_ensure_topics_is_noop_when_all_present(mocker) -> None:
    list_topics = mocker.patch(
        "tg_notes.telegram._list_topics",
        return_value={"General": 1, "contacts": 2, "daily": 3},
    )
    create = mocker.patch("tg_notes.telegram._create_topic")

    result = telegram._ensure_topics(mocker.Mock(), mocker.Mock(), ["contacts", "daily"])

    create.assert_not_called()
    assert list_topics.call_count == 1  # no second round-trip when nothing is created
    assert result == {"contacts": 2, "daily": 3}


# --- helper: _pin_marker ---------------------------------------------------------


def test_pin_marker_sends_and_pins_marker(mocker) -> None:
    client = mocker.Mock()
    entity = mocker.Mock()
    message = client.send_message.return_value

    result = telegram._pin_marker(client, entity)

    client.send_message.assert_called_once()
    args, _ = client.send_message.call_args
    assert args[0] is entity
    assert telegram.STORAGE_MARKER in args[1]  # marker text carries the recovery tag
    client.pin_message.assert_called_once_with(entity, message)
    assert result is message
