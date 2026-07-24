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


def test_transcriber_fields_round_trip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    cfg = config.Config(
        api_id=1,
        api_hash="h",
        transcriber="auto",
        whisper_cmd="/usr/bin/whisper-cli",
        whisper_model="small",
    )

    config.save(cfg)
    loaded = config.load()

    assert loaded.transcriber == "auto"
    assert loaded.whisper_cmd == "/usr/bin/whisper-cli"
    assert loaded.whisper_model == "small"


def test_transcriber_fields_default_to_none() -> None:
    cfg = config.Config()
    assert cfg.transcriber is None
    assert cfg.whisper_cmd is None
    assert cfg.whisper_model is None
    assert cfg.transcriber_autoinstall is None


def test_transcriber_autoinstall_round_trips_as_bool(tmp_path: Path, monkeypatch) -> None:
    # A bool must serialize as a TOML bool (true/false), not a quoted string, so it loads
    # back as a real bool — exercises the bool branch in _dump_toml.
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    for value in (True, False):
        config.save(config.Config(api_id=1, api_hash="h", transcriber_autoinstall=value))
        loaded = config.load()
        assert loaded.transcriber_autoinstall is value


def test_transcriber_autoinstall_absent_loads_none(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    config.save(config.Config(api_id=1, api_hash="h"))  # field left at default
    assert config.load().transcriber_autoinstall is None


def test_config_dir_respects_tg_notes_config_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TG_NOTES_CONFIG_DIR", str(tmp_path))

    # The override is the exact config dir (config.toml + session live directly in it).
    assert config.config_dir() == tmp_path
    assert config.config_path() == tmp_path / "config.toml"
    assert config.default_session_path() == tmp_path / "tg-notes.session"

    # A save→load round-trip works in the overridden dir.
    config.save(config.Config(api_id=7, api_hash="cafef00d"))
    loaded = config.load()
    assert loaded.api_id == 7
    assert loaded.api_hash == "cafef00d"

    # TG_NOTES_CONFIG_DIR wins over XDG_CONFIG_HOME when both are set.
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert config.config_dir() == tmp_path
