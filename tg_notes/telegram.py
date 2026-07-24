"""Telegram client layer for tg-notes.

Thin, deterministic wrapper around Telethon (MTProto). Importing ``telethon.sync`` first
turns the async client methods into blocking calls, so the rest of this module — and the
CLI on top of it — stays synchronous and easy to reason about. All Telegram I/O in the
project funnels through here; no AI logic lives in this layer.
"""
from __future__ import annotations

import os

import telethon.sync  # noqa: F401  # enables synchronous TelegramClient methods
from telethon import TelegramClient, utils
from telethon.tl.functions.channels import CreateChannelRequest
from telethon.tl.functions.messages import (
    CreateForumTopicRequest,
    GetForumTopicsRequest,
)

from .config import Config

#: Fixed title for the storage supergroup — part of the recovery tag (docs/architecture).
STORAGE_TITLE = "tg-notes storage"
#: About text; explains what the group is and warns against renaming it.
STORAGE_ABOUT = "tg-notes note store — managed by the tg-notes CLI. Do not rename."
#: Marker embedded in the pinned message so a lost store can be re-discovered (TGN-D2).
STORAGE_MARKER = "tg-notes-store:v1"
#: The address-book topic every store has.
CONTACTS_TOPIC = "contacts"
#: The notebook topic created by default when none is named.
DEFAULT_NOTEBOOK = "daily"


class NotConfiguredError(Exception):
    """Raised when ``api_id`` / ``api_hash`` are missing from local config."""


class NotAuthorizedError(Exception):
    """Raised when the local session is not logged in (run ``tg-notes login``)."""


def build_client(cfg: Config) -> TelegramClient:
    """Construct a Telethon client from local config (does not connect).

    Raises:
        NotConfiguredError: if ``cfg`` has no ``api_id`` / ``api_hash``.
    """
    if not cfg.is_configured():
        raise NotConfiguredError(
            "api_id/api_hash are not set — configure tg-notes before connecting"
        )
    return TelegramClient(cfg.session, cfg.api_id, cfg.api_hash)


def connect_authorized(cfg: Config) -> TelegramClient:
    """Return a connected, authorized client.

    Raises:
        NotConfiguredError: if the credentials are missing.
        NotAuthorizedError: if the session exists but is not logged in.
    """
    client = build_client(cfg)
    client.connect()
    if not client.is_user_authorized():
        client.disconnect()  # do not leak a connected client on the failure path
        raise NotAuthorizedError(
            "not logged in — run `tg-notes login` to authorize this session"
        )
    return client


def whoami(cfg: Config) -> dict:
    """Return the logged-in account identity, then disconnect.

    Raises:
        NotConfiguredError / NotAuthorizedError: as in :func:`connect_authorized`.
    """
    client = connect_authorized(cfg)
    try:
        me = client.get_me()
        return {"id": me.id, "username": me.username, "first_name": me.first_name}
    finally:
        client.disconnect()


def login(cfg: Config) -> dict:
    """Run the one-time interactive login and return the account identity.

    ``client.start()`` prompts for phone number, the login code, and 2FA password as
    needed, then writes the ``*.session`` file (full account access — locked to 0o600).
    Kept thin and side-effectful on purpose; the unit tests cover the pieces below it.

    Raises:
        NotConfiguredError: if the credentials are missing.
    """
    session_file = cfg.session
    if not session_file.endswith(".session"):
        session_file += ".session"
    parent = os.path.dirname(session_file)
    if parent:
        os.makedirs(parent, exist_ok=True)
        os.chmod(parent, 0o700)

    client = build_client(cfg)
    old_umask = os.umask(0o077)  # session file must be created private (0600), no race window
    try:
        client.start()  # interactive: phone / code / 2FA
        me = client.get_me()
        if os.path.exists(session_file):
            os.chmod(session_file, 0o600)
        return {"id": me.id, "username": me.username, "first_name": me.first_name}
    finally:
        os.umask(old_umask)
        client.disconnect()


def setup(cfg: Config, notebook: str = DEFAULT_NOTEBOOK) -> dict:
    """Provision (or attach to) the storage supergroup and its topics (TGN-3).

    Idempotent: if ``cfg.storage_group_id`` points at a resolvable group the store is
    attached and reused; otherwise a fresh forum supergroup is created and tagged with a
    pinned recovery marker. Either way the ``contacts`` topic and the given ``notebook``
    topic are ensured to exist. Persistence of the resolved id is the caller's job — this
    layer only does Telegram I/O and returns a summary.

    Returns:
        ``{"group_id": int, "created": bool, "title": str, "topics": {name: id}}``.

    Raises:
        NotConfiguredError / NotAuthorizedError: as in :func:`connect_authorized`.
    """
    client = connect_authorized(cfg)
    try:
        entity, created = _resolve_or_create(client, cfg)
        topics = _ensure_topics(client, entity, [CONTACTS_TOPIC, notebook])
        return {
            "group_id": utils.get_peer_id(entity),
            "created": created,
            "title": STORAGE_TITLE,
            "topics": topics,
        }
    finally:
        client.disconnect()


def _resolve_or_create(client: TelegramClient, cfg: Config) -> tuple[object, bool]:
    """Return ``(entity, created)`` — reuse the configured store or create a new one."""
    if cfg.storage_group_id:
        try:
            return client.get_entity(cfg.storage_group_id), False
        except (ValueError, TypeError):
            pass  # configured id no longer resolves → fall through and create a new store
    channel = _create_storage_group(client)
    _pin_marker(client, channel)
    return channel, True


def _create_storage_group(client: TelegramClient) -> object:
    """Create the private forum supergroup and return its channel entity."""
    result = client(
        CreateChannelRequest(
            title=STORAGE_TITLE,
            about=STORAGE_ABOUT,
            megagroup=True,
            forum=True,
        )
    )
    return result.chats[0]


def _pin_marker(client: TelegramClient, entity: object) -> object:
    """Post and pin the recovery marker in the store's General topic."""
    text = (
        f"{STORAGE_MARKER}\n\n"
        "Storage group for the tg-notes CLI. This pinned marker lets the tool "
        "re-discover the group if local config is lost. Do not unpin or delete."
    )
    message = client.send_message(entity, text)
    client.pin_message(entity, message)
    return message


def _list_topics(client: TelegramClient, entity: object) -> dict[str, int]:
    """Return a ``{title: topic_id}`` map of the store's forum topics."""
    result = client(
        GetForumTopicsRequest(
            peer=entity, offset_date=None, offset_id=0, offset_topic=0, limit=100
        )
    )
    return {topic.title: topic.id for topic in result.topics}


def _create_topic(client: TelegramClient, entity: object, title: str) -> int:
    """Create a forum topic and return its id."""
    updates = client(CreateForumTopicRequest(peer=entity, title=title))
    return _topic_id_from_updates(updates)


def _topic_id_from_updates(updates: object) -> int:
    """Extract the new topic's id from a ``CreateForumTopicRequest`` response.

    A forum topic's id is the id of the service message that opens it; scan the returned
    updates for the first one carrying a message.
    """
    for update in getattr(updates, "updates", []) or []:
        message = getattr(update, "message", None)
        message_id = getattr(message, "id", None)
        if isinstance(message_id, int):
            return message_id
    raise RuntimeError("could not determine the created topic id from the server response")


def _ensure_topics(
    client: TelegramClient, entity: object, names: list[str]
) -> dict[str, int]:
    """Ensure each named topic exists; create the missing ones. Returns their ids."""
    existing = _list_topics(client, entity)
    missing = [name for name in names if name not in existing]
    for name in missing:
        _create_topic(client, entity, name)
    if missing:
        existing = _list_topics(client, entity)  # re-list to pick up the new topic ids
    return {name: existing[name] for name in names}
