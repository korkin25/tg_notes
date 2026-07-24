"""Tests for the named-launcher re-exec (``tg_notes.relaunch``).

The launcher makes the KeePassXC / Secret Service confirmation prompt identify the
requesting process as ``tg-notes`` rather than ``python3.12``. These tests NEVER let a
real ``os.execv`` run — it is mocked in every case — and they patch ``sys.executable`` /
``sys.prefix`` / ``sys.platform`` and manage the ``TG_NOTES_RELAUNCHED`` sentinel through
the function-scoped ``monkeypatch`` so the guard never leaks between tests.
"""
from __future__ import annotations

import os
import sys

from tg_notes import config, relaunch

_PURELIB = "/venv/lib/python3.12/site-packages"
_SRC = "/usr/bin/python3.12"
_BOOT_TAIL = "from tg_notes.cli import main;main()"


def _arrange_gate_open(mocker, monkeypatch, *, backend="keyring", paths=None):
    """Patch everything so the gate is OPEN (linux + keyring + no sentinel + not frozen).

    Returns the mocked ``os.execv``. Individual tests then set up the filesystem branch
    (copy / reuse / stale) and assert.
    """
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "executable", "/venv/bin/python")
    monkeypatch.setattr(sys, "prefix", "/venv")
    monkeypatch.setattr(sys, "argv", ["tg-notes", "notes", "list"])
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delenv("TG_NOTES_RELAUNCHED", raising=False)
    mocker.patch.object(
        relaunch.config, "load", return_value=config.Config(secrets_backend=backend)
    )
    mocker.patch.object(
        relaunch.sysconfig,
        "get_paths",
        return_value=paths or {"purelib": _PURELIB, "platlib": _PURELIB},
    )
    mocker.patch.object(relaunch.os.path, "realpath", return_value=_SRC)
    mocker.patch.object(relaunch.os, "makedirs")
    return mocker.patch.object(relaunch.os, "execv")


# --- skip cases -----------------------------------------------------------------------


def test_skip_when_not_linux(mocker, monkeypatch) -> None:
    execv = _arrange_gate_open(mocker, monkeypatch)
    monkeypatch.setattr(sys, "platform", "darwin")

    relaunch.relaunch_as_named()

    execv.assert_not_called()


def test_skip_when_sentinel_set(mocker, monkeypatch) -> None:
    execv = _arrange_gate_open(mocker, monkeypatch)
    monkeypatch.setenv("TG_NOTES_RELAUNCHED", "1")

    relaunch.relaunch_as_named()

    execv.assert_not_called()


def test_skip_when_backend_file(mocker, monkeypatch) -> None:
    execv = _arrange_gate_open(mocker, monkeypatch, backend="file")

    relaunch.relaunch_as_named()

    execv.assert_not_called()


def test_skip_when_backend_none(mocker, monkeypatch) -> None:
    execv = _arrange_gate_open(mocker, monkeypatch, backend=None)

    relaunch.relaunch_as_named()

    execv.assert_not_called()


def test_skip_when_frozen(mocker, monkeypatch) -> None:
    execv = _arrange_gate_open(mocker, monkeypatch)
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    relaunch.relaunch_as_named()

    execv.assert_not_called()


def test_skip_when_no_executable(mocker, monkeypatch) -> None:
    execv = _arrange_gate_open(mocker, monkeypatch)
    monkeypatch.setattr(sys, "executable", "")

    relaunch.relaunch_as_named()

    execv.assert_not_called()


# --- the exec path --------------------------------------------------------------------


def test_exec_when_linux_keyring_no_sentinel(mocker, monkeypatch) -> None:
    execv = _arrange_gate_open(mocker, monkeypatch)
    mocker.patch.object(relaunch.os.path, "exists", return_value=False)
    copy2 = mocker.patch.object(relaunch.shutil, "copy2")
    chmod = mocker.patch.object(relaunch.os, "chmod")

    seen = {}

    def _record(*_a, **_k):
        seen["sentinel"] = os.environ.get("TG_NOTES_RELAUNCHED")

    execv.side_effect = _record

    relaunch.relaunch_as_named()

    launcher = os.path.join("/venv", "libexec", "tg-notes")
    execv.assert_called_once()
    (called_path, argv), _kwargs = execv.call_args
    assert called_path == launcher
    boot = argv[3]
    assert argv == [launcher, "-S", "-c", boot, "notes", "list"]
    assert f"site.addsitedir({_PURELIB!r})" in boot
    assert boot.endswith(_BOOT_TAIL)
    assert boot.startswith("import site;")
    # The sentinel must be set to "1" BEFORE the exec, not after.
    assert seen["sentinel"] == "1"
    assert os.environ["TG_NOTES_RELAUNCHED"] == "1"
    # Fresh copy was made and made executable.
    copy2.assert_called_once_with(_SRC, launcher)
    chmod.assert_called_once_with(launcher, 0o755)


def test_reuse_when_fresh(mocker, monkeypatch) -> None:
    execv = _arrange_gate_open(mocker, monkeypatch)
    mocker.patch.object(relaunch.os.path, "exists", return_value=True)
    mocker.patch.object(relaunch.os.path, "getsize", return_value=100)
    copy2 = mocker.patch.object(relaunch.shutil, "copy2")
    remove = mocker.patch.object(relaunch.os, "remove")

    relaunch.relaunch_as_named()

    copy2.assert_not_called()
    remove.assert_not_called()
    execv.assert_called_once()


def test_recreate_when_stale(mocker, monkeypatch) -> None:
    execv = _arrange_gate_open(mocker, monkeypatch)
    launcher = os.path.join("/venv", "libexec", "tg-notes")
    mocker.patch.object(relaunch.os.path, "exists", return_value=True)
    mocker.patch.object(
        relaunch.os.path,
        "getsize",
        side_effect=lambda path: 10 if path == launcher else 20,
    )
    remove = mocker.patch.object(relaunch.os, "remove")
    copy2 = mocker.patch.object(relaunch.shutil, "copy2")
    mocker.patch.object(relaunch.os, "chmod")

    relaunch.relaunch_as_named()

    remove.assert_called_once_with(launcher)
    copy2.assert_called_once_with(_SRC, launcher)
    execv.assert_called_once()


def test_platlib_differs_adds_second_addsitedir(mocker, monkeypatch) -> None:
    platlib = "/venv/lib/python3.12/lib-dynload"
    execv = _arrange_gate_open(
        mocker,
        monkeypatch,
        paths={"purelib": _PURELIB, "platlib": platlib},
    )
    mocker.patch.object(relaunch.os.path, "exists", return_value=False)
    mocker.patch.object(relaunch.shutil, "copy2")
    mocker.patch.object(relaunch.os, "chmod")

    relaunch.relaunch_as_named()

    boot = execv.call_args[0][1][3]
    assert f"site.addsitedir({_PURELIB!r})" in boot
    assert f"site.addsitedir({platlib!r})" in boot
    assert boot.count("site.addsitedir(") == 2
    assert boot.endswith(_BOOT_TAIL)


def test_platlib_equal_adds_single_addsitedir(mocker, monkeypatch) -> None:
    execv = _arrange_gate_open(mocker, monkeypatch)
    mocker.patch.object(relaunch.os.path, "exists", return_value=False)
    mocker.patch.object(relaunch.shutil, "copy2")
    mocker.patch.object(relaunch.os, "chmod")

    relaunch.relaunch_as_named()

    boot = execv.call_args[0][1][3]
    assert boot.count("site.addsitedir(") == 1


# --- graceful fallbacks (never raise, never exec on setup failure) --------------------


def test_graceful_when_makedirs_raises(mocker, monkeypatch) -> None:
    execv = _arrange_gate_open(mocker, monkeypatch)
    relaunch.os.makedirs.side_effect = OSError("read-only file system")

    relaunch.relaunch_as_named()  # must not raise

    execv.assert_not_called()


def test_graceful_when_copy2_raises(mocker, monkeypatch) -> None:
    execv = _arrange_gate_open(mocker, monkeypatch)
    mocker.patch.object(relaunch.os.path, "exists", return_value=False)
    mocker.patch.object(relaunch.shutil, "copy2", side_effect=OSError("no space"))
    mocker.patch.object(relaunch.os, "chmod")

    relaunch.relaunch_as_named()  # must not raise

    execv.assert_not_called()


def test_graceful_when_execv_raises(mocker, monkeypatch) -> None:
    execv = _arrange_gate_open(mocker, monkeypatch)
    mocker.patch.object(relaunch.os.path, "exists", return_value=False)
    mocker.patch.object(relaunch.shutil, "copy2")
    mocker.patch.object(relaunch.os, "chmod")
    execv.side_effect = OSError("exec format error")

    relaunch.relaunch_as_named()  # must not raise

    execv.assert_called_once()


def test_launcher_path_is_prefix_libexec(mocker, monkeypatch) -> None:
    execv = _arrange_gate_open(mocker, monkeypatch)
    mocker.patch.object(relaunch.os.path, "exists", return_value=False)
    mocker.patch.object(relaunch.shutil, "copy2")
    mocker.patch.object(relaunch.os, "chmod")

    relaunch.relaunch_as_named()

    assert execv.call_args[0][0] == os.path.join(sys.prefix, "libexec", "tg-notes")
