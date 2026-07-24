"""Mocked, CI-safe tests for ``scripts/sandbox.py``.

The sandbox helper lives under ``scripts/`` (not a package), so it is loaded from its path
with ``importlib``. These tests NEVER run the real recipe: the single function that reads
the real credentials and spawns ``tg-notes setup`` (``_provision_sandbox``) is always
monkeypatched, and ``subprocess`` / ``os.execvpe`` are mocked. Nothing here touches the
real config, keyring, or Telegram.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from tg_notes.config import Config

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "sandbox.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("sandbox_helper", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sandbox = _load_module()


# --- sandbox_dir resolution ------------------------------------------------------


def test_sandbox_dir_defaults(monkeypatch) -> None:
    monkeypatch.delenv("TG_NOTES_SANDBOX_DIR", raising=False)
    assert sandbox.sandbox_dir() == sandbox.DEFAULT_SANDBOX


def test_sandbox_dir_env_override(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TG_NOTES_SANDBOX_DIR", str(tmp_path / "sbx"))
    assert sandbox.sandbox_dir() == tmp_path / "sbx"


# --- idempotency: _is_configured / ensure_sandbox --------------------------------


def test_is_configured_true_when_group_present(mocker, tmp_path) -> None:
    mocker.patch.object(sandbox.config, "load", return_value=Config(storage_group_id=-100_1))
    assert sandbox._is_configured(tmp_path) is True


def test_is_configured_false_without_group(mocker, tmp_path) -> None:
    mocker.patch.object(sandbox.config, "load", return_value=Config())
    assert sandbox._is_configured(tmp_path) is False


def test_ensure_sandbox_short_circuits_when_configured(mocker, tmp_path) -> None:
    """A configured sandbox is reused verbatim — the real recipe never runs."""
    mocker.patch.object(sandbox.config, "load", return_value=Config(storage_group_id=-100_999))
    provision = mocker.patch.object(sandbox, "_provision_sandbox")

    assert sandbox.ensure_sandbox(tmp_path) == -100_999
    provision.assert_not_called()


def test_ensure_sandbox_provisions_when_missing(mocker, tmp_path) -> None:
    """When no group id is present, the (mocked) provision step runs, then the id is read."""
    loads = iter([Config(), Config(storage_group_id=-100_123)])
    mocker.patch.object(sandbox.config, "load", side_effect=lambda: next(loads))
    provision = mocker.patch.object(sandbox, "_provision_sandbox")

    assert sandbox.ensure_sandbox(tmp_path) == -100_123
    provision.assert_called_once_with(tmp_path)


def test_ensure_sandbox_errors_when_no_group_after_provision(mocker, tmp_path) -> None:
    mocker.patch.object(sandbox.config, "load", return_value=Config())
    mocker.patch.object(sandbox, "_provision_sandbox")
    with pytest.raises(sandbox.SandboxError):
        sandbox.ensure_sandbox(tmp_path)


# --- real-credential read uses the REAL namespaces (overrides unset) -------------


def test_read_real_credentials_unsets_overrides(monkeypatch, mocker) -> None:
    monkeypatch.setenv("TG_NOTES_CONFIG_DIR", "/sandbox")
    monkeypatch.setenv("TG_NOTES_KEYRING_SERVICE", "tg-notes-sandbox")
    seen: dict[str, str | None] = {}

    def fake_load() -> Config:
        seen["config_dir"] = sandbox.os.environ.get("TG_NOTES_CONFIG_DIR")
        return Config(api_id=42)

    def fake_vault(key: str) -> str:
        seen["keyring_service"] = sandbox.os.environ.get("TG_NOTES_KEYRING_SERVICE")
        return {"api_hash": "realhash", "session": "realsession"}[key]

    mocker.patch.object(sandbox.config, "load", side_effect=fake_load)
    mocker.patch.object(sandbox.secrets, "_vault_read", side_effect=fake_vault)

    assert sandbox._read_real_credentials() == (42, "realhash", "realsession")
    # The real namespaces were read with the sandbox overrides removed ...
    assert seen["config_dir"] is None
    assert seen["keyring_service"] is None
    # ... and the caller's environment is restored afterwards.
    assert sandbox.os.environ["TG_NOTES_CONFIG_DIR"] == "/sandbox"
    assert sandbox.os.environ["TG_NOTES_KEYRING_SERVICE"] == "tg-notes-sandbox"


def test_read_real_credentials_errors_without_api_id(monkeypatch, mocker) -> None:
    monkeypatch.delenv("TG_NOTES_CONFIG_DIR", raising=False)
    mocker.patch.object(sandbox.config, "load", return_value=Config(api_id=None))
    mocker.patch.object(sandbox.secrets, "_vault_read", return_value="x")
    with pytest.raises(sandbox.SandboxError):
        sandbox._read_real_credentials()


# --- CI credential source: seed from env, not the local keyring (TGN-25) ----------
#
# Under GitHub Actions there is no local keyring/session. The dedicated test account's
# credentials arrive as environment variables (from the `ci-functional` secrets), and
# `_provision_sandbox` seeds a throwaway file-backend config from them instead of reading
# the real vault. These tests never touch a real vault or Telegram.

_CI_KEYS = ("TG_NOTES_API_ID", "TG_NOTES_API_HASH", "TG_NOTES_SESSION", "TG_NOTES_TEST_GROUP")


def _set_ci_env(
    monkeypatch,
    *,
    api_id="42",
    api_hash="cihash",
    session="1BcIsThisAStringSession",
    group="-1001234567890",
) -> None:
    """Set (or clear, when a value is ``None``) the CI credential env vars."""
    for key in _CI_KEYS:
        monkeypatch.delenv(key, raising=False)
    for key, value in {
        "TG_NOTES_API_ID": api_id,
        "TG_NOTES_API_HASH": api_hash,
        "TG_NOTES_SESSION": session,
        "TG_NOTES_TEST_GROUP": group,
    }.items():
        if value is not None:
            monkeypatch.setenv(key, value)


def test_read_ci_credentials_from_env(monkeypatch) -> None:
    _set_ci_env(monkeypatch)
    assert sandbox._read_ci_credentials() == (
        42,
        "cihash",
        "1BcIsThisAStringSession",
        -1001234567890,
    )


def test_read_ci_credentials_without_group(monkeypatch) -> None:
    _set_ci_env(monkeypatch, group=None)
    assert sandbox._read_ci_credentials() == (42, "cihash", "1BcIsThisAStringSession", None)


def test_read_ci_credentials_returns_none_when_incomplete(monkeypatch) -> None:
    """A missing required var ⇒ no CI creds ⇒ caller falls back to the local recipe."""
    _set_ci_env(monkeypatch, session=None)
    assert sandbox._read_ci_credentials() is None


def test_read_ci_credentials_bad_api_id(monkeypatch) -> None:
    _set_ci_env(monkeypatch, api_id="not-an-int")
    with pytest.raises(sandbox.SandboxError):
        sandbox._read_ci_credentials()


def test_read_ci_credentials_bad_group(monkeypatch) -> None:
    _set_ci_env(monkeypatch, group="not-an-int")
    with pytest.raises(sandbox.SandboxError):
        sandbox._read_ci_credentials()


def test_provision_uses_ci_credentials(monkeypatch, mocker, tmp_path) -> None:
    """With CI creds in the env, provisioning seeds the file backend from them and never
    reads the real vault; a supplied test group is attached (idempotent re-runs)."""
    _set_ci_env(monkeypatch, group="-1009876543210")
    real = mocker.patch.object(sandbox, "_read_real_credentials")
    saved = mocker.patch.object(sandbox.config, "save")
    write_session = mocker.patch.object(sandbox.secrets, "_write_file_session")
    run_setup = mocker.patch.object(sandbox, "_run_tg_setup")

    sandbox._provision_sandbox(tmp_path)

    real.assert_not_called()
    cfg = saved.call_args[0][0]
    assert cfg.api_id == 42
    assert cfg.api_hash == "cihash"
    assert cfg.secrets_backend == "file"
    assert cfg.storage_group_id == -1009876543210
    assert write_session.call_args[0][1] == "1BcIsThisAStringSession"
    run_setup.assert_called_once_with(tmp_path)


def test_provision_falls_back_to_real_credentials(monkeypatch, mocker, tmp_path) -> None:
    """No CI creds ⇒ the local keyring recipe runs and lets `setup` create the group."""
    for key in _CI_KEYS:
        monkeypatch.delenv(key, raising=False)
    real = mocker.patch.object(
        sandbox, "_read_real_credentials", return_value=(7, "realhash", "realsession")
    )
    saved = mocker.patch.object(sandbox.config, "save")
    write_session = mocker.patch.object(sandbox.secrets, "_write_file_session")
    mocker.patch.object(sandbox, "_run_tg_setup")

    sandbox._provision_sandbox(tmp_path)

    real.assert_called_once()
    cfg = saved.call_args[0][0]
    assert cfg.api_id == 7
    assert cfg.api_hash == "realhash"
    assert cfg.storage_group_id is None
    assert write_session.call_args[0][1] == "realsession"


# --- run: builds sandbox env + execs the given argv ------------------------------


def test_run_execs_with_sandbox_env(mocker, tmp_path) -> None:
    mocker.patch.object(sandbox, "sandbox_dir", return_value=tmp_path)
    mocker.patch.object(sandbox, "ensure_sandbox", return_value=-100_5)
    execvpe = mocker.patch.object(sandbox.os, "execvpe")

    sandbox.cmd_run(["tg-notes", "notes", "list", "--notebook", "daily"])

    execvpe.assert_called_once()
    file, argv, env = execvpe.call_args[0]
    assert file == "tg-notes"
    assert argv == ["tg-notes", "notes", "list", "--notebook", "daily"]
    assert env["TG_NOTES_CONFIG_DIR"] == str(tmp_path)


def test_run_without_command_errors(mocker, tmp_path) -> None:
    mocker.patch.object(sandbox, "sandbox_dir", return_value=tmp_path)
    ensure = mocker.patch.object(sandbox, "ensure_sandbox")
    execvpe = mocker.patch.object(sandbox.os, "execvpe")
    with pytest.raises(sandbox.SandboxError):
        sandbox.cmd_run([])
    ensure.assert_not_called()
    execvpe.assert_not_called()


# --- reset: removes the sandbox dir + session ------------------------------------


def test_reset_removes_sandbox_tree(mocker, tmp_path, capsys) -> None:
    sbx = tmp_path / "sbx"
    sbx.mkdir()
    (sbx / "config.toml").write_text("storage_group_id = -100\n")
    (sbx / "tg-notes.session").write_text("session-bytes")
    mocker.patch.object(sandbox, "sandbox_dir", return_value=sbx)

    assert sandbox.cmd_reset([]) == 0
    assert not sbx.exists()
    assert str(sbx) in capsys.readouterr().out


def test_reset_when_absent_is_noop(mocker, tmp_path, capsys) -> None:
    sbx = tmp_path / "missing"
    mocker.patch.object(sandbox, "sandbox_dir", return_value=sbx)

    assert sandbox.cmd_reset([]) == 0
    assert "nothing to remove" in capsys.readouterr().out


# --- pytest passthrough: TG_NOTES_LIVE + sandbox config dir ----------------------


def test_pytest_runs_gated_live(mocker, tmp_path) -> None:
    mocker.patch.object(sandbox, "sandbox_dir", return_value=tmp_path)
    mocker.patch.object(sandbox, "ensure_sandbox", return_value=-100_7)
    run = mocker.patch.object(sandbox.subprocess, "run")
    run.return_value = mocker.Mock(returncode=0)

    assert sandbox.cmd_pytest(["tests/test_live_media.py", "-v"]) == 0

    cmd = run.call_args[0][0]
    env = run.call_args.kwargs["env"]
    assert cmd[-2:] == ["tests/test_live_media.py", "-v"]
    assert env["TG_NOTES_LIVE"] == "1"
    assert env["TG_NOTES_CONFIG_DIR"] == str(tmp_path)


# --- argparse wiring -------------------------------------------------------------


def test_parser_run_remainder_strips_dashdash() -> None:
    args = sandbox.build_parser().parse_args(["run", "--", "tg-notes", "notes"])
    assert sandbox._strip_dashdash(args.argv) == ["tg-notes", "notes"]


def test_main_dispatches_reset(mocker) -> None:
    reset = mocker.patch.object(sandbox, "cmd_reset", return_value=0)
    assert sandbox.main(["reset"]) == 0
    reset.assert_called_once()


def test_main_reports_sandbox_error(mocker, capsys) -> None:
    mocker.patch.object(sandbox, "cmd_setup", side_effect=sandbox.SandboxError("boom"))
    assert sandbox.main(["setup"]) == 1
    assert "boom" in capsys.readouterr().err
