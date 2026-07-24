"""Gated live test for the secure-store (keyring) backend — dev machine only (TGN-25).

This is **group-(b)**: it needs a real Secret Service (gnome-keyring / KWallet / KeePassXC),
which CI does not have — as the maintainer put it, "secure store под CI нет". So it runs
**only** when explicitly opted in on a developer machine with an unlocked vault:

    TG_NOTES_LIVE=1 TG_NOTES_LIVE_KEYRING=1 \
        scripts/sandbox.py pytest -- tests/test_live_secure_store.py -v

It round-trips the crown-jewel secrets through the OS vault: migrate the seeded file backend
into the keyring, prove ``whoami`` works reading the ``StringSession`` **from the vault**, then
migrate back to files — restoring the sandbox to how it started even on failure. A throwaway
``TG_NOTES_KEYRING_SERVICE`` namespace keeps the real ``tg-notes`` vault entries untouched.
The migration *logic* is covered exhaustively (mocked) in ``test_secrets.py``; this proves the
real Secret Service round-trip.
"""
from __future__ import annotations

import os

import pytest

from tg_notes import config, secrets, telegram

pytestmark = pytest.mark.skipif(
    not (os.environ.get("TG_NOTES_LIVE") and os.environ.get("TG_NOTES_LIVE_KEYRING")),
    reason=(
        "secure-store live test — set TG_NOTES_LIVE=1 and TG_NOTES_LIVE_KEYRING=1 on a dev "
        "machine with an unlocked Secret Service (never runs in CI)"
    ),
)

REAL_STORE_ID = -1004432534270


def _live_cfg() -> config.Config:
    cfg = config.load()
    assert cfg.storage_group_id, "no storage group configured — run `tg-notes setup` first"
    assert cfg.storage_group_id != REAL_STORE_ID, "refusing to touch the real store"
    return cfg


def test_secure_store_migration_roundtrip(monkeypatch) -> None:
    _live_cfg()
    # Isolate the vault entries under a throwaway namespace, not the real `tg-notes` one.
    monkeypatch.setenv("TG_NOTES_KEYRING_SERVICE", f"tg-notes-citest-{os.getpid()}")
    if not secrets.keyring_available():
        pytest.skip("no usable/unlocked Secret Service on this machine")

    # Baseline: the seeded file backend is authorized.
    assert secrets.get_backend(config.load()).has_session()

    try:
        cfg = config.load()
        secrets.migrate_to_keyring(cfg)  # api_hash + session → vault; session file removed
        config.save(cfg)

        vault = secrets.get_backend(config.load())
        assert vault.name == "keyring", vault.name
        assert vault.has_session(), "session not readable from the vault"
        assert vault.api_hash(), "api_hash not readable from the vault"

        identity = telegram.whoami(config.load())  # connects using the vault StringSession
        assert isinstance(identity["id"], int), identity
    finally:
        # Restore the sandbox to the file backend no matter what happened above.
        restore = config.load()
        if restore.secrets_backend == "keyring":
            secrets.migrate_to_file(restore)
            config.save(restore)

    back = secrets.get_backend(config.load())
    assert back.name == "file" and back.has_session(), "did not restore the file backend"
