"""Contact records — the tg-notes address book stored in the ``contacts`` topic.

One Telegram message per contact, formatted as a parseable block (see
docs/architecture.md). This module is **pure**: it only (de)serializes the block; all
Telegram I/O lives in :mod:`tg_notes.telegram`.

Block layout::

    #contact <key>
    name: <human name, never sent>
    chat_id: <-100… | @username | me>
    topic_id: <forum topic id | empty>
    mention: <@username | empty>
    style: <prompt: how to compile notes for this recipient>
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_HEADER = re.compile(r"^#contact\s+(\S+)\s*$")
_TEXT_FIELDS = ("name", "chat_id", "mention", "style")


@dataclass
class Contact:
    """One address-book entry. ``chat_id`` stays a string (``-100…`` / ``@user`` / ``me``)."""

    key: str
    name: str | None = None
    chat_id: str | None = None
    topic_id: int | None = None
    mention: str | None = None
    style: str | None = None

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "chat_id": self.chat_id,
            "topic_id": self.topic_id,
            "mention": self.mention,
            "style": self.style,
        }


def _clean(value: object) -> str:
    """Render a field value on a single line (newlines collapsed) so the block parses."""
    if value is None:
        return ""
    return " ".join(str(value).split())


def serialize(contact: Contact) -> str:
    """Render a :class:`Contact` as its message block."""
    return "\n".join(
        [
            f"#contact {contact.key}",
            f"name: {_clean(contact.name)}",
            f"chat_id: {_clean(contact.chat_id)}",
            f"topic_id: {_clean(contact.topic_id)}",
            f"mention: {_clean(contact.mention)}",
            f"style: {_clean(contact.style)}",
        ]
    )


def parse(text: str) -> Contact | None:
    """Parse a message body into a :class:`Contact`, or ``None`` if it is not one."""
    lines = (text or "").splitlines()
    if not lines:
        return None
    header = _HEADER.match(lines[0].strip())
    if header is None:
        return None

    values: dict[str, str] = {}
    for line in lines[1:]:
        field, sep, value = line.partition(":")
        if not sep:
            continue
        field = field.strip()
        if field in _TEXT_FIELDS or field == "topic_id":
            values[field] = value.strip()

    topic_id: int | None = None
    raw_topic = values.get("topic_id")
    if raw_topic:
        try:
            topic_id = int(raw_topic)
        except ValueError:
            topic_id = None

    return Contact(
        key=header.group(1),
        name=values.get("name") or None,
        chat_id=values.get("chat_id") or None,
        topic_id=topic_id,
        mention=values.get("mention") or None,
        style=values.get("style") or None,
    )
