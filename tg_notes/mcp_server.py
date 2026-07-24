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
import os
import sys

# `transcribe` is aliased to `_transcribe` — it is a parameter name on note_add_file below.
from . import config, telegram
from . import transcribe as _transcribe
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


async def note_add_file(
    file: str,
    notebook: str = "daily",
    caption: str | None = None,
    transcribe: bool = True,
    hashtags: list[str] | None = None,
) -> dict:
    """Upload a LOCAL file as a note into a notebook topic (created on demand).

    ``file`` is a path on this machine — a photo, video, audio, or document — stored as
    native Telegram media (the kind is auto-detected). For an audio file with no ``caption``
    the audio is auto-transcribed into the caption (best-effort, local whisper), mirroring the
    CLI; pass your own ``caption`` (e.g. a description of an image) to skip transcription, or
    set ``transcribe=False`` to never transcribe. Returns the posted note (with ``media_type``
    and ``caption``).
    """
    if not os.path.exists(file):
        raise FileNotFoundError(f"file not found: {file}")
    cfg = config.load()
    # Best-effort audio transcription, mirroring the CLI handler: only when enabled, no
    # caption was given, the file is audio, and a local engine is available. A missing/failing
    # engine never aborts the upload — it just proceeds with no caption.
    if (
        transcribe
        and caption is None
        and _transcribe.is_audio(file)
        and _transcribe.available_transcriber(cfg) is not None
    ):
        try:
            text = await asyncio.to_thread(_transcribe.transcribe, file, cfg)
            caption = text or None
        except (_transcribe.TranscriptionUnavailable, _transcribe.TranscriptionError) as exc:
            sys.stderr.write(
                f"tg-notes: audio transcription failed ({exc}) — "
                "uploading the file without a caption\n"
            )
            caption = None
    return await asyncio.to_thread(
        telegram.note_add_file,
        cfg,
        notebook=notebook,
        file_path=file,
        caption=caption,
        hashtags=hashtags,
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
TOOLS = (note_add, note_add_file, notes_list, contacts_list, send)


def build_server(*, host: str | None = None, port: int | None = None):
    """Construct the FastMCP server with the tools registered (needs the ``mcp`` extra).

    ``host``/``port`` bind the remote streamable-HTTP transport (TGN-24); they are
    ignored by the default stdio transport.
    """
    from mcp.server.fastmcp import FastMCP  # optional dep — imported only when running

    kwargs: dict[str, object] = {"instructions": INSTRUCTIONS}
    if host is not None:
        kwargs["host"] = host
    if port is not None:
        kwargs["port"] = port
    server = FastMCP(SERVER_NAME, **kwargs)
    for tool in TOOLS:
        server.tool()(tool)
    return server


_MCP_MISSING = (
    "the MCP server needs the 'mcp' extra — install with "
    '`pipx install "tg-notes[mcp]"`\n'
)


def main() -> int:
    """Console entrypoint: run the tg-notes MCP server over stdio."""
    try:
        server = build_server()
    except ImportError:
        sys.stderr.write(_MCP_MISSING)
        return 1
    server.run()  # stdio transport by default
    return 0


def run_http() -> int:
    """Console entrypoint: serve the MCP server over remote streamable-HTTP (TGN-24).

    Host/port come from ``TG_NOTES_MCP_HOST`` (default ``0.0.0.0``) and
    ``TG_NOTES_MCP_PORT`` (default ``8000``) so it can run as a networked service
    (e.g. a Kubernetes Deployment) rather than a local stdio subprocess.
    """
    try:
        server = build_server(
            host=os.environ.get("TG_NOTES_MCP_HOST", "0.0.0.0"),
            port=int(os.environ.get("TG_NOTES_MCP_PORT", "8000")),
        )
    except ImportError:
        sys.stderr.write(_MCP_MISSING)
        return 1
    server.run(transport="streamable-http")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
