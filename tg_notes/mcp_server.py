"""Local stdio MCP server for tg-notes (TGN-17).

A second frontend over the same core as the CLI: it exposes the note / notes / contacts /
send operations as MCP tools, so agent hosts that cannot shell out (Claude Desktop,
ChatGPT desktop, …) can drive tg-notes. **stdio only** — the Telethon session and secrets
stay on the local machine; nothing is hosted.

The tool functions below are importable **without** the optional ``mcp`` dependency (so
they stay unit-testable); only :func:`build_server` / :func:`main` need it
(``pipx install "tg-notes[mcp]"``).

The core (``telegram``) is synchronous (Telethon via ``telethon.sync``), which only works
outside a running event loop. MCP tools run *inside* one, so each tool offloads the
blocking core call to a worker thread via :func:`asyncio.to_thread`.
"""
from __future__ import annotations

import asyncio
import sys

from . import config, telegram
from .cli import _parse_since

SERVER_NAME = "tg-notes"
INSTRUCTIONS = (
    "Notes stored in a private Telegram group, published under the user's own account. "
    "note_add/notes_list/contacts_list read and write the store; send publishes to a "
    "contact AS THE USER — prefer dry_run to preview, and confirm with the user first."
)


async def note_add(
    text: str, notebook: str = "daily", hashtags: list[str] | None = None
) -> dict:
    """Append a note to a notebook topic (created on demand). Returns the posted note."""
    cfg = config.load()
    return await asyncio.to_thread(
        telegram.note_add, cfg, notebook=notebook, text=text, hashtags=hashtags
    )


async def notes_list(notebook: str = "daily", since: str | None = None) -> list[dict]:
    """List a notebook's raw notes, oldest first.

    ``since`` optionally bounds by time: ``today`` | ``HH:MM`` | ``YYYY-MM-DD`` | ISO
    datetime (local when it carries no offset).
    """
    cfg = config.load()
    bound = _parse_since(since) if since else None
    return await asyncio.to_thread(telegram.notes_list, cfg, notebook=notebook, since=bound)


async def contacts_list() -> list[dict]:
    """List the address book (one entry per contact: key, name, chat_id, topic_id, style)."""
    return await asyncio.to_thread(telegram.contacts_list, config.load())


async def send(contact: str, text: str, dry_run: bool = False) -> dict:
    """Publish text to a contact's chat AS THE USER (userbot).

    Set ``dry_run`` to compose and return the outgoing message without sending. A real send
    goes out under the user's own account — confirm with the user before calling with
    ``dry_run=False``.
    """
    return await asyncio.to_thread(
        telegram.send, config.load(), contact, text, dry_run=dry_run
    )


#: The tools exposed by the server, in registration order.
TOOLS = (note_add, notes_list, contacts_list, send)


def build_server():
    """Construct the FastMCP server with the tools registered (needs the ``mcp`` extra)."""
    from mcp.server.fastmcp import FastMCP  # optional dep — imported only when running

    server = FastMCP(SERVER_NAME, instructions=INSTRUCTIONS)
    for tool in TOOLS:
        server.tool()(tool)
    return server


def main() -> int:
    """Console entrypoint: run the tg-notes MCP server over stdio."""
    try:
        server = build_server()
    except ImportError:
        sys.stderr.write(
            "the MCP server needs the 'mcp' extra — install with "
            '`pipx install "tg-notes[mcp]"`\n'
        )
        return 1
    server.run()  # stdio transport by default
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
