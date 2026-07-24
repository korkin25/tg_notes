"""Pluggable secrets backend for tg-notes (TGN-18).

Two backends decide where the two real secrets — the ``api_hash`` and the Telethon session
— live:

- **file** (default): ``api_hash`` in ``config.toml`` (mode 600) and the session in a local
  ``*.session`` file. Zero dependencies; works unattended.
- **keyring**: ``api_hash`` and the session (as a Telethon ``StringSession``) in the OS
  Secret Service via the ``keyring`` library — gnome-keyring, KWallet, or KeePassXC
  (whichever owns ``org.freedesktop.secrets``). Opt-in; needs ``tg-notes[keyring]``.

``api_id`` and ``storage_group_id`` are not secret and always stay in ``config.toml``. The
active backend is chosen by ``config.secrets_backend`` ("file" when unset). The keyring
path never requires an interactive unlock on a session that is already unlocked at login,
so scheduled/unattended runs keep working.
"""
from __future__ import annotations

import contextlib
import os
from contextlib import contextmanager

from .config import Config

#: Service name under which secrets are stored in the keyring.
KEYRING_SERVICE = "tg-notes"
_KEY_API_HASH = "api_hash"
_KEY_SESSION = "session"


class FileBackend:
    """Secrets in ``config.toml`` (api_hash) + a local ``*.session`` file (the default)."""

    name = "file"

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    def api_hash(self) -> str | None:
        return self.cfg.api_hash

    def is_configured(self) -> bool:
        return bool(self.cfg.api_id and self.cfg.api_hash)

    def has_session(self) -> bool:
        path = self.cfg.session
        return os.path.exists(path) or os.path.exists(path + ".session")

    def session_arg(self):
        return self.cfg.session  # a path → Telethon SqliteSession

    @contextmanager
    def login_guard(self):
        session_file = _dotsession(self.cfg.session)
        parent = os.path.dirname(session_file)
        if parent:
            os.makedirs(parent, exist_ok=True)
            os.chmod(parent, 0o700)
        old_umask = os.umask(0o077)  # session file created private (0600), no race window
        try:
            yield
        finally:
            os.umask(old_umask)

    def persist_login(self, client) -> None:
        session_file = _dotsession(self.cfg.session)
        if os.path.exists(session_file):
            os.chmod(session_file, 0o600)


class KeyringBackend:
    """Secrets in the OS Secret Service via ``keyring`` (session as a ``StringSession``)."""

    name = "keyring"

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    @staticmethod
    def _keyring():
        import keyring  # optional dependency — imported only on the keyring path

        return keyring

    def api_hash(self) -> str | None:
        # config value wins during migration; otherwise from the vault
        return self.cfg.api_hash or self._keyring().get_password(KEYRING_SERVICE, _KEY_API_HASH)

    def is_configured(self) -> bool:
        return bool(self.cfg.api_id and self.api_hash())

    def has_session(self) -> bool:
        return bool(self._keyring().get_password(KEYRING_SERVICE, _KEY_SESSION))

    def session_arg(self):
        from telethon.sessions import StringSession

        saved = self._keyring().get_password(KEYRING_SERVICE, _KEY_SESSION)
        return StringSession(saved) if saved else StringSession()

    @contextmanager
    def login_guard(self):
        yield  # nothing on disk to guard

    def persist_login(self, client) -> None:
        from telethon.sessions import StringSession

        self._keyring().set_password(
            KEYRING_SERVICE, _KEY_SESSION, StringSession.save(client.session)
        )


def get_backend(cfg: Config):
    """Return the secrets backend selected by ``cfg.secrets_backend`` (file by default)."""
    if cfg.secrets_backend == "keyring":
        return KeyringBackend(cfg)
    return FileBackend(cfg)


def keyring_available() -> bool:
    """True if ``keyring`` imports and the Secret Service round-trips a probe secret."""
    try:
        import keyring
    except ImportError:
        return False
    try:
        keyring.set_password(KEYRING_SERVICE, "_probe", "1")
        ok = keyring.get_password(KEYRING_SERVICE, "_probe") == "1"
        keyring.delete_password(KEYRING_SERVICE, "_probe")
        return ok
    except Exception:  # noqa: BLE001 — any backend failure means "not usable"
        return False


# --- migration between backends --------------------------------------------------


def _dotsession(path: str) -> str:
    return path if path.endswith(".session") else path + ".session"


def _export_string_session(cfg: Config) -> str:
    """Serialize the file-based session to a portable ``StringSession`` string."""
    from telethon.sessions import SQLiteSession, StringSession

    stem = cfg.session.removesuffix(".session")
    return StringSession.save(SQLiteSession(stem))


def _write_file_session(cfg: Config, session_str: str) -> None:
    """Materialize a ``StringSession`` string back into a local ``*.session`` file."""
    from telethon.sessions import SQLiteSession, StringSession

    src = StringSession(session_str)
    stem = cfg.session.removesuffix(".session")
    dst = SQLiteSession(stem)
    if src.auth_key is not None:
        dst.set_dc(src.dc_id, src.server_address, src.port)
        dst.auth_key = src.auth_key
    dst.save()
    dst.close()
    if os.path.exists(_dotsession(cfg.session)):
        os.chmod(_dotsession(cfg.session), 0o600)


def migrate_to_keyring(cfg: Config) -> None:
    """Move ``api_hash`` + the session into the keyring; leaves ``cfg`` pointing there.

    Mutates ``cfg`` (``secrets_backend='keyring'``, ``api_hash=None``) — the caller saves
    it. Verifies the keyring round-trip before removing the on-disk session.
    """
    import keyring

    if not cfg.api_hash:
        raise ValueError("no api_hash in config to migrate")
    session_str = _export_string_session(cfg)

    keyring.set_password(KEYRING_SERVICE, _KEY_API_HASH, cfg.api_hash)
    keyring.set_password(KEYRING_SERVICE, _KEY_SESSION, session_str)
    if keyring.get_password(KEYRING_SERVICE, _KEY_SESSION) != session_str:
        raise RuntimeError("keyring did not store the session — aborting migration")

    dotfile = _dotsession(cfg.session)
    if os.path.exists(dotfile):
        os.remove(dotfile)  # crown-jewel session off disk, now only in the vault
    cfg.secrets_backend = "keyring"
    cfg.api_hash = None


def migrate_to_file(cfg: Config) -> None:
    """Move ``api_hash`` + the session from the keyring back to config + a session file."""
    import keyring

    api_hash = keyring.get_password(KEYRING_SERVICE, _KEY_API_HASH)
    session_str = keyring.get_password(KEYRING_SERVICE, _KEY_SESSION)
    if not session_str:
        raise RuntimeError("no session in the keyring to migrate")

    from keyring.errors import PasswordDeleteError

    _write_file_session(cfg, session_str)
    keyring.delete_password(KEYRING_SERVICE, _KEY_SESSION)
    with contextlib.suppress(PasswordDeleteError):  # absent api_hash key is fine
        keyring.delete_password(KEYRING_SERVICE, _KEY_API_HASH)
    cfg.secrets_backend = "file"
    cfg.api_hash = api_hash
