#!/usr/bin/env python3
"""Cleanup for tg-notes live/integration test data.

The gated live tests post transient notes/media into a **dedicated test group** (never the
real store). Left alone, those accumulate across every local and CI run. This helper purges
them — and can tear the whole test group down — so the store stays tidy.

Hard safety: every subcommand refuses to run unless a store is configured **and** it is not
the real note store (``REAL_STORE_ID``). The store is read from ``TG_NOTES_CONFIG_DIR`` (the
sandbox / CI throwaway config, file backend), exactly like the tests it cleans up after.

Subcommands::

    cleanup_live.py purge [--notebook N ...]   # delete every note in the test notebooks
                                               # (default: citest, mediatest)
    cleanup_live.py group                      # delete the ENTIRE dedicated test group

Typical use — after the gated live suite, against the same sandbox::

    TG_NOTES_CONFIG_DIR=~/.config/tg-notes-sandbox python scripts/cleanup_live.py purge

In CI the ``live-functional`` job runs ``purge`` as an always-run step so each run leaves the
dedicated group clean.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:  # importable even when tg-notes is not pip-installed
    sys.path.insert(0, str(REPO_ROOT))

from tg_notes import config, telegram
from tg_notes.config import Config

#: The maintainer's real note store (see CLAUDE.md) — cleanup must NEVER touch it.
REAL_STORE_ID = -1004432534270
#: Notebooks the gated live tests write into; purged by default.
DEFAULT_TEST_NOTEBOOKS = ["citest", "mediatest"]
#: Telegram lets you delete at most this many messages per request.
_DELETE_BATCH = 100


class CleanupError(RuntimeError):
    """A cleanup step refused to run or failed, with a message meant for the user."""


def _assert_safe_store(cfg: Config) -> None:
    """Guard: a store must be configured and must not be the real note store."""
    if not cfg.storage_group_id:
        raise CleanupError("no storage group configured — nothing to clean up")
    if cfg.storage_group_id == REAL_STORE_ID:
        raise CleanupError(
            f"refusing to clean the REAL store ({REAL_STORE_ID}) — point "
            "TG_NOTES_CONFIG_DIR at a dedicated test sandbox"
        )


def purge(cfg: Config, notebooks: list[str]) -> int:
    """Delete every note in ``notebooks`` (keeping each topic's opener). Returns the count."""
    client = telegram.connect_authorized(cfg)
    try:
        entity = telegram._resolve_store(client, cfg)
        topics = telegram._list_topics(client, entity)
        removed = 0
        for name in notebooks:
            topic_id = topics.get(name)
            if topic_id is None:
                continue  # notebook was never created — nothing to purge
            # The topic-opening service message has id == topic_id; never delete it.
            ids = [
                m.id
                for m in client.iter_messages(entity, reply_to=topic_id)
                if m.id != topic_id
            ]
            for start in range(0, len(ids), _DELETE_BATCH):
                client.delete_messages(entity, ids[start : start + _DELETE_BATCH])
            removed += len(ids)
        return removed
    finally:
        client.disconnect()


def delete_group(cfg: Config) -> None:
    """Delete the entire dedicated test group (full teardown)."""
    from telethon.tl.functions.channels import DeleteChannelRequest

    client = telegram.connect_authorized(cfg)
    try:
        entity = telegram._resolve_store(client, cfg)
        client(DeleteChannelRequest(entity))
    finally:
        client.disconnect()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cleanup_live.py",
        description="Purge or tear down tg-notes live-test data (dedicated store only).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p_purge = sub.add_parser("purge", help="delete every note in the test notebooks")
    p_purge.add_argument(
        "--notebook",
        action="append",
        metavar="NAME",
        help=f"notebook to purge (repeatable; default: {', '.join(DEFAULT_TEST_NOTEBOOKS)})",
    )
    sub.add_parser("group", help="delete the ENTIRE dedicated test group")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = config.load()
    try:
        _assert_safe_store(cfg)
    except CleanupError as exc:
        sys.stderr.write(f"cleanup: error: {exc}\n")
        return 1

    if args.command == "purge":
        notebooks = args.notebook or DEFAULT_TEST_NOTEBOOKS
        removed = purge(cfg, notebooks)
        print(f"purged {removed} note(s) from {', '.join(notebooks)} in {cfg.storage_group_id}")
        return 0
    if args.command == "group":
        delete_group(cfg)
        print(f"deleted dedicated test group {cfg.storage_group_id}")
        return 0
    return 2  # unreachable: subparser is required


if __name__ == "__main__":
    raise SystemExit(main())
