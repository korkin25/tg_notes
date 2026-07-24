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

#: Default service name under which secrets are stored in the keyring.
KEYRING_SERVICE = "tg-notes"
_KEY_API_HASH = "api_hash"
_KEY_SESSION = "session"


def _keyring_service() -> str:
    """The keyring service namespace — overridable via TG_NOTES_KEYRING_SERVICE (for sandboxes)."""
    return os.environ.get("TG_NOTES_KEYRING_SERVICE", KEYRING_SERVICE)


# --- vault access layer (Secret Service via secretstorage, with unlock-and-wait) --
#
# The plain ``keyring`` API reads a freshly-created / locked item without unlocking it,
# so a per-access-confirmation vault (KeePassXC) raises ``LockedException`` immediately
# instead of prompting. Accessing the Secret Service through ``secretstorage`` lets us
# call ``unlock()`` explicitly, which BLOCKS until the user answers the vault prompt —
# the behaviour every other app has. Entries stay compatible with ones written by the
# ``keyring`` library: both are looked up by the ``{service, username}`` attributes.


def _unlock_wait(obj, attempts: int = 3) -> bool:
    """Unlock a locked collection/item, WAITING for the user's vault prompt (like every
    other app). Re-requests up to ``attempts`` times if the prompt is dismissed. Returns
    True when unlocked."""
    for _ in range(attempts):
        if not obj.is_locked():
            return True
        obj.unlock()  # blocks until the user answers the vault prompt
    return not obj.is_locked()


_SS_CONN = None  # cached Secret Service D-Bus connection (one prompt per process)


def _ensure_dbus_env() -> None:
    """Best-effort: point ``DBUS_SESSION_BUS_ADDRESS`` at the user's session bus when unset.

    When the process is spawned with a sanitized environment (an MCP host, a cron job)
    ``DBUS_SESSION_BUS_ADDRESS`` may be missing, so ``secretstorage.dbus_init()`` fails with
    "Environment variable DBUS_SESSION_BUS_ADDRESS is unset" and the keyring backend can't
    reach the Secret Service. If the variable is unset and the standard per-user bus socket
    exists, we set it. Never raises — if the socket isn't there we leave the env as-is and let
    the normal error surface.
    """
    if os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        return
    getuid = getattr(os, "getuid", None)  # POSIX-only; this path is Linux/secretstorage-only
    if getuid is None:
        return
    sock = f"/run/user/{getuid()}/bus"
    if os.path.exists(sock):
        os.environ["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={sock}"


def _ss_collection():
    """Return the default Secret Service collection, unlocked (waiting for the prompt).

    The D-Bus connection is opened once and cached for the life of the process. KeePassXC
    binds each per-access-confirmation grant to the requesting D-Bus connection, so reusing
    one connection means a single command triggers at most ONE confirmation prompt instead
    of one per vault read (``api_hash`` + session + ``has_session`` …).
    """
    global _SS_CONN
    import secretstorage

    _ensure_dbus_env()  # self-heal a sanitized env (MCP host / cron) before dbus_init
    if _SS_CONN is None:
        _SS_CONN = secretstorage.dbus_init()
    collection = secretstorage.get_default_collection(_SS_CONN)
    _unlock_wait(collection)
    return collection


def _ss_read(key: str) -> str | None:
    for item in _ss_collection().search_items(
        {"service": _keyring_service(), "username": key}
    ):
        _unlock_wait(item)
        return item.get_secret().decode()
    return None


def _ss_write(key: str, value: str) -> None:
    collection = _ss_collection()
    for item in collection.search_items({"service": _keyring_service(), "username": key}):
        _unlock_wait(item)
        item.delete()  # replace any prior entry (incl. ones written by the keyring lib)
    collection.create_item(
        f"tg-notes {key}",
        {"application": "tg-notes", "service": _keyring_service(), "username": key},
        value.encode(),
    )


def _ss_delete(key: str) -> None:
    for item in _ss_collection().search_items(
        {"service": _keyring_service(), "username": key}
    ):
        _unlock_wait(item)
        item.delete()


def _vault_read(key: str) -> str | None:
    """Read a secret, waiting for the vault prompt (Secret Service via secretstorage); falls
    back to the plain ``keyring`` API where secretstorage is unavailable (non-Linux)."""
    try:
        import secretstorage  # noqa: F401
    except ImportError:
        import keyring

        return keyring.get_password(_keyring_service(), key)
    return _ss_read(key)


def _vault_write(key: str, value: str) -> None:
    """Write a secret, waiting for the vault prompt; keyring fallback where unavailable."""
    try:
        import secretstorage  # noqa: F401
    except ImportError:
        import keyring

        keyring.set_password(_keyring_service(), key, value)
        return
    _ss_write(key, value)


def _vault_delete(key: str) -> None:
    """Delete a secret (idempotent), waiting for the vault prompt; keyring fallback."""
    try:
        import secretstorage  # noqa: F401
    except ImportError:
        import keyring

        keyring.delete_password(_keyring_service(), key)
        return
    _ss_delete(key)


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

    def api_hash(self) -> str | None:
        # config value wins during migration; otherwise from the vault
        return self.cfg.api_hash or _vault_read(_KEY_API_HASH)

    def is_configured(self) -> bool:
        return bool(self.cfg.api_id and self.api_hash())

    def has_session(self) -> bool:
        return bool(_vault_read(_KEY_SESSION))

    def session_arg(self):
        from telethon.sessions import StringSession

        saved = _vault_read(_KEY_SESSION)
        return StringSession(saved) if saved else StringSession()

    @contextmanager
    def login_guard(self):
        yield  # nothing on disk to guard

    def persist_login(self, client) -> None:
        from telethon.sessions import StringSession

        _vault_write(_KEY_SESSION, StringSession.save(client.session))


def get_backend(cfg: Config):
    """Return the secrets backend selected by ``cfg.secrets_backend`` (file by default)."""
    if cfg.secrets_backend == "keyring":
        return KeyringBackend(cfg)
    return FileBackend(cfg)


def keyring_probe() -> tuple[bool, str | None]:
    """Round-trip a probe secret through the keyring; classify any failure.

    Returns ``(ok, kind)``. ``kind`` is a short classifier so callers can recommend a fix:
    ``"not-installed"`` (the ``keyring`` extra is missing), ``"no-collection"`` (no default
    collection / no exposed group — the vault tried to create one and the prompt was
    dismissed), ``"locked"`` (per-access confirmation is blocking reads), or
    ``"error:<Type>"`` for anything else. ``kind`` is ``None`` on success.
    """
    try:
        import secretstorage  # noqa: F401 — preferred path (unlock-and-wait)
    except ImportError:
        try:
            import keyring  # noqa: F401 — fallback path (non-Linux)
        except ImportError:
            return False, "not-installed"
    try:
        _vault_write("_probe", "1")
        ok = _vault_read("_probe") == "1"
        _vault_delete("_probe")
        return (True, None) if ok else (False, "error:readback-mismatch")
    except Exception as exc:  # noqa: BLE001 — classify any backend failure
        msg = str(exc).lower()
        if "prompt dismissed" in msg or "create the collection" in msg:
            return False, "no-collection"
        if "locked" in msg or "dismiss" in msg:
            return False, "locked"
        return False, f"error:{type(exc).__name__}"


def keyring_available() -> bool:
    """True if ``keyring`` imports and the Secret Service round-trips a probe secret."""
    return keyring_probe()[0]


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
    it. Verifies the vault round-trip before removing the on-disk session.
    """
    if not cfg.api_hash:
        raise ValueError("no api_hash in config to migrate")
    session_str = _export_string_session(cfg)
    if not session_str:  # empty = no authorized session; never overwrite the vault with it
        raise RuntimeError("no authorized session to migrate — run `tg-notes login` first")

    _vault_write(_KEY_API_HASH, cfg.api_hash)
    _vault_write(_KEY_SESSION, session_str)
    if _vault_read(_KEY_SESSION) != session_str:
        raise RuntimeError("keyring did not store the session — aborting migration")

    dotfile = _dotsession(cfg.session)
    if os.path.exists(dotfile):
        os.remove(dotfile)  # crown-jewel session off disk, now only in the vault
    cfg.secrets_backend = "keyring"
    cfg.api_hash = None


def migrate_to_file(cfg: Config) -> None:
    """Move ``api_hash`` + the session from the keyring back to config + a session file."""
    api_hash = _vault_read(_KEY_API_HASH)
    session_str = _vault_read(_KEY_SESSION)
    if not session_str:
        raise RuntimeError("no session in the keyring to migrate")

    _write_file_session(cfg, session_str)
    _vault_delete(_KEY_SESSION)
    with contextlib.suppress(Exception):  # absent api_hash key is fine
        _vault_delete(_KEY_API_HASH)
    cfg.secrets_backend = "file"
    cfg.api_hash = api_hash
