"""Re-exec the CLI through a named launcher so the vault prompt shows ``tg-notes``.

KeePassXC (and any Secret Service provider that confirms access) identifies the
requesting process by its real executable — ``/proc/<pid>/exe``. For a Python CLI that
is ``python3.12``, which is meaningless in the confirmation dialog. To make the prompt
say ``tg-notes`` instead, on Linux with the keyring backend we re-exec the process
through a copy of the base interpreter placed at ``<venv>/libexec/tg-notes``. The venv's
site-packages are added back explicitly via ``site.addsitedir`` under ``-S`` (system
site-packages isolated), so the exe basename is exactly ``tg-notes`` — with no collision
with the ``<venv>/bin/tg-notes`` console script — while ``telethon`` / ``secretstorage``
/ ``tg_notes`` still resolve.

The whole thing is best-effort: a read-only venv, a missing interpreter, or any other
failure simply skips the re-exec (the prompt then shows ``python`` but the CLI keeps
working). ``TG_NOTES_RELAUNCHED`` is an internal loop guard.
"""
from __future__ import annotations

import os
import shutil
import sys
import sysconfig

from . import config


def relaunch_as_named() -> None:
    """Re-exec the CLI via ``<venv>/libexec/tg-notes`` so the vault prompt names it.

    No-op unless on Linux, using the keyring backend, not already re-exec'd, and running
    a normal (non-frozen) interpreter. Every failure path degrades gracefully to normal
    in-process execution.
    """
    # 1. Gate — only re-exec where it actually helps and is safe.
    if not sys.platform.startswith("linux"):
        return
    if os.environ.get("TG_NOTES_RELAUNCHED") == "1":
        return
    if getattr(sys, "frozen", False) or not sys.executable:
        return
    if config.load().secrets_backend != "keyring":
        return

    # 2. Resolve the venv site-packages to hand back to the isolated (-S) interpreter.
    paths = sysconfig.get_paths()
    purelib = paths["purelib"]
    platlib = paths["platlib"]

    # 3. Where the named copy of the interpreter lives, and what to copy from.
    launcher_dir = os.path.join(sys.prefix, "libexec")
    launcher = os.path.join(launcher_dir, "tg-notes")
    src = os.path.realpath(sys.executable)

    # 4. Ensure a fresh named copy of the interpreter exists. Any OSError (e.g. a
    #    read-only venv) → skip the re-exec; the CLI keeps working in-process.
    try:
        os.makedirs(launcher_dir, exist_ok=True)
        if os.path.exists(launcher) and os.path.getsize(launcher) == os.path.getsize(src):
            pass  # up to date — reuse it
        else:
            if os.path.exists(launcher):
                os.remove(launcher)
            shutil.copy2(src, launcher)
            # 0o755 is intentional: a copy of the interpreter has to be executable
            # (mirrors the mode of the system python it copies).
            os.chmod(launcher, 0o755)  # nosec B103
    except OSError:
        return

    # 5. Bootstrap: add the venv site-packages, then run the CLI directly.
    boot = f"import site;site.addsitedir({purelib!r});"
    if platlib != purelib:
        boot += f"site.addsitedir({platlib!r});"
    boot += "from tg_notes.cli import main;main()"

    # 6. Re-exec through the named launcher. Set the loop guard first (execv replaces the
    #    process image, so os.environ must be updated before). argv[1:] carries the
    #    original arguments through, so main()'s argparse sees them unchanged.
    os.environ["TG_NOTES_RELAUNCHED"] = "1"
    try:
        # Fixed launcher path (a copy of this interpreter) with a literal argv, no shell
        # and no untrusted input; -S isolates system site-packages.
        os.execv(launcher, [launcher, "-S", "-c", boot, *sys.argv[1:]])  # nosec B606
    except OSError:
        return  # fall through to normal in-process execution
