"""Tests for the pluggable secrets backend (TGN-18). The keyring is fully mocked."""
from __future__ import annotations

import pytest
from telethon.sessions import StringSession

from tg_notes import secrets, telegram
from tg_notes.config import Config

# --- backend selection + file backend --------------------------------------------


def test_get_backend_defaults_to_file() -> None:
    assert secrets.get_backend(Config()).name == "file"


def test_get_backend_keyring_when_selected() -> None:
    assert secrets.get_backend(Config(secrets_backend="keyring")).name == "keyring"


def test_file_backend_reads_from_config(tmp_path) -> None:
    cfg = Config(api_id=1, api_hash="h", session_path=str(tmp_path / "s.session"))
    backend = secrets.get_backend(cfg)
    assert backend.is_configured() is True
    assert backend.api_hash() == "h"
    assert backend.session_arg() == cfg.session
    assert backend.has_session() is False  # no file yet


def test_file_backend_not_configured_without_api_hash() -> None:
    assert secrets.get_backend(Config(api_id=1)).is_configured() is False


# --- keyring backend (mocked) ----------------------------------------------------


def _fake_keyring(mocker, stored: dict):
    fake = mocker.Mock()
    fake.get_password.side_effect = lambda service, key: stored.get(key)
    mocker.patch.object(secrets.KeyringBackend, "_keyring", return_value=fake)
    return fake


def test_keyring_backend_reads_api_hash_and_session_from_vault(mocker) -> None:
    _fake_keyring(mocker, {"api_hash": "vaulthash", "session": None})
    backend = secrets.get_backend(Config(api_id=1, secrets_backend="keyring"))

    assert backend.api_hash() == "vaulthash"
    assert backend.is_configured() is True
    assert backend.has_session() is False
    assert isinstance(backend.session_arg(), StringSession)  # empty session


def test_keyring_backend_persist_login_stores_stringsession(mocker) -> None:
    fake = _fake_keyring(mocker, {})
    mocker.patch("telethon.sessions.StringSession.save", return_value="SESSIONSTR")
    backend = secrets.get_backend(Config(api_id=1, secrets_backend="keyring"))

    backend.persist_login(mocker.Mock())

    fake.set_password.assert_called_once_with("tg-notes", "session", "SESSIONSTR")


# --- keyring_available ------------------------------------------------------------


def test_keyring_available_true_on_roundtrip(mocker) -> None:
    mocker.patch("keyring.set_password")
    mocker.patch("keyring.get_password", return_value="1")
    mocker.patch("keyring.delete_password")
    assert secrets.keyring_available() is True


def test_keyring_available_false_on_error(mocker) -> None:
    mocker.patch("keyring.set_password", side_effect=RuntimeError("no backend"))
    assert secrets.keyring_available() is False


# --- migration --------------------------------------------------------------------


def test_migrate_to_keyring_stores_and_mutates_cfg(mocker, tmp_path) -> None:
    mocker.patch("tg_notes.secrets._export_string_session", return_value="SESS")
    setp = mocker.patch("keyring.set_password")
    mocker.patch("keyring.get_password", return_value="SESS")  # verify readback
    session_file = tmp_path / "s.session"
    session_file.write_text("db", encoding="utf-8")
    cfg = Config(api_id=1, api_hash="h", session_path=str(session_file))

    secrets.migrate_to_keyring(cfg)

    assert cfg.secrets_backend == "keyring"
    assert cfg.api_hash is None  # removed from config
    assert not session_file.exists()  # session taken off disk
    setp.assert_any_call("tg-notes", "api_hash", "h")
    setp.assert_any_call("tg-notes", "session", "SESS")


def test_migrate_to_keyring_requires_api_hash() -> None:
    with pytest.raises(ValueError):
        secrets.migrate_to_keyring(Config(api_id=1))


def test_migrate_to_keyring_aborts_if_vault_readback_fails(mocker, tmp_path) -> None:
    mocker.patch("tg_notes.secrets._export_string_session", return_value="SESS")
    mocker.patch("keyring.set_password")
    mocker.patch("keyring.get_password", return_value=None)  # readback mismatch
    session_file = tmp_path / "s.session"
    session_file.write_text("db", encoding="utf-8")
    cfg = Config(api_id=1, api_hash="h", session_path=str(session_file))

    with pytest.raises(RuntimeError):
        secrets.migrate_to_keyring(cfg)

    assert session_file.exists()  # not removed on failure


def test_migrate_to_file_restores_cfg(mocker, tmp_path) -> None:
    stored = {"api_hash": "h", "session": "SESS"}
    mocker.patch("keyring.get_password", side_effect=lambda service, key: stored.get(key))
    write = mocker.patch("tg_notes.secrets._write_file_session")
    mocker.patch("keyring.delete_password")
    cfg = Config(api_id=1, secrets_backend="keyring", session_path=str(tmp_path / "s.session"))

    secrets.migrate_to_file(cfg)

    assert cfg.secrets_backend == "file"
    assert cfg.api_hash == "h"
    write.assert_called_once_with(cfg, "SESS")


# --- telegram build_client honours the backend -----------------------------------


def test_build_client_uses_keyring_stringsession(mocker) -> None:
    fake_cls = mocker.patch("tg_notes.telegram.TelegramClient")
    _fake_keyring(mocker, {"api_hash": "vaulthash", "session": None})

    telegram.build_client(Config(api_id=1, secrets_backend="keyring"))

    session_arg, api_id, api_hash = fake_cls.call_args.args
    assert isinstance(session_arg, StringSession)
    assert api_id == 1
    assert api_hash == "vaulthash"
