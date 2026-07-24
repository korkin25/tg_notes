#!/usr/bin/env python3
"""Isolated sandbox for tg-notes live/integration testing.

Every live or end-to-end test MUST run against a THROWAWAY, fully isolated tg-notes
install so the real ``~/.config/tg-notes``, the real keyring, and the real storage group
are never touched. This helper builds and drives that sandbox.

What it does (idempotently):

1. Read the REAL credentials with no sandbox overrides — ``api_id`` from ``config.load()``
   and ``api_hash`` + the Telethon session string from the real keyring namespace
   (``secrets._vault_read``), with ``TG_NOTES_KEYRING_SERVICE`` unset while reading.
2. Seed a sandbox config dir (``$TG_NOTES_SANDBOX_DIR`` or ``~/.config/tg-notes-sandbox``)
   with the ``file`` secrets backend and materialize the session on disk there.
3. Run ``tg-notes setup`` under ``TG_NOTES_CONFIG_DIR=<sandbox>`` so it creates a
   DEDICATED test group (a fresh ``-100…`` id, never the real storage group) and records
   it in the sandbox config.

Why the file backend (not keyring): with the keyring backend ``tg-notes setup`` re-prompts
for the ``api_hash`` (config-level ``is_configured`` can't see the vault) and blocks. The
file backend makes ``setup`` fully non-interactive for scripted/agent runs.

Subcommands::

    scripts/sandbox.py setup                    # ensure the sandbox (prints the export line)
    scripts/sandbox.py run -- tg-notes notes list --notebook daily
    scripts/sandbox.py reset                     # delete the sandbox (next setup is fresh)
    scripts/sandbox.py pytest -- tests/test_live_media.py -v   # gated live tests, sandboxed

SECURITY — the sandbox session file grants FULL account access. It is a copy of the real
Telethon session, so anything holding it can act as the user on Telegram. It is written
``chmod 600`` (via ``secrets._write_file_session``) and lives under the sandbox dir OUTSIDE
the repo (default ``~/.config/tg-notes-sandbox``). Never commit it, never move it into the
working tree, and ``reset`` it when you are done. See docs/sandbox-testing.md.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess  # nosec B404  # only drives our own trusted tg-notes / pytest CLIs
import sys
from contextlib import contextmanager
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:  # make tg_notes importable even when not pip-installed
    sys.path.insert(0, str(REPO_ROOT))

from tg_notes import config, secrets
from tg_notes.config import Config

#: The `tg-notes` entry point to invoke for `setup`; overridable for tests/odd installs.
TG_NOTES_BIN = os.environ.get("TG_NOTES_BIN", "tg-notes")
#: Default sandbox config dir when `$TG_NOTES_SANDBOX_DIR` is unset.
DEFAULT_SANDBOX = Path.home() / ".config" / "tg-notes-sandbox"


class SandboxError(RuntimeError):
    """A sandbox step failed with a message meant for the user (non-zero exit)."""


def sandbox_dir() -> Path:
    """The sandbox config dir: ``$TG_NOTES_SANDBOX_DIR`` or ``~/.config/tg-notes-sandbox``."""
    return Path(os.environ.get("TG_NOTES_SANDBOX_DIR") or DEFAULT_SANDBOX)


def _sandbox_session_path(sbx: Path) -> Path:
    return sbx / "tg-notes.session"


@contextmanager
def _config_dir_env(sbx: Path):
    """Temporarily point ``TG_NOTES_CONFIG_DIR`` at the sandbox for in-process config I/O."""
    prev = os.environ.get("TG_NOTES_CONFIG_DIR")
    os.environ["TG_NOTES_CONFIG_DIR"] = str(sbx)
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("TG_NOTES_CONFIG_DIR", None)
        else:
            os.environ["TG_NOTES_CONFIG_DIR"] = prev


def _load_sandbox_config(sbx: Path) -> Config:
    """Load the sandbox's own ``config.toml`` (empty ``Config`` if it does not exist yet)."""
    with _config_dir_env(sbx):
        return config.load()


def _is_configured(sbx: Path) -> bool:
    """True when the sandbox already has a ``storage_group_id`` — the idempotency short-circuit."""
    return bool(_load_sandbox_config(sbx).storage_group_id)


def _sandbox_env(sbx: Path) -> dict[str, str]:
    """A copy of the current environment with ``TG_NOTES_CONFIG_DIR`` pointed at the sandbox."""
    env = dict(os.environ)
    env["TG_NOTES_CONFIG_DIR"] = str(sbx)
    return env


def _read_real_credentials() -> tuple[int, str, str]:
    """Read the REAL ``api_id`` / ``api_hash`` / session string with no sandbox overrides.

    ``api_id`` comes from the real ``config.load()`` and ``api_hash`` + the Telethon session
    string from the real keyring namespace. ``TG_NOTES_CONFIG_DIR`` and
    ``TG_NOTES_KEYRING_SERVICE`` are unset for the duration so the real config and the real
    ``tg-notes`` vault (not a sandbox namespace) are what we read. Restores them afterwards.
    """
    saved = {
        key: os.environ.pop(key, None)
        for key in ("TG_NOTES_CONFIG_DIR", "TG_NOTES_KEYRING_SERVICE")
    }
    try:
        real = config.load()
        api_id = real.api_id
        api_hash = secrets._vault_read("api_hash")
        session_str = secrets._vault_read("session")
    finally:
        for key, value in saved.items():
            if value is not None:
                os.environ[key] = value
    if not api_id:
        raise SandboxError("no real api_id in your config — run `tg-notes setup` first")
    if not api_hash:
        raise SandboxError("no real api_hash in your keyring — is the vault unlocked?")
    if not session_str:
        raise SandboxError("no real session in your keyring — run `tg-notes login` first")
    return api_id, api_hash, session_str


def _read_ci_credentials() -> tuple[int, str, str, int | None] | None:
    """Read the dedicated test account's credentials from the environment (CI path, TGN-25).

    Under GitHub Actions there is no local keyring, so the credentials arrive as env vars
    (the ``ci-functional`` environment secrets): ``TG_NOTES_API_ID``, ``TG_NOTES_API_HASH``,
    ``TG_NOTES_SESSION`` (a Telethon ``StringSession`` for a **dedicated test account**, never
    a personal one) and the optional ``TG_NOTES_TEST_GROUP`` (a pre-created dedicated group id
    so ``setup`` attaches instead of creating a fresh group every run).

    Returns ``(api_id, api_hash, session_str, group_id | None)`` when the three required vars
    are all present, or ``None`` when they are not — the caller then falls back to the local
    keyring recipe (:func:`_read_real_credentials`).

    Raises:
        SandboxError: if ``TG_NOTES_API_ID`` / ``TG_NOTES_TEST_GROUP`` are set but not integers.
    """
    raw_id = os.environ.get("TG_NOTES_API_ID")
    api_hash = os.environ.get("TG_NOTES_API_HASH")
    session_str = os.environ.get("TG_NOTES_SESSION")
    if not (raw_id and api_hash and session_str):
        return None
    try:
        api_id = int(raw_id)
    except ValueError as exc:
        raise SandboxError(f"TG_NOTES_API_ID must be an integer, got {raw_id!r}") from exc
    group_id: int | None = None
    raw_group = os.environ.get("TG_NOTES_TEST_GROUP")
    if raw_group:
        try:
            group_id = int(raw_group)
        except ValueError as exc:
            raise SandboxError(
                f"TG_NOTES_TEST_GROUP must be an integer, got {raw_group!r}"
            ) from exc
    return api_id, api_hash, session_str, group_id


def _run_tg_setup(sbx: Path) -> None:
    """Run ``tg-notes setup`` under the sandbox config dir to create the dedicated test group."""
    env = _sandbox_env(sbx)
    env.pop("TG_NOTES_KEYRING_SERVICE", None)  # sandbox uses the file backend end-to-end
    try:
        result = subprocess.run(  # nosec B603  # fixed argv, no shell; our own tg-notes CLI
            [TG_NOTES_BIN, "setup"],
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SandboxError(
            f"could not run `{TG_NOTES_BIN}` — is tg-notes installed / on PATH? ({exc})"
        ) from exc
    if result.returncode != 0:
        raise SandboxError(
            f"`{TG_NOTES_BIN} setup` failed (exit {result.returncode}):\n"
            f"{(result.stderr or result.stdout).strip()}"
        )


def _provision_sandbox(sbx: Path) -> None:
    """Seed the sandbox from credentials, then create/attach its dedicated test group.

    Credentials come from the environment when the CI vars are set (``_read_ci_credentials``
    — the GitHub Actions path, with an optionally pre-created test group), otherwise from the
    local keyring (``_read_real_credentials`` — the developer-machine path). Either way the
    session is materialized on disk under the file backend so ``setup`` runs non-interactively.

    NOTE: this is the ONE function that touches real/CI credentials and spawns ``setup``;
    tests monkeypatch it so neither recipe runs unintentionally.
    """
    ci = _read_ci_credentials()
    if ci is not None:
        api_id, api_hash, session_str, group_id = ci
    else:
        api_id, api_hash, session_str = _read_real_credentials()
        group_id = None  # let `setup` create a fresh dedicated group on the dev machine
    sbx.mkdir(parents=True, exist_ok=True)
    os.chmod(sbx, 0o700)
    cfg = Config(
        api_id=api_id,
        api_hash=api_hash,
        secrets_backend="file",
        session_path=str(_sandbox_session_path(sbx)),
        storage_group_id=group_id,  # attach to a pre-created dedicated group when given
    )
    with _config_dir_env(sbx):
        config.save(cfg)
        secrets._write_file_session(cfg, session_str)  # writes the *.session chmod 600
    _run_tg_setup(sbx)


def ensure_sandbox(sbx: Path) -> int:
    """Ensure the sandbox exists per the recipe and return its dedicated group id. Idempotent."""
    if not _is_configured(sbx):
        _provision_sandbox(sbx)
    group_id = _load_sandbox_config(sbx).storage_group_id
    if not group_id:
        raise SandboxError("sandbox setup produced no storage_group_id — check `tg-notes setup`")
    return group_id


def _remove_sandbox(sbx: Path) -> list[Path]:
    """Delete the sandbox config dir (config + session live inside) and any stray session
    file a custom ``session_path`` might have placed outside it. Returns the paths removed."""
    removed: list[Path] = []
    if sbx.exists():
        shutil.rmtree(sbx)
        removed.append(sbx)
    session = _sandbox_session_path(sbx)
    for extra in (session, Path(str(session) + "-journal")):
        if extra.exists():  # only reachable if it lived outside the dir
            extra.unlink()
            removed.append(extra)
    return removed


# --- subcommands -----------------------------------------------------------------


def cmd_setup(_argv: list[str]) -> int:
    """Ensure the sandbox and print its dir, dedicated group id, and the export line to use."""
    sbx = sandbox_dir()
    group_id = ensure_sandbox(sbx)
    session = _sandbox_session_path(sbx)
    print(f"sandbox dir     : {sbx}")
    print(f"dedicated group : {group_id}")
    print(f"session file    : {session}  (chmod 600, full account access — never commit)")
    print()
    print("# use the sandbox in your shell:")
    print(f"export TG_NOTES_CONFIG_DIR={sbx}")
    return 0


def cmd_run(argv: list[str]) -> int:
    """Ensure the sandbox, then exec ``argv`` with ``TG_NOTES_CONFIG_DIR`` set to it."""
    if not argv:
        raise SandboxError("nothing to run — usage: sandbox.py run -- <cmd> [args...]")
    sbx = sandbox_dir()
    ensure_sandbox(sbx)
    env = _sandbox_env(sbx)
    os.execvpe(argv[0], argv, env)  # nosec B606  # no shell; replaces us with the caller's cmd
    return 0  # unreachable in practice (execvpe never returns on success)


def cmd_reset(_argv: list[str]) -> int:
    """Delete the sandbox config dir + session so the next setup builds a fresh group."""
    sbx = sandbox_dir()
    removed = _remove_sandbox(sbx)
    if removed:
        print("removed:")
        for path in removed:
            print(f"  {path}")
    else:
        print(f"nothing to remove — no sandbox at {sbx}")
    return 0


def _pytest_cmd() -> list[str]:
    """Prefer the repo's ``.venv`` pytest; fall back to the current interpreter's pytest."""
    venv_pytest = REPO_ROOT / ".venv" / "bin" / "pytest"
    if venv_pytest.exists():
        return [str(venv_pytest)]
    return [sys.executable, "-m", "pytest"]


def cmd_pytest(argv: list[str]) -> int:
    """Run pytest against the sandbox with ``TG_NOTES_LIVE=1`` so the gated live tests fire."""
    sbx = sandbox_dir()
    ensure_sandbox(sbx)
    env = _sandbox_env(sbx)
    env["TG_NOTES_LIVE"] = "1"
    result = subprocess.run(  # nosec B603  # fixed pytest argv, no shell
        [*_pytest_cmd(), *argv],
        env=env,
        check=False,
    )
    return result.returncode


def _strip_dashdash(argv: list[str]) -> list[str]:
    """Drop a leading ``--`` left by ``argparse.REMAINDER`` (``run -- cmd`` → ``cmd``)."""
    return argv[1:] if argv and argv[0] == "--" else argv


def build_parser() -> argparse.ArgumentParser:
    """Build the argparse CLI for the sandbox helper."""
    parser = argparse.ArgumentParser(
        prog="sandbox.py",
        description="Isolated sandbox for tg-notes live/integration testing.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("setup", help="ensure the isolated sandbox exists (idempotent)")
    p_run = sub.add_parser("run", help="run a command against the sandbox")
    p_run.add_argument(
        "argv", nargs=argparse.REMAINDER, help="-- <cmd> [args...] to run in the sandbox"
    )
    sub.add_parser("reset", help="delete the sandbox config dir + session file")
    p_pytest = sub.add_parser("pytest", help="run the gated live tests against the sandbox")
    p_pytest.add_argument(
        "argv", nargs=argparse.REMAINDER, help="-- <pytest args...>"
    )
    return parser


#: command -> (handler attribute name, whether it takes passthrough argv). Handlers are
#: resolved by name at call time via ``getattr`` so tests can monkeypatch them.
_HANDLERS = {
    "setup": ("cmd_setup", False),
    "run": ("cmd_run", True),
    "reset": ("cmd_reset", False),
    "pytest": ("cmd_pytest", True),
}


def main(argv: list[str] | None = None) -> int:
    """Parse args and dispatch to the matching subcommand handler."""
    args = build_parser().parse_args(argv)
    handler_name, takes_argv = _HANDLERS[args.command]
    handler = globals()[handler_name]  # resolved by name so tests can monkeypatch handlers
    passthrough = _strip_dashdash(getattr(args, "argv", [])) if takes_argv else []
    try:
        return handler(passthrough)
    except SandboxError as exc:
        print(f"sandbox: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
