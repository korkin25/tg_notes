"""tg-notes command-line entrypoint.

Command surface (implemented incrementally — see TODO.md):
  login                        one-time interactive Telegram login     (TGN-2)
  whoami                       print the logged-in account identity    (TGN-2)
  setup                        create/attach the storage group        (TGN-3)
  note add                     append a note to a notebook             (TGN-4)
  notes list                   list raw notes from a notebook          (TGN-5)
  contacts list|set|remove     address book in the contacts topic      (TGN-6)
  send                         publish a compiled note to a contact    (TGN-7)
  notebooks list               list notebook topics                    (TGN-8)

All Phase 1 commands are implemented; the intelligence (composing/compiling notes) lives
in the agent Skills on top, not here.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from . import __version__, config, secrets, telegram


def _login(args: argparse.Namespace) -> int:
    """Run the one-time interactive Telegram login and store the session."""
    cfg = config.load()
    try:
        identity = telegram.login(cfg)
    except telegram.NotConfiguredError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    print(json.dumps(identity, ensure_ascii=False))
    return 0


def _setup(args: argparse.Namespace) -> int:
    """Provision/attach the storage group, driving first-run onboarding as needed.

    ``setup`` is self-sufficient: if the Telegram credentials are missing it prompts for
    them and saves them to local config (mode 600); if the device is not logged in it runs
    the interactive ``login`` (phone → code → 2FA) and retries. Then it creates or attaches
    the storage group and persists its id.
    """
    cfg = config.load()

    # 1. Ensure credentials — ask and persist (chmod 600) when they are missing.
    if not cfg.is_configured():
        if not _prompt_credentials(cfg):
            _instruct_configure()
            return 1
        config.save(cfg)

    # 2. Provision; a fresh/expired session surfaces as NotAuthorized → log in and retry.
    try:
        result = telegram.setup(cfg, notebook=args.notebook)
    except telegram.NotConfiguredError:
        _instruct_configure()
        return 1
    except telegram.NotAuthorizedError:
        telegram.login(cfg)  # interactive phone/code/2FA, then retry provisioning
        result = telegram.setup(cfg, notebook=args.notebook)

    cfg.storage_group_id = result["group_id"]
    config.save(cfg)
    print(json.dumps(result, ensure_ascii=False))
    if not cfg.secrets_backend:
        sys.stderr.write(
            "\ntip: to keep your api_hash + session in a secret store (KeePassXC/keyring) "
            "instead of local files, run `tg-notes secrets doctor`.\n"
        )
    return 0


def _ask(prompt: str) -> str:
    """Read a single trimmed line from the user (wrapped for testability)."""
    return input(prompt).strip()


def _prompt_credentials(cfg: config.Config) -> bool:
    """Interactively collect ``api_id``/``api_hash`` onto ``cfg``.

    Returns ``True`` when both were captured, ``False`` if the input was empty or the
    ``api_id`` was not an integer (the caller then prints full guidance and aborts).
    """
    sys.stderr.write(
        "tg-notes needs your Telegram api_id/api_hash (one-time).\n"
        "Get them at https://my.telegram.org → 'API development tools'.\n"
    )
    raw_id = _ask("api_id: ")
    api_hash = _ask("api_hash: ")
    if not raw_id or not api_hash:
        return False
    try:
        cfg.api_id = int(raw_id)
    except ValueError:
        return False
    cfg.api_hash = api_hash
    return True


def _instruct_configure() -> None:
    """Explain how to supply Telegram credentials by hand (used when the prompt is skipped
    or the entered values were unusable)."""
    path = config.config_path()
    sys.stderr.write(
        "tg-notes still has no usable Telegram api_id/api_hash.\n"
        "\n"
        "Set them up manually:\n"
        "  1. Get an api_id and api_hash at https://my.telegram.org\n"
        "     (log in → 'API development tools' → create an app).\n"
        f"  2. Save them to {path}:\n"
        "         api_id = 1234567\n"
        '         api_hash = "your_api_hash"\n'
        f"     Then keep the secrets private: chmod 600 {path}\n"
        "  3. Run `tg-notes login` to authorize this device (phone → code → 2FA).\n"
        "  4. Run `tg-notes setup` again.\n"
    )


def _whoami(args: argparse.Namespace) -> int:
    """Print the identity of the currently logged-in account."""
    cfg = config.load()
    try:
        identity = telegram.whoami(cfg)
    except telegram.NotConfiguredError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    except telegram.NotAuthorizedError as exc:
        sys.stderr.write(f"{exc}\n")
        return 3
    print(json.dumps(identity, ensure_ascii=False))
    return 0


def _handle_store_errors(exc: Exception) -> int:
    """Map a store-access exception to a user message and exit code (4 / 1 / 3)."""
    if isinstance(exc, telegram.NotSetUpError):
        sys.stderr.write(f"{exc}\n")
        return 4
    if isinstance(exc, telegram.NotConfiguredError):
        _instruct_configure()
        return 1
    sys.stderr.write("not logged in — run `tg-notes login` (or `tg-notes setup`) first\n")
    return 3


_STORE_ERRORS = (
    telegram.NotSetUpError,
    telegram.NotConfiguredError,
    telegram.NotAuthorizedError,
)


def _read_text_arg(path: str) -> str:
    """Read note text from a file, or from stdin when ``path`` is ``-``."""
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def _interactive() -> bool:
    """True only when both stdin and stdout are real terminals."""
    return sys.stdin.isatty() and sys.stdout.isatty()


#: Fuzzy finders tried in order; first one on PATH wins.
_PICKERS = ("fzf", "sk", "fzy")


def _pick(options: list[tuple[str, str]], prompt: str) -> str | None:
    """Let the user choose one of ``options`` (each a ``(value, label)`` pair).

    Uses a fuzzy finder (fzf/sk/fzy) when one is installed; otherwise a numbered prompt.
    Returns the chosen ``value``, or ``None`` if there is nothing to choose, the session is
    not interactive, or the user cancels. Never reads stdin/prompts in a non-TTY session.
    """
    import shutil

    # Safe: finder resolved via shutil.which, fixed argv, no shell, labels fed via stdin.
    import subprocess  # nosec B404

    options = list(options)
    if not options or not _interactive():
        return None
    labels = [label for _, label in options]
    finder = None
    for name in _PICKERS:
        finder = shutil.which(name)
        if finder:
            break
    chosen: str | None
    if finder:
        try:
            proc = subprocess.run(  # nosec B603
                [finder, "--prompt", f"{prompt}> ", "--height", "40%", "--reverse"],
                input="\n".join(labels),
                text=True,
                capture_output=True,
                check=False,
            )
        except OSError:
            return None
        chosen = proc.stdout.strip() if proc.returncode == 0 else None
    else:
        for i, label in enumerate(labels, 1):
            sys.stderr.write(f"  {i}. {label}\n")
        raw = input(f"{prompt} [1-{len(labels)}]: ").strip()
        try:
            chosen = labels[int(raw) - 1]
        except (ValueError, IndexError):
            chosen = None
    if chosen is None:
        return None
    return next((value for value, label in options if label == chosen), None)


def _contact_label(c: dict) -> str:
    """Build a human-readable one-line label for a contact picker entry."""
    bits = [c["key"]]
    if c.get("name"):
        bits.append(f"— {c['name']}")
    if c.get("chat_id"):
        bits.append(f"({c['chat_id']})")
    return " ".join(bits)


def _note_add(args: argparse.Namespace) -> int:
    """Append a note to a notebook topic — text, or a media file with --file (TGN-4)."""
    cfg = config.load()
    if args.file is not None:
        return _note_add_file(cfg, args)
    if not args.text_file:
        sys.stderr.write("provide --text-file <f> (or --file <path> for media)\n")
        return 2
    try:
        text = _read_text_arg(args.text_file)
    except OSError as exc:
        sys.stderr.write(f"cannot read note text from {args.text_file}: {exc}\n")
        return 1
    try:
        result = telegram.note_add(
            cfg, notebook=args.notebook, text=text, hashtags=args.hashtag
        )
    except _STORE_ERRORS as exc:
        return _handle_store_errors(exc)
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


def _note_add_file(cfg: config.Config, args: argparse.Namespace) -> int:
    """Upload a media file as a note (media Phase 1).

    Caption comes from ``--caption``; if omitted, ``--text-file`` (when given) is read as
    the caption, mirroring the text path's text source. Any ``--hashtag`` tokens are
    appended to the caption.
    """
    caption = args.caption
    if caption is None and args.text_file:
        try:
            caption = _read_text_arg(args.text_file)
        except OSError as exc:
            sys.stderr.write(f"cannot read caption from {args.text_file}: {exc}\n")
            return 1
    try:
        result = telegram.note_add_file(
            cfg,
            notebook=args.notebook,
            file_path=args.file,
            caption=caption,
            hashtags=args.hashtag,
        )
    except _STORE_ERRORS as exc:
        return _handle_store_errors(exc)
    except (FileNotFoundError, ValueError) as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


def _parse_since(value: str) -> datetime:
    """Parse a ``--since`` bound into a timezone-aware datetime (naive input is local).

    Accepts ``today``, ``HH:MM`` (today at that time), a date (``YYYY-MM-DD``), or a full
    ISO datetime. Raises ``ValueError`` on anything else.
    """
    text = value.strip()
    now = datetime.now().astimezone()
    if text.lower() == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        clock = datetime.strptime(text, "%H:%M")  # noqa: DTZ007 (time-of-day only)
    except ValueError:
        pass
    else:
        return now.replace(hour=clock.hour, minute=clock.minute, second=0, microsecond=0)
    parsed = datetime.fromisoformat(text)  # raises ValueError on bad input
    return parsed if parsed.tzinfo is not None else parsed.astimezone()


def _notes_list(args: argparse.Namespace) -> int:
    """List the raw notes of a notebook topic as JSON (TGN-5)."""
    cfg = config.load()
    since = None
    if args.since:
        try:
            since = _parse_since(args.since)
        except ValueError as exc:
            sys.stderr.write(f"invalid --since value {args.since!r}: {exc}\n")
            return 1
    notebook = args.notebook
    if notebook is None:
        # Preserve the old non-interactive default (daily); offer a picker to humans.
        notebook = "daily"
        if _interactive():
            try:
                items = telegram.notebooks_list(cfg)
            except _STORE_ERRORS as exc:
                return _handle_store_errors(exc)
            if items:
                picked = _pick([(n["name"], n["name"]) for n in items], "notebook")
                if picked is not None:
                    notebook = picked
    try:
        notes = telegram.notes_list(cfg, notebook=notebook, since=since)
    except _STORE_ERRORS as exc:
        return _handle_store_errors(exc)
    print(json.dumps(notes, ensure_ascii=False))
    return 0


def _contacts_list(args: argparse.Namespace) -> int:
    """Print the address book as JSON (TGN-6)."""
    cfg = config.load()
    try:
        items = telegram.contacts_list(cfg)
    except _STORE_ERRORS as exc:
        return _handle_store_errors(exc)
    print(json.dumps(items, ensure_ascii=False))
    return 0


def _contacts_set(args: argparse.Namespace) -> int:
    """Create or update a contact (TGN-6)."""
    cfg = config.load()
    try:
        result = telegram.contacts_set(
            cfg,
            args.key,
            chat_id=args.chat_id,
            name=args.name,
            topic_id=args.topic_id,
            mention=args.mention,
            style=args.style,
        )
    except _STORE_ERRORS as exc:
        return _handle_store_errors(exc)
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


def _contacts_remove(args: argparse.Namespace) -> int:
    """Remove a contact by key (TGN-6)."""
    cfg = config.load()
    key = args.key
    if key is None:
        if not _interactive():
            sys.stderr.write("specify a contact key (e.g. `tg-notes contacts remove boss`)\n")
            return 2
        try:
            items = telegram.contacts_list(cfg)
        except _STORE_ERRORS as exc:
            return _handle_store_errors(exc)
        if not items:
            sys.stderr.write("no contacts yet — nothing to remove\n")
            return 2
        key = _pick([(c["key"], _contact_label(c)) for c in items], "contact")
        if key is None:
            sys.stderr.write("no contact selected\n")
            return 2
    try:
        result = telegram.contacts_remove(cfg, key)
    except _STORE_ERRORS as exc:
        return _handle_store_errors(exc)
    print(json.dumps(result, ensure_ascii=False))
    return 0


def _notebooks_list(args: argparse.Namespace) -> int:
    """List the storage group's notebook topics as JSON (TGN-8)."""
    cfg = config.load()
    try:
        items = telegram.notebooks_list(cfg)
    except _STORE_ERRORS as exc:
        return _handle_store_errors(exc)
    print(json.dumps(items, ensure_ascii=False))
    return 0


def _send(args: argparse.Namespace) -> int:
    """Publish compiled text to a contact's chat/topic (TGN-7)."""
    cfg = config.load()
    # Resolve the contact BEFORE touching the text: agents pass --contact and run
    # non-interactively, so this path stays byte-for-byte unchanged for them.
    contact = args.contact
    if contact is None:
        if not _interactive():
            sys.stderr.write("--contact is required (e.g. --contact boss)\n")
            return 2
        try:
            items = telegram.contacts_list(cfg)
        except _STORE_ERRORS as exc:
            return _handle_store_errors(exc)
        if not items:
            sys.stderr.write("no contacts yet — add one with `tg-notes contacts set`\n")
            return 2
        contact = _pick([(c["key"], _contact_label(c)) for c in items], "contact")
        if contact is None:
            sys.stderr.write("no contact selected\n")
            return 2
    try:
        text = _read_text_arg(args.text_file)
    except OSError as exc:
        sys.stderr.write(f"cannot read text from {args.text_file}: {exc}\n")
        return 1
    try:
        result = telegram.send(cfg, contact, text, dry_run=args.dry_run)
    except _STORE_ERRORS as exc:
        return _handle_store_errors(exc)
    except telegram.ContactNotFoundError as exc:
        sys.stderr.write(f"{exc}\n")
        return 5
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


#: Known secret-store daemon process names → friendly labels.
_SECRET_PROVIDERS = {
    "gnome-keyring-d": "gnome-keyring",
    "keepassxc": "keepassxc",
    "kwalletd6": "kwalletd (KDE)",
    "kwalletd5": "kwalletd (KDE)",
    "ksecretd": "ksecretd (KDE)",
}


def _busctl_list() -> str | None:
    """Return `busctl --user list` output, or None if busctl is unavailable."""
    import shutil

    # Safe: trusted binary resolved via shutil.which, fixed argv, no shell, no user input.
    import subprocess  # nosec B404

    busctl = shutil.which("busctl")
    if not busctl:
        return None
    try:
        return subprocess.run(  # nosec B603
            [busctl, "--user", "list"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None


def _secret_service_provider() -> str | None:
    """Best-effort name of the process owning org.freedesktop.secrets (None if unknown)."""
    out = _busctl_list()
    if out is None:
        return None
    for line in out.splitlines():
        if line.startswith("org.freedesktop.secrets"):
            parts = line.split()
            return parts[2] if len(parts) > 2 else None
    return None


def _available_secret_stores() -> list[str]:
    """List detected secret-store providers, noting which one serves Secret Service."""
    out = _busctl_list()
    if out is None:
        return []
    ss_owner = None
    running: dict[str, str] = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        name, process = parts[0], parts[2]
        if name == "org.freedesktop.secrets":
            ss_owner = process
        if process in _SECRET_PROVIDERS:
            running[_SECRET_PROVIDERS[process]] = process
    stores = []
    for label, process in running.items():
        state = "serves Secret Service" if process == ss_owner else "running"
        stores.append(f"{label} ({state})")
    return sorted(stores)


def _secrets_state(cfg: config.Config) -> dict:
    """Gather the full secrets diagnosis (backend, vault probe, provider, stores)."""
    backend = secrets.get_backend(cfg)
    probe_ok, probe_kind = secrets.keyring_probe()
    return {
        "backend": backend.name,
        "configured": backend.is_configured(),
        "has_session": backend.has_session(),
        "keyring_installed": probe_kind != "not-installed",
        "probe_ok": probe_ok,
        "probe_kind": probe_kind,
        "provider": _secret_service_provider(),
        "stores": _available_secret_stores(),
        "config_dir": str(config.config_dir()),
        "keyring_service": secrets._keyring_service(),
    }


def _secrets_recommendations(state: dict) -> list[str]:
    """Turn a secrets diagnosis into ordered, actionable recommendations."""
    recs: list[str] = []
    if not state["configured"]:
        recs.append("Not configured — run `tg-notes setup` to add api_id/api_hash and log in.")
    if not state["keyring_installed"]:
        recs.append(
            'Secret-store support is not installed — `pipx install "tg-notes[keyring]"` to '
            "use a vault; otherwise the file backend is fine."
        )
        return recs

    provider = state["provider"]
    stores = state["stores"]
    kp_running = any(s.startswith("keepassxc (running") for s in stores)
    kp_serves = any(s.startswith("keepassxc (serves") for s in stores)

    if provider is None:
        recs.append(
            "No Secret Service provider is running — start a vault (KeePassXC / gnome-keyring "
            "/ KWallet) or stay on the file backend."
        )
    elif "gnome-keyring" in provider and kp_running and not kp_serves:
        recs.append(
            "KeePassXC is running but gnome-keyring holds the Secret Service. To hand it to "
            "KeePassXC: disable gnome-keyring's secrets (systemd user drop-in "
            "`--components=pkcs11`; `~/.config/autostart/gnome-keyring-secrets.desktop` with "
            "`Hidden=true`; a user D-Bus override "
            "`~/.local/share/dbus-1/services/org.freedesktop.secrets.service` → `/bin/false`), "
            "enable KeePassXC autostart + `loginctl enable-linger`, then re-login."
        )

    if state["probe_ok"]:
        if state["backend"] == "file":
            recs.append(
                "The vault works — move your secrets into it with "
                "`tg-notes secrets migrate --to keyring`."
            )
        else:
            recs.append("Vault backend is active and working — nothing to do.")
    else:
        kind = state["probe_kind"]
        if kind == "no-collection":
            recs.append(
                "The vault has no default collection — in KeePassXC: Database Settings → "
                "Secret Service Integration → enable 'Expose entries under this group' and "
                "pick/create a group."
            )
        elif kind == "locked":
            recs.append(
                "The vault confirms every access, and KeePassXC ties that grant to the "
                "short-lived D-Bus connection — so a fresh CLI run re-prompts each time and via "
                "keyring usually fails (persistent per-app authorization is unimplemented, "
                "keepassxc#6458). Practical fix: in KeePassXC expose a DEDICATED group holding "
                "only tg-notes' secrets (Database Settings → Secret Service Integration → "
                "'Expose entries under this group'), then turn OFF 'confirm when passwords are "
                "retrieved by clients' (Settings → Secret Service Integration). Confirmation is "
                "app-global, so the dedicated group keeps the always-readable surface limited to "
                "the tg-notes session — the same trust boundary as the on-disk session file. See "
                "docs/keepassxc.md."
            )
        elif kind and kind.startswith("error:"):
            recs.append(
                f"Vault round-trip failed ({kind}) — make sure the vault app is running and "
                "its database is unlocked."
            )
    return recs


def _secrets_doctor(args: argparse.Namespace) -> int:
    """Diagnose the secrets setup and print actionable recommendations (TGN-18)."""
    state = _secrets_state(config.load())
    recs = _secrets_recommendations(state)
    if getattr(args, "json", False):
        print(json.dumps({**state, "recommendations": recs}, ensure_ascii=False))
        return 0
    probe = "OK" if state["probe_ok"] else f"FAILED ({state['probe_kind']})"
    print("tg-notes secrets — diagnosis")
    print(f"  backend         : {state['backend']}")
    print(f"  config dir      : {state['config_dir']}")
    print(f"  keyring service : {state['keyring_service']}")
    print(f"  configured      : {state['configured']}")
    print(f"  session present : {state['has_session']}")
    print(f"  Secret Service  : {state['provider'] or '(nobody serves org.freedesktop.secrets)'}")
    print(f"  vault round-trip: {probe}")
    if state["stores"]:
        print(f"  detected stores : {', '.join(state['stores'])}")
    print("\nRecommendations:")
    for i, rec in enumerate(recs, 1):
        print(f"  {i}. {rec}")
    if not recs:
        print("  none — you're all set.")
    return 0


def _secrets_status(args: argparse.Namespace) -> int:
    """Print the active secrets backend and what's available (TGN-18)."""
    cfg = config.load()
    backend = secrets.get_backend(cfg)
    status = {
        "backend": backend.name,
        "configured": backend.is_configured(),
        "has_session": backend.has_session(),
        "keyring_available": secrets.keyring_available(),
        "secret_service_provider": _secret_service_provider(),
        "available_stores": _available_secret_stores(),
        "config_dir": str(config.config_dir()),
        "keyring_service": secrets._keyring_service(),
    }
    print(json.dumps(status, ensure_ascii=False))
    return 0


def _secrets_migrate(args: argparse.Namespace) -> int:
    """Move secrets (api_hash + session) between the file and keyring backends (TGN-18)."""
    cfg = config.load()
    target = args.to
    if target is None:
        if not _interactive():
            sys.stderr.write("specify --to file|keyring\n")
            return 2
        target = _pick([("file", "file"), ("keyring", "keyring")], "backend")
        if target is None:
            sys.stderr.write("no backend selected\n")
            return 2
    current = secrets.get_backend(cfg).name
    if target == current:
        print(json.dumps({"backend": current, "migrated": False, "note": "already active"}))
        return 0
    try:
        if target == "keyring":
            state = _secrets_state(cfg)
            if not state["probe_ok"]:
                sys.stderr.write("cannot migrate — the secret store is not ready:\n")
                for rec in _secrets_recommendations(state):
                    sys.stderr.write(f"  - {rec}\n")
                sys.stderr.write("run `tg-notes secrets doctor` for the full diagnosis.\n")
                return 1
            secrets.migrate_to_keyring(cfg)
        elif target == "file":
            secrets.migrate_to_file(cfg)
    except (ValueError, RuntimeError) as exc:
        sys.stderr.write(f"migration failed: {exc}\n")
        return 1
    config.save(cfg)
    print(json.dumps({"backend": cfg.secrets_backend or "file", "migrated": True}))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tg-notes",
        description="Notes to a private Telegram group, published under your own account.",
    )
    parser.add_argument("--version", action="version", version=f"tg-notes {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>", required=True)

    # login (TGN-2)
    p_login = sub.add_parser("login", help="one-time interactive Telegram login")
    p_login.set_defaults(func=_login)

    # whoami (TGN-2)
    p_whoami = sub.add_parser("whoami", help="print the logged-in account identity")
    p_whoami.set_defaults(func=_whoami)

    # setup (TGN-3)
    p_setup = sub.add_parser("setup", help="create or attach the storage group")
    p_setup.add_argument(
        "--notebook",
        default="daily",
        help="name of the default notebook topic to ensure (default: daily)",
    )
    p_setup.set_defaults(func=_setup)

    # note add (TGN-4)
    p_note = sub.add_parser("note", help="work with notes")
    note_sub = p_note.add_subparsers(dest="subcommand", metavar="<subcommand>", required=True)
    p_note_add = note_sub.add_parser(
        "add", help="append a note (text, or a media --file) to a notebook"
    )
    p_note_add.add_argument("--notebook", default="daily", help="target notebook topic")
    p_note_add.add_argument(
        "--text-file",
        default=None,
        help="file with the note text (use - for stdin); omit when using --file",
    )
    p_note_add.add_argument(
        "--file",
        default=None,
        metavar="PATH",
        help="upload a media file (photo/video/audio/document) as the note instead of text",
    )
    p_note_add.add_argument(
        "--caption",
        default=None,
        help="caption for --file media (the note's searchable text)",
    )
    p_note_add.add_argument(
        "--hashtag",
        action="append",
        metavar="TAG",
        help="append a #hashtag to the note/caption (repeatable)",
    )
    p_note_add.set_defaults(func=_note_add)

    # notes list (TGN-5)
    p_notes = sub.add_parser("notes", help="query notes")
    notes_sub = p_notes.add_subparsers(dest="subcommand", metavar="<subcommand>", required=True)
    p_notes_list = notes_sub.add_parser("list", help="list raw notes from a notebook")
    p_notes_list.add_argument(
        "--notebook",
        default=None,
        help="source notebook topic (omit to pick interactively; else defaults to daily)",
    )
    p_notes_list.add_argument(
        "--since",
        help="lower time bound: today | HH:MM | YYYY-MM-DD | ISO datetime (local if naive)",
    )
    p_notes_list.set_defaults(func=_notes_list)

    # contacts (TGN-6)
    p_contacts = sub.add_parser("contacts", help="address book")
    contacts_sub = p_contacts.add_subparsers(dest="subcommand", metavar="<subcommand>", required=True)
    contacts_sub.add_parser("list", help="list contacts").set_defaults(func=_contacts_list)
    p_c_set = contacts_sub.add_parser("set", help="add or update a contact")
    p_c_set.add_argument("key", help="contact key")
    p_c_set.add_argument("--chat-id", dest="chat_id", help="-100… | @username | me")
    p_c_set.add_argument("--name", help="human name (never sent)")
    p_c_set.add_argument("--topic-id", dest="topic_id", type=int, help="forum topic id")
    p_c_set.add_argument("--mention", help="@username to mention when posting")
    p_c_set.add_argument("--style", help="prompt: how to compile notes for this recipient")
    p_c_set.set_defaults(func=_contacts_set)
    p_c_rm = contacts_sub.add_parser("remove", help="remove a contact")
    p_c_rm.add_argument(
        "key", nargs="?", default=None, help="contact key (omit to pick interactively)"
    )
    p_c_rm.set_defaults(func=_contacts_remove)

    # send (TGN-7)
    p_send = sub.add_parser("send", help="publish a compiled note to a contact")
    p_send.add_argument(
        "--contact",
        required=False,
        default=None,
        help="contact key from the address book (omit to pick interactively)",
    )
    p_send.add_argument(
        "--text-file", required=True, help="file with the compiled text (use - for stdin)"
    )
    p_send.add_argument(
        "--dry-run",
        action="store_true",
        help="compose and print what would be sent, without sending",
    )
    p_send.set_defaults(func=_send)

    # notebooks list (TGN-8)
    p_nb = sub.add_parser("notebooks", help="notebooks")
    nb_sub = p_nb.add_subparsers(dest="subcommand", metavar="<subcommand>", required=True)
    nb_sub.add_parser("list", help="list notebook topics").set_defaults(func=_notebooks_list)

    # secrets (TGN-18)
    p_secrets = sub.add_parser("secrets", help="secrets backend (file / keyring)")
    secrets_sub = p_secrets.add_subparsers(dest="subcommand", metavar="<subcommand>", required=True)
    secrets_sub.add_parser(
        "status", help="show the active secrets backend and what's available"
    ).set_defaults(func=_secrets_status)
    p_sec_doc = secrets_sub.add_parser(
        "doctor", help="diagnose the secret store and recommend setup/migration steps"
    )
    p_sec_doc.add_argument("--json", action="store_true", help="machine-readable output")
    p_sec_doc.set_defaults(func=_secrets_doctor)
    p_sec_mig = secrets_sub.add_parser("migrate", help="move secrets between backends")
    p_sec_mig.add_argument(
        "--to",
        choices=["file", "keyring"],
        default=None,
        help="target backend (omit to pick interactively)",
    )
    p_sec_mig.set_defaults(func=_secrets_migrate)

    return parser


def main(argv: list[str] | None = None) -> int:
    # Before argparse or any secrets access: on Linux + keyring backend, re-exec through a
    # named launcher so the vault confirmation prompt identifies the app as tg-notes (a
    # no-op everywhere else; see tg_notes/relaunch.py).
    from .relaunch import relaunch_as_named

    relaunch_as_named()
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
