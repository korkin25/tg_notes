"""Tests for the pluggable secrets backend (TGN-18). The vault layer is fully mocked."""
from __future__ import annotations

import builtins

import pytest
from telethon.sessions import StringSession

from tg_notes import secrets, telegram
from tg_notes.config import Config


@pytest.fixture(autouse=True)
def _reset_ss_conn():
    """Reset the cached Secret Service connection around every test so the module-level
    ``_SS_CONN`` cache never leaks between tests (each patches ``secretstorage`` fresh)."""
    secrets._SS_CONN = None
    yield
    secrets._SS_CONN = None


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


# --- _unlock_wait: wait for the vault prompt, retry on dismissal ------------------


def test_unlock_wait_unlocks_after_retries(mocker) -> None:
    obj = mocker.Mock()
    obj.is_locked.side_effect = [True, True, False]  # locked twice, then unlocked
    assert secrets._unlock_wait(obj) is True
    assert obj.unlock.call_count == 2  # one unlock per locked check before success


def test_unlock_wait_returns_false_when_dismissed(mocker) -> None:
    obj = mocker.Mock()
    obj.is_locked.return_value = True  # user keeps dismissing the prompt
    assert secrets._unlock_wait(obj) is False
    assert obj.unlock.call_count == 3  # tried the default number of attempts


def test_unlock_wait_no_op_when_already_unlocked(mocker) -> None:
    obj = mocker.Mock()
    obj.is_locked.return_value = False
    assert secrets._unlock_wait(obj) is True
    obj.unlock.assert_not_called()


# --- secretstorage layer (_ss_*) — secretstorage entrypoints mocked ---------------


def _fake_ss_collection(mocker, items):
    """Patch secretstorage so ``_ss_collection`` returns a fake unlocked collection."""
    collection = mocker.Mock()
    collection.is_locked.return_value = False
    collection.search_items.return_value = list(items)
    mocker.patch("secretstorage.dbus_init", return_value=mocker.Mock())
    mocker.patch("secretstorage.get_default_collection", return_value=collection)
    return collection


def test_ss_read_returns_decoded_secret(mocker) -> None:
    item = mocker.Mock()
    item.is_locked.return_value = False
    item.get_secret.return_value = b"topsecret"
    _fake_ss_collection(mocker, [item])
    assert secrets._ss_read("session") == "topsecret"


def test_ss_read_none_when_absent(mocker) -> None:
    _fake_ss_collection(mocker, [])
    assert secrets._ss_read("session") is None


def test_ss_write_replaces_existing_and_tags_attributes(mocker) -> None:
    old = mocker.Mock()
    old.is_locked.return_value = False
    collection = _fake_ss_collection(mocker, [old])

    secrets._ss_write("session", "v")

    old.delete.assert_called_once()  # prior entry (incl. keyring-written) replaced
    _label, attrs, secret = collection.create_item.call_args.args
    assert attrs["service"] == secrets._keyring_service()  # compat lookup key
    assert attrs["username"] == "session"
    assert secret == b"v"


def test_ss_delete_removes_matches(mocker) -> None:
    item = mocker.Mock()
    item.is_locked.return_value = False
    _fake_ss_collection(mocker, [item])
    secrets._ss_delete("session")
    item.delete.assert_called_once()


def test_ss_collection_reuses_one_connection(mocker) -> None:
    # One D-Bus connection per process → at most one KeePassXC prompt per command.
    conn = mocker.Mock(name="ss_conn")
    collection = mocker.Mock()
    collection.is_locked.return_value = False
    init = mocker.patch("secretstorage.dbus_init", return_value=conn)
    get_coll = mocker.patch("secretstorage.get_default_collection", return_value=collection)
    secrets._SS_CONN = None  # start from a cold cache

    first = secrets._ss_collection()
    second = secrets._ss_collection()

    assert first is collection and second is collection
    init.assert_called_once()  # connection opened exactly once, then reused
    assert get_coll.call_count == 2
    assert [c.args for c in get_coll.call_args_list] == [(conn,), (conn,)]  # same conn


# --- _vault_* dispatch: secretstorage when available, keyring fallback -------------


def test_vault_read_uses_secretstorage_when_available(mocker) -> None:
    ss = mocker.patch("tg_notes.secrets._ss_read", return_value="x")
    assert secrets._vault_read("k") == "x"
    ss.assert_called_once_with("k")


def test_vault_write_uses_secretstorage_when_available(mocker) -> None:
    ss = mocker.patch("tg_notes.secrets._ss_write")
    secrets._vault_write("k", "v")
    ss.assert_called_once_with("k", "v")


def test_vault_delete_uses_secretstorage_when_available(mocker) -> None:
    ss = mocker.patch("tg_notes.secrets._ss_delete")
    secrets._vault_delete("k")
    ss.assert_called_once_with("k")


def _no_secretstorage(monkeypatch):
    """Make ``import secretstorage`` raise, forcing the plain-keyring fallback path."""
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "secretstorage":
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)


def test_vault_read_falls_back_to_keyring(monkeypatch, mocker) -> None:
    _no_secretstorage(monkeypatch)
    kr = mocker.patch("keyring.get_password", return_value="fromkeyring")
    assert secrets._vault_read("k") == "fromkeyring"
    kr.assert_called_once_with(secrets._keyring_service(), "k")


def test_vault_write_falls_back_to_keyring(monkeypatch, mocker) -> None:
    _no_secretstorage(monkeypatch)
    kr = mocker.patch("keyring.set_password")
    secrets._vault_write("k", "v")
    kr.assert_called_once_with(secrets._keyring_service(), "k", "v")


def test_vault_delete_falls_back_to_keyring(monkeypatch, mocker) -> None:
    _no_secretstorage(monkeypatch)
    kr = mocker.patch("keyring.delete_password")
    secrets._vault_delete("k")
    kr.assert_called_once_with(secrets._keyring_service(), "k")


# --- keyring backend (vault layer mocked) ----------------------------------------


def _fake_vault_read(mocker, stored: dict):
    return mocker.patch(
        "tg_notes.secrets._vault_read", side_effect=lambda key: stored.get(key)
    )


def test_keyring_backend_reads_api_hash_and_session_from_vault(mocker) -> None:
    _fake_vault_read(mocker, {"api_hash": "vaulthash", "session": None})
    backend = secrets.get_backend(Config(api_id=1, secrets_backend="keyring"))

    assert backend.api_hash() == "vaulthash"
    assert backend.is_configured() is True
    assert backend.has_session() is False
    assert isinstance(backend.session_arg(), StringSession)  # empty session


def _valid_session_str() -> str:
    """A non-empty, parseable Telethon ``StringSession`` string (fake auth key)."""
    from telethon.crypto import AuthKey

    s = StringSession()
    s.set_dc(1, "149.154.167.51", 443)
    s.auth_key = AuthKey(bytes(256))
    return StringSession.save(s)


def test_keyring_backend_reads_existing_session(mocker) -> None:
    _fake_vault_read(mocker, {"api_hash": "vaulthash", "session": _valid_session_str()})
    backend = secrets.get_backend(Config(api_id=1, secrets_backend="keyring"))
    assert backend.has_session() is True
    assert isinstance(backend.session_arg(), StringSession)


def test_keyring_backend_persist_login_stores_stringsession(mocker) -> None:
    setv = mocker.patch("tg_notes.secrets._vault_write")
    mocker.patch("telethon.sessions.StringSession.save", return_value="SESSIONSTR")
    backend = secrets.get_backend(Config(api_id=1, secrets_backend="keyring"))

    backend.persist_login(mocker.Mock())

    setv.assert_called_once_with(secrets._KEY_SESSION, "SESSIONSTR")


# --- keyring service namespace (sandbox override) --------------------------------


def test_keyring_service_default(monkeypatch) -> None:
    monkeypatch.delenv("TG_NOTES_KEYRING_SERVICE", raising=False)
    assert secrets._keyring_service() == "tg-notes"


def test_keyring_service_env_override(monkeypatch) -> None:
    monkeypatch.setenv("TG_NOTES_KEYRING_SERVICE", "tg-notes-sandbox")
    assert secrets._keyring_service() == "tg-notes-sandbox"


# --- keyring_probe / keyring_available (vault layer mocked) -----------------------


def test_keyring_probe_roundtrips_via_vault(mocker) -> None:
    mocker.patch("tg_notes.secrets._vault_write")
    mocker.patch("tg_notes.secrets._vault_read", return_value="1")
    mocker.patch("tg_notes.secrets._vault_delete")
    assert secrets.keyring_probe() == (True, None)


def test_keyring_available_true_on_roundtrip(mocker) -> None:
    mocker.patch("tg_notes.secrets._vault_write")
    mocker.patch("tg_notes.secrets._vault_read", return_value="1")
    mocker.patch("tg_notes.secrets._vault_delete")
    assert secrets.keyring_available() is True


def test_keyring_available_false_on_error(mocker) -> None:
    mocker.patch("tg_notes.secrets._vault_write", side_effect=RuntimeError("no backend"))
    assert secrets.keyring_available() is False


def test_keyring_probe_readback_mismatch(mocker) -> None:
    mocker.patch("tg_notes.secrets._vault_write")
    mocker.patch("tg_notes.secrets._vault_read", return_value="WRONG")
    mocker.patch("tg_notes.secrets._vault_delete")
    assert secrets.keyring_probe() == (False, "error:readback-mismatch")


def test_keyring_probe_classifies_no_collection(mocker) -> None:
    mocker.patch(
        "tg_notes.secrets._vault_write",
        side_effect=Exception("Failed to create the collection: Prompt dismissed."),
    )
    assert secrets.keyring_probe() == (False, "no-collection")


def test_keyring_probe_classifies_locked(mocker) -> None:
    mocker.patch("tg_notes.secrets._vault_write")
    mocker.patch(
        "tg_notes.secrets._vault_read", side_effect=Exception("Item is locked!")
    )
    assert secrets.keyring_probe() == (False, "locked")


def test_keyring_probe_other_error(mocker) -> None:
    mocker.patch("tg_notes.secrets._vault_write", side_effect=RuntimeError("boom"))
    assert secrets.keyring_probe() == (False, "error:RuntimeError")


def test_keyring_probe_not_installed(monkeypatch) -> None:
    # neither secretstorage nor keyring importable → not-installed, no vault touched
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name in ("secretstorage", "keyring"):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert secrets.keyring_probe() == (False, "not-installed")


# --- migration --------------------------------------------------------------------


def test_migrate_to_keyring_stores_and_mutates_cfg(mocker, tmp_path) -> None:
    mocker.patch("tg_notes.secrets._export_string_session", return_value="SESS")
    setv = mocker.patch("tg_notes.secrets._vault_write")
    mocker.patch("tg_notes.secrets._vault_read", return_value="SESS")  # verify readback
    session_file = tmp_path / "s.session"
    session_file.write_text("db", encoding="utf-8")
    cfg = Config(api_id=1, api_hash="h", session_path=str(session_file))

    secrets.migrate_to_keyring(cfg)

    assert cfg.secrets_backend == "keyring"
    assert cfg.api_hash is None  # removed from config
    assert not session_file.exists()  # session taken off disk
    setv.assert_any_call(secrets._KEY_API_HASH, "h")
    setv.assert_any_call(secrets._KEY_SESSION, "SESS")


def test_migrate_to_keyring_requires_api_hash() -> None:
    with pytest.raises(ValueError):
        secrets.migrate_to_keyring(Config(api_id=1))


def test_migrate_to_keyring_aborts_if_vault_readback_fails(mocker, tmp_path) -> None:
    mocker.patch("tg_notes.secrets._export_string_session", return_value="SESS")
    mocker.patch("tg_notes.secrets._vault_write")
    mocker.patch("tg_notes.secrets._vault_read", return_value=None)  # readback mismatch
    session_file = tmp_path / "s.session"
    session_file.write_text("db", encoding="utf-8")
    cfg = Config(api_id=1, api_hash="h", session_path=str(session_file))

    with pytest.raises(RuntimeError):
        secrets.migrate_to_keyring(cfg)

    assert session_file.exists()  # not removed on failure


def test_migrate_to_keyring_refuses_empty_session(mocker, tmp_path) -> None:
    # empty session export = not logged in; must not overwrite the vault with it
    mocker.patch("tg_notes.secrets._export_string_session", return_value="")
    setv = mocker.patch("tg_notes.secrets._vault_write")
    cfg = Config(api_id=1, api_hash="h", session_path=str(tmp_path / "s.session"))

    with pytest.raises(RuntimeError):
        secrets.migrate_to_keyring(cfg)

    setv.assert_not_called()  # nothing written to the vault


def test_migrate_to_file_restores_cfg(mocker, tmp_path) -> None:
    stored = {"api_hash": "h", "session": "SESS"}
    mocker.patch("tg_notes.secrets._vault_read", side_effect=lambda key: stored.get(key))
    write = mocker.patch("tg_notes.secrets._write_file_session")
    delv = mocker.patch("tg_notes.secrets._vault_delete")
    cfg = Config(api_id=1, secrets_backend="keyring", session_path=str(tmp_path / "s.session"))

    secrets.migrate_to_file(cfg)

    assert cfg.secrets_backend == "file"
    assert cfg.api_hash == "h"
    write.assert_called_once_with(cfg, "SESS")
    delv.assert_any_call(secrets._KEY_SESSION)


# --- telegram build_client honours the backend -----------------------------------


def test_build_client_uses_keyring_stringsession(mocker) -> None:
    fake_cls = mocker.patch("tg_notes.telegram.TelegramClient")
    _fake_vault_read(mocker, {"api_hash": "vaulthash", "session": None})

    telegram.build_client(Config(api_id=1, secrets_backend="keyring"))

    session_arg, api_id, api_hash = fake_cls.call_args.args
    assert isinstance(session_arg, StringSession)
    assert api_id == 1
    assert api_hash == "vaulthash"
