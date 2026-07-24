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

`login` and `whoami` are implemented (TGN-2); the remaining command bodies land in
their own tasks and are stubs for now.
"""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__, config, telegram


def _todo(task: str):
    """Placeholder handler for a not-yet-implemented command."""

    def handler(args: argparse.Namespace) -> int:
        sys.stderr.write(f"not implemented yet ({task})\n")
        return 2

    return handler


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
    p_setup.set_defaults(func=_todo("TGN-3"))

    # note add (TGN-4)
    p_note = sub.add_parser("note", help="work with notes")
    note_sub = p_note.add_subparsers(dest="subcommand", metavar="<subcommand>", required=True)
    p_note_add = note_sub.add_parser("add", help="append a note to a notebook")
    p_note_add.add_argument("--notebook", default="daily", help="target notebook topic")
    p_note_add.add_argument("--text-file", required=True, help="file with the note text")
    p_note_add.set_defaults(func=_todo("TGN-4"))

    # notes list (TGN-5)
    p_notes = sub.add_parser("notes", help="query notes")
    notes_sub = p_notes.add_subparsers(dest="subcommand", metavar="<subcommand>", required=True)
    p_notes_list = notes_sub.add_parser("list", help="list raw notes from a notebook")
    p_notes_list.add_argument("--notebook", default="daily", help="source notebook topic")
    p_notes_list.add_argument("--since", help="lower time bound (e.g. YYYY-MM-DD or 00:00)")
    p_notes_list.set_defaults(func=_todo("TGN-5"))

    # contacts (TGN-6)
    p_contacts = sub.add_parser("contacts", help="address book")
    contacts_sub = p_contacts.add_subparsers(dest="subcommand", metavar="<subcommand>", required=True)
    contacts_sub.add_parser("list", help="list contacts").set_defaults(func=_todo("TGN-6"))
    p_c_set = contacts_sub.add_parser("set", help="add or update a contact")
    p_c_set.add_argument("key", help="contact key")
    p_c_set.set_defaults(func=_todo("TGN-6"))
    p_c_rm = contacts_sub.add_parser("remove", help="remove a contact")
    p_c_rm.add_argument("key", help="contact key")
    p_c_rm.set_defaults(func=_todo("TGN-6"))

    # send (TGN-7)
    p_send = sub.add_parser("send", help="publish a compiled note to a contact")
    p_send.add_argument("--contact", required=True, help="contact key from the address book")
    p_send.add_argument("--text-file", required=True, help="file with the compiled text")
    p_send.set_defaults(func=_todo("TGN-7"))

    # notebooks list (TGN-8)
    p_nb = sub.add_parser("notebooks", help="notebooks")
    nb_sub = p_nb.add_subparsers(dest="subcommand", metavar="<subcommand>", required=True)
    nb_sub.add_parser("list", help="list notebook topics").set_defaults(func=_todo("TGN-8"))

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
