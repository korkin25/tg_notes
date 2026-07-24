"""Telegram client layer for tg-notes.

Thin, deterministic wrapper around Telethon (MTProto). Importing ``telethon.sync`` first
turns the async client methods into blocking calls, so the rest of this module — and the
CLI on top of it — stays synchronous and easy to reason about. All Telegram I/O in the
project funnels through here; no AI logic lives in this layer.
"""
from __future__ import annotations

import telethon.sync  # noqa: F401  # enables synchronous TelegramClient methods
from telethon import TelegramClient, utils
from telethon.errors import MessageNotModifiedError
from telethon.tl.functions.channels import CreateChannelRequest
from telethon.tl.functions.messages import (
    CreateForumTopicRequest,
    GetForumTopicsRequest,
)

from . import contacts as contacts_mod
from . import secrets
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
#: Topics that are not notebooks (the forum default and the address book).
RESERVED_TOPICS = frozenset({"General", CONTACTS_TOPIC})


class NotConfiguredError(Exception):
    """Raised when ``api_id`` / ``api_hash`` are missing from local config."""


class NotAuthorizedError(Exception):
    """Raised when the local session is not logged in (run ``tg-notes login``)."""


class NotSetUpError(Exception):
    """Raised when no storage group is configured/resolvable (run ``tg-notes setup``)."""


class ContactNotFoundError(Exception):
    """Raised when ``send`` targets a contact key absent from the address book."""


def build_client(cfg: Config) -> TelegramClient:
    """Construct a Telethon client from local config (does not connect).

    Raises:
        NotConfiguredError: if ``cfg`` has no ``api_id`` / ``api_hash``.
    """
    backend = secrets.get_backend(cfg)
    if not backend.is_configured():
        raise NotConfiguredError(
            "api_id/api_hash are not set — configure tg-notes before connecting"
        )
    return TelegramClient(backend.session_arg(), cfg.api_id, backend.api_hash())


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
    needed. Where the resulting session is persisted depends on the active secrets backend
    (a ``*.session`` file locked to 0o600, or a ``StringSession`` in the keyring).

    Raises:
        NotConfiguredError: if the credentials are missing.
    """
    backend = secrets.get_backend(cfg)
    with backend.login_guard():
        client = build_client(cfg)
        try:
            client.start()  # interactive: phone / code / 2FA
            me = client.get_me()
            backend.persist_login(client)  # file: chmod 600; keyring: store StringSession
            return {"id": me.id, "username": me.username, "first_name": me.first_name}
        finally:
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


def note_add(
    cfg: Config, notebook: str, text: str, hashtags: list[str] | None = None
) -> dict:
    """Append a note to a notebook topic, creating the topic on demand (TGN-4).

    Returns ``{"notebook", "topic_id", "message_id", "date"}`` for the posted note.

    Raises:
        NotSetUpError: if no storage group is configured or it no longer resolves.
        NotConfiguredError / NotAuthorizedError: as in :func:`connect_authorized`.
        ValueError: if the composed note is empty.
    """
    if not cfg.storage_group_id:
        raise NotSetUpError(
            "no storage group configured — run `tg-notes setup` first"
        )
    body = _compose_note(text, hashtags)
    if not body:
        raise ValueError("refusing to post an empty note")

    client = connect_authorized(cfg)
    try:
        entity = _resolve_store(client, cfg)
        topic_id = _ensure_topics(client, entity, [notebook])[notebook]
        message = client.send_message(entity, body, reply_to=topic_id)
        return {
            "notebook": notebook,
            "topic_id": topic_id,
            "message_id": message.id,
            "date": _message_date_iso(message),
        }
    finally:
        client.disconnect()


def notes_list(cfg: Config, notebook: str, since: object | None = None) -> list[dict]:
    """Return the raw notes of a notebook topic, oldest first (TGN-5).

    Feeds compilation: each note is ``{"message_id", "date", "text"}``. Service/empty
    messages (e.g. the topic opener) are skipped. ``since`` is an optional lower bound on
    the message date (a timezone-aware ``datetime``). An unknown notebook yields ``[]``.

    Raises:
        NotSetUpError: if no storage group is configured or it no longer resolves.
        NotConfiguredError / NotAuthorizedError: as in :func:`connect_authorized`.
    """
    if not cfg.storage_group_id:
        raise NotSetUpError(
            "no storage group configured — run `tg-notes setup` first"
        )
    client = connect_authorized(cfg)
    try:
        entity = _resolve_store(client, cfg)
        topic_id = _list_topics(client, entity).get(notebook)
        if topic_id is None:
            return []  # notebook never created → no notes, and nothing to fetch
        notes = []
        for message in client.iter_messages(entity, reply_to=topic_id):
            if since is not None and message.date is not None and message.date < since:
                continue
            if not message.text:
                continue  # skip the topic-opening service message and any empty ones
            notes.append(
                {
                    "message_id": message.id,
                    "date": _message_date_iso(message),
                    "text": message.text,
                }
            )
        notes.sort(key=lambda note: note["message_id"])  # oldest first
        return notes
    finally:
        client.disconnect()


def notebooks_list(cfg: Config) -> list[dict]:
    """Return the storage group's notebook topics as ``{name, topic_id}``, sorted (TGN-8).

    Excludes the reserved topics (``General``, ``contacts``) — only real notebooks.

    Raises:
        NotSetUpError / NotConfiguredError / NotAuthorizedError: store/auth problems.
    """
    if not cfg.storage_group_id:
        raise NotSetUpError("no storage group configured — run `tg-notes setup` first")
    client = connect_authorized(cfg)
    try:
        entity = _resolve_store(client, cfg)
        notebooks = [
            {"name": name, "topic_id": topic_id}
            for name, topic_id in _list_topics(client, entity).items()
            if name not in RESERVED_TOPICS
        ]
        notebooks.sort(key=lambda entry: entry["name"])
        return notebooks
    finally:
        client.disconnect()


def contacts_list(cfg: Config) -> list[dict]:
    """Return the address book (one entry per contact message), sorted by key (TGN-6)."""
    if not cfg.storage_group_id:
        raise NotSetUpError("no storage group configured — run `tg-notes setup` first")
    client = connect_authorized(cfg)
    try:
        entity = _resolve_store(client, cfg)
        topic_id = _list_topics(client, entity).get(CONTACTS_TOPIC)
        if topic_id is None:
            return []
        found = []
        for message in client.iter_messages(entity, reply_to=topic_id):
            contact = contacts_mod.parse(message.text or "")
            if contact is not None:
                found.append(contact.to_dict())
        found.sort(key=lambda entry: entry["key"])
        return found
    finally:
        client.disconnect()


def contacts_set(
    cfg: Config,
    key: str,
    *,
    chat_id: str | None = None,
    name: str | None = None,
    topic_id: int | None = None,
    mention: str | None = None,
    style: str | None = None,
) -> dict:
    """Create or update a contact (TGN-6).

    Only the provided fields override an existing record; a brand-new contact needs a
    ``chat_id``. Returns the stored contact plus ``"created"`` (True when newly added).
    """
    if not cfg.storage_group_id:
        raise NotSetUpError("no storage group configured — run `tg-notes setup` first")
    client = connect_authorized(cfg)
    try:
        entity = _resolve_store(client, cfg)
        contacts_topic = _ensure_topics(client, entity, [CONTACTS_TOPIC])[CONTACTS_TOPIC]
        message, existing = _find_contact(client, entity, contacts_topic, key)
        merged = _merge_contact(
            key, existing, chat_id=chat_id, name=name, topic_id=topic_id,
            mention=mention, style=style,
        )
        text = contacts_mod.serialize(merged)
        if message is not None:
            try:
                client.edit_message(entity, message.id, text)
            except MessageNotModifiedError:
                pass  # identical content — nothing to change, still a successful set
            created = False
        else:
            client.send_message(entity, text, reply_to=contacts_topic)
            created = True
        return {**merged.to_dict(), "created": created}
    finally:
        client.disconnect()


def contacts_remove(cfg: Config, key: str) -> dict:
    """Delete a contact's message. Returns ``{"key", "removed"}`` (TGN-6)."""
    if not cfg.storage_group_id:
        raise NotSetUpError("no storage group configured — run `tg-notes setup` first")
    client = connect_authorized(cfg)
    try:
        entity = _resolve_store(client, cfg)
        contacts_topic = _list_topics(client, entity).get(CONTACTS_TOPIC)
        if contacts_topic is None:
            return {"key": key, "removed": False}
        message, _ = _find_contact(client, entity, contacts_topic, key)
        if message is None:
            return {"key": key, "removed": False}
        client.delete_messages(entity, [message.id])
        return {"key": key, "removed": True}
    finally:
        client.disconnect()


def send(cfg: Config, contact_key: str, text: str, *, dry_run: bool = False) -> dict:
    """Post ``text`` to a contact's chat/topic, as the user (TGN-7).

    Looks the contact up in the address book, prepends its ``mention`` (if any), and posts
    into its ``chat_id`` — into a forum topic when the contact has a ``topic_id``. With
    ``dry_run`` the message is composed and returned but nothing is sent (no target lookup).

    Returns ``{"contact", "chat_id", "topic_id", "text", "sent", ...}``; a real send also
    includes ``message_id`` and ``date``.

    Raises:
        NotSetUpError / NotConfiguredError / NotAuthorizedError: store/auth problems.
        ContactNotFoundError: if ``contact_key`` is not in the address book.
        ValueError: if ``text`` is empty.
    """
    if not cfg.storage_group_id:
        raise NotSetUpError("no storage group configured — run `tg-notes setup` first")
    if not text.strip():
        raise ValueError("refusing to send an empty message")

    client = connect_authorized(cfg)
    try:
        store = _resolve_store(client, cfg)
        contacts_topic = _list_topics(client, store).get(CONTACTS_TOPIC)
        contact = None
        if contacts_topic is not None:
            _, contact = _find_contact(client, store, contacts_topic, contact_key)
        if contact is None:
            raise ContactNotFoundError(
                f"no contact '{contact_key}' — add it with `tg-notes contacts set`"
            )

        body = _compose_outgoing(text, contact.mention)
        result = {
            "contact": contact_key,
            "chat_id": contact.chat_id,
            "topic_id": contact.topic_id,
            "text": body,
        }
        if dry_run:
            result["sent"] = False
            return result

        target = client.get_entity(_target_from_chat_id(contact.chat_id))
        message = client.send_message(target, body, reply_to=contact.topic_id)
        result.update(
            sent=True, message_id=message.id, date=_message_date_iso(message)
        )
        return result
    finally:
        client.disconnect()


def _compose_outgoing(text: str, mention: str | None) -> str:
    """Trim the body and prepend the contact's mention on its own line, if set."""
    body = text.strip()
    return f"{mention}\n\n{body}" if mention else body


def _target_from_chat_id(chat_id: str):
    """Coerce a stored ``chat_id`` to what ``get_entity`` expects (int id, or @user / me)."""
    text = str(chat_id).strip()
    try:
        return int(text)
    except ValueError:
        return text


def _find_contact(client, entity, contacts_topic, key):
    """Return ``(message, Contact)`` for ``key`` in the contacts topic, or ``(None, None)``."""
    for message in client.iter_messages(entity, reply_to=contacts_topic):
        contact = contacts_mod.parse(message.text or "")
        if contact is not None and contact.key == key:
            return message, contact
    return None, None


def _merge_contact(key, existing, *, chat_id, name, topic_id, mention, style):
    """Overlay the provided fields onto ``existing`` (or a blank record) for ``key``."""
    base = existing or contacts_mod.Contact(key=key)
    merged = contacts_mod.Contact(
        key=key,
        name=name if name is not None else base.name,
        chat_id=chat_id if chat_id is not None else base.chat_id,
        topic_id=topic_id if topic_id is not None else base.topic_id,
        mention=mention if mention is not None else base.mention,
        style=style if style is not None else base.style,
    )
    if not merged.chat_id:
        raise ValueError("a new contact needs --chat-id (where to send)")
    return merged


def _resolve_store(client: TelegramClient, cfg: Config) -> object:
    """Resolve the configured storage group, or raise :class:`NotSetUpError`."""
    try:
        return client.get_entity(cfg.storage_group_id)
    except (ValueError, TypeError) as exc:
        raise NotSetUpError(
            "configured storage group not found — run `tg-notes setup`"
        ) from exc


def _compose_note(text: str, hashtags: list[str] | None = None) -> str:
    """Trim the note body and append normalized hashtags on a trailing blank line."""
    body = text.strip()
    tags = [_normalize_hashtag(h) for h in (hashtags or []) if h.strip()]
    if not tags:
        return body
    tag_line = " ".join(tags)
    return f"{body}\n\n{tag_line}" if body else tag_line


def _normalize_hashtag(raw: str) -> str:
    """Return ``raw`` as a single ``#tag`` token (strip, drop leading ``#``, re-prefix)."""
    return "#" + raw.strip().lstrip("#")


def _message_date_iso(message: object) -> str | None:
    """ISO-8601 timestamp of a sent message, or ``None`` if it carries no date."""
    date = getattr(message, "date", None)
    return date.isoformat() if date is not None else None


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
