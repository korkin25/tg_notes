"""Tests for the local MCP server (TGN-17).

The tool functions are tested with the core (`telegram`/`config`) mocked. Server assembly
is tested against the real `mcp` package when present (installed via the `dev`/`mcp` extra).
"""
from __future__ import annotations

import asyncio

import pytest

from tg_notes import mcp_server


def test_note_add_tool_calls_core(mocker) -> None:
    cfg = object()
    mocker.patch("tg_notes.mcp_server.config.load", return_value=cfg)
    add = mocker.patch("tg_notes.mcp_server.telegram.note_add", return_value={"message_id": 1})

    result = asyncio.run(mcp_server.note_add("hello", notebook="daily", hashtags=["x"]))

    add.assert_called_once_with(cfg, notebook="daily", text="hello", hashtags=["x"])
    assert result == {"message_id": 1}


def test_notes_list_tool_parses_since(mocker) -> None:
    cfg = object()
    mocker.patch("tg_notes.mcp_server.config.load", return_value=cfg)
    lst = mocker.patch("tg_notes.mcp_server.telegram.notes_list", return_value=[])

    asyncio.run(mcp_server.notes_list(notebook="daily", since="2026-07-24"))

    args, kwargs = lst.call_args
    assert args[0] is cfg
    assert kwargs["notebook"] == "daily"
    since = kwargs["since"]
    assert (since.year, since.month, since.day) == (2026, 7, 24)
    assert since.tzinfo is not None


def test_notes_list_tool_without_since_passes_none(mocker) -> None:
    mocker.patch("tg_notes.mcp_server.config.load", return_value=object())
    lst = mocker.patch("tg_notes.mcp_server.telegram.notes_list", return_value=[])

    asyncio.run(mcp_server.notes_list())

    assert lst.call_args.kwargs["since"] is None


def test_contacts_list_tool_calls_core(mocker) -> None:
    cfg = object()
    mocker.patch("tg_notes.mcp_server.config.load", return_value=cfg)
    lst = mocker.patch("tg_notes.mcp_server.telegram.contacts_list", return_value=[{"key": "a"}])

    assert asyncio.run(mcp_server.contacts_list()) == [{"key": "a"}]
    lst.assert_called_once_with(cfg)


def test_send_tool_passes_dry_run(mocker) -> None:
    cfg = object()
    mocker.patch("tg_notes.mcp_server.config.load", return_value=cfg)
    snd = mocker.patch("tg_notes.mcp_server.telegram.send", return_value={"sent": False})

    asyncio.run(mcp_server.send("boss", "hi", dry_run=True))

    snd.assert_called_once_with(cfg, "boss", "hi", dry_run=True)


def test_build_server_registers_all_tools() -> None:
    pytest.importorskip("mcp")
    import asyncio

    server = mcp_server.build_server()
    tools = asyncio.run(server.list_tools())

    assert {t.name for t in tools} == {"note_add", "notes_list", "contacts_list", "send"}
    assert all(t.description for t in tools)  # descriptions come from the docstrings


def test_main_reports_when_mcp_missing(mocker, capsys) -> None:
    mocker.patch("tg_notes.mcp_server.build_server", side_effect=ImportError("no mcp"))

    rc = mcp_server.main()

    assert rc == 1
    assert "tg-notes[mcp]" in capsys.readouterr().err
