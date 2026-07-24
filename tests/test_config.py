"""Tests for the local configuration module (TGN-2)."""
from __future__ import annotations

import stat
from pathlib import Path

from tg_notes import config


def test_save_load_round_trip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    cfg = config.Config(
        api_id=12345,
        api_hash="deadbeefcafebabe",
        session_path="/custom/tg.session",
        storage_group_id=-1001234567890,
    )

    config.save(cfg)
    loaded = config.load()

    assert loaded.api_id == 12345
    assert loaded.api_hash == "deadbeefcafebabe"
    assert loaded.session_path == "/custom/tg.session"
    assert loaded.storage_group_id == -1001234567890


def test_saved_config_file_mode_is_600(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    cfg = config.Config(api_id=1, api_hash="hash")

    path = config.save(cfg)

    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600


def test_load_returns_empty_config_when_absent(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    loaded = config.load()

    assert loaded.api_id is None
    assert loaded.api_hash is None
    assert loaded.is_configured() is False


def test_default_session_path_follows_xdg(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    cfg = config.Config(api_id=1, api_hash="hash")

    # No explicit session_path → derives from the XDG config dir.
    assert cfg.session == str(tmp_path / "tg-notes" / "tg-notes.session")


def test_explicit_session_path_wins(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    cfg = config.Config(api_id=1, api_hash="hash", session_path="/opt/tg.session")

    assert cfg.session == "/opt/tg.session"


def test_is_configured_true_and_false() -> None:
    assert config.Config(api_id=1, api_hash="hash").is_configured() is True
    assert config.Config(api_id=1).is_configured() is False
    assert config.Config(api_hash="hash").is_configured() is False
    assert config.Config().is_configured() is False
