"""Telegram client layer for tg-notes.

Thin, deterministic wrapper around Telethon (MTProto). Importing ``telethon.sync`` first
turns the async client methods into blocking calls, so the rest of this module — and the
CLI on top of it — stays synchronous and easy to reason about. All Telegram I/O in the
project funnels through here; no AI logic lives in this layer.
"""
from __future__ import annotations

import os

import telethon.sync  # noqa: F401  # enables synchronous TelegramClient methods
from telethon import TelegramClient

from .config import Config


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
