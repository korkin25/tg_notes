"""Tests for the Telegram client layer (TGN-2).

Telethon is fully mocked here — ``tg_notes.telegram.TelegramClient`` is patched — so the
suite never touches the network and needs no session.
"""
from __future__ import annotations

import pytest

from tg_notes import telegram
from tg_notes.config import Config


def configured() -> Config:
    return Config(api_id=42, api_hash="cafe", session_path="/tmp/x.session")


def test_build_client_raises_when_not_configured() -> None:
    with pytest.raises(telegram.NotConfiguredError):
        telegram.build_client(Config())


def test_build_client_constructs_telegram_client_from_cfg(mocker) -> None:
    fake_cls = mocker.patch("tg_notes.telegram.TelegramClient")
    cfg = configured()

    client = telegram.build_client(cfg)

    fake_cls.assert_called_once_with(cfg.session, cfg.api_id, cfg.api_hash)
    assert client is fake_cls.return_value


def test_connect_authorized_raises_when_not_authorized(mocker) -> None:
    fake_cls = mocker.patch("tg_notes.telegram.TelegramClient")
    instance = fake_cls.return_value
    instance.is_user_authorized.return_value = False

    with pytest.raises(telegram.NotAuthorizedError):
        telegram.connect_authorized(configured())

    instance.connect.assert_called_once_with()
    instance.disconnect.assert_called_once_with()  # no leaked connection on failure


def test_connect_authorized_returns_client_when_authorized(mocker) -> None:
    fake_cls = mocker.patch("tg_notes.telegram.TelegramClient")
    instance = fake_cls.return_value
    instance.is_user_authorized.return_value = True

    client = telegram.connect_authorized(configured())

    assert client is instance
    instance.connect.assert_called_once_with()


def test_whoami_returns_identity_and_disconnects(mocker) -> None:
    fake_cls = mocker.patch("tg_notes.telegram.TelegramClient")
    instance = fake_cls.return_value
    instance.is_user_authorized.return_value = True
    me = mocker.Mock()
    me.id = 777
    me.username = "korkin25"
    me.first_name = "K"
    instance.get_me.return_value = me

    result = telegram.whoami(configured())

    assert result == {"id": 777, "username": "korkin25", "first_name": "K"}
    instance.disconnect.assert_called_once_with()


def test_whoami_disconnects_even_when_get_me_fails(mocker) -> None:
    fake_cls = mocker.patch("tg_notes.telegram.TelegramClient")
    instance = fake_cls.return_value
    instance.is_user_authorized.return_value = True
    instance.get_me.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError):
        telegram.whoami(configured())

    instance.disconnect.assert_called_once_with()
