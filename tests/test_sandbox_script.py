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
