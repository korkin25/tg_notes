"""Local configuration for tg-notes.

Only secrets and pointers live here — never notes or contacts data. Stored at the XDG
config path as TOML with mode 600. The store's group id is kept here as the source of
truth for which Telegram group is the store (see docs/architecture.md, TGN-D2).
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")
    return Path(base) / "tg-notes"


def config_path() -> Path:
    return config_dir() / "config.toml"


def default_session_path() -> Path:
    return config_dir() / "tg-notes.session"


@dataclass
class Config:
    api_id: int | None = None
    api_hash: str | None = None
    session_path: str | None = None
    storage_group_id: int | None = None
    #: Where secrets live: "file" (default — config.toml + *.session) or "keyring".
    secrets_backend: str | None = None

    @property
    def session(self) -> str:
        return self.session_path or str(default_session_path())

    def is_configured(self) -> bool:
        return bool(self.api_id and self.api_hash)


def load() -> Config:
    path = config_path()
    if not path.exists():
        return Config()
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return Config(
        api_id=data.get("api_id"),
        api_hash=data.get("api_hash"),
        session_path=data.get("session_path"),
        storage_group_id=data.get("storage_group_id"),
        secrets_backend=data.get("secrets_backend"),
    )


def save(cfg: Config) -> Path:
    directory = config_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = config_path()
    path.write_text(_dump_toml(cfg), encoding="utf-8")
    os.chmod(path, 0o600)
    return path


def _dump_toml(cfg: Config) -> str:
    lines = ["# tg-notes local config — secrets + storage pointer. Do not commit."]
    fields = {
        "api_id": cfg.api_id,
        "api_hash": cfg.api_hash,
        "session_path": cfg.session_path,
        "storage_group_id": cfg.storage_group_id,
        "secrets_backend": cfg.secrets_backend,
    }
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, int) and not isinstance(value, bool):
            lines.append(f"{key} = {value}")
        else:
            escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{key} = "{escaped}"')
    return "\n".join(lines) + "\n"
