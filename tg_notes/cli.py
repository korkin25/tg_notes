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

from . import __version__, config, telegram


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


def _note_add(args: argparse.Namespace) -> int:
    """Append a note to a notebook topic (TGN-4)."""
    cfg = config.load()
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
    try:
        notes = telegram.notes_list(cfg, notebook=args.notebook, since=since)
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
    try:
        result = telegram.contacts_remove(cfg, args.key)
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
    try:
        text = _read_text_arg(args.text_file)
    except OSError as exc:
        sys.stderr.write(f"cannot read text from {args.text_file}: {exc}\n")
        return 1
    try:
        result = telegram.send(cfg, args.contact, text, dry_run=args.dry_run)
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
    p_note_add = note_sub.add_parser("add", help="append a note to a notebook")
    p_note_add.add_argument("--notebook", default="daily", help="target notebook topic")
    p_note_add.add_argument(
        "--text-file", required=True, help="file with the note text (use - for stdin)"
    )
    p_note_add.add_argument(
        "--hashtag",
        action="append",
        metavar="TAG",
        help="append a #hashtag to the note (repeatable)",
    )
    p_note_add.set_defaults(func=_note_add)

    # notes list (TGN-5)
    p_notes = sub.add_parser("notes", help="query notes")
    notes_sub = p_notes.add_subparsers(dest="subcommand", metavar="<subcommand>", required=True)
    p_notes_list = notes_sub.add_parser("list", help="list raw notes from a notebook")
    p_notes_list.add_argument("--notebook", default="daily", help="source notebook topic")
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
    p_c_rm.add_argument("key", help="contact key")
    p_c_rm.set_defaults(func=_contacts_remove)

    # send (TGN-7)
    p_send = sub.add_parser("send", help="publish a compiled note to a contact")
    p_send.add_argument("--contact", required=True, help="contact key from the address book")
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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
