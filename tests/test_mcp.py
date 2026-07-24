"""Tests for the local MCP server (TGN-17).

The tool functions are tested with the core (`telegram`/`config`) mocked. Server assembly
is tested against the real `mcp` package when present (installed via the `dev`/`mcp` extra).
"""
from __future__ import annotations

import asyncio

import pytest

from tg_notes import mcp_server, transcribe


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


def test_notes_list_tool_passes_media_through(mocker) -> None:
    # The notes_list tool returns telegram.notes_list output verbatim, including the
    # additive `media` key (the type, or None) that media notes carry.
    mocker.patch("tg_notes.mcp_server.config.load", return_value=object())
    notes = [
        {"message_id": 6, "date": "d", "text": "plain", "media": None},
        {"message_id": 7, "date": "d", "text": "a picture", "media": "photo"},
    ]
    mocker.patch("tg_notes.mcp_server.telegram.notes_list", return_value=notes)

    result = asyncio.run(mcp_server.notes_list(notebook="daily"))

    assert result == notes  # pass-through, media key survives
    assert [n["media"] for n in result] == [None, "photo"]


# --- note_add_file tool: media upload + best-effort audio transcription (mirrors CLI) --


def _audio(tmp_path):
    f = tmp_path / "voice.ogg"
    f.write_bytes(b"x")
    return str(f)


def test_note_add_file_tool_transcribes_audio(mocker, tmp_path) -> None:
    f = _audio(tmp_path)
    cfg = object()
    mocker.patch("tg_notes.mcp_server.config.load", return_value=cfg)
    mocker.patch(
        "tg_notes.mcp_server._transcribe.available_transcriber", return_value="faster-whisper"
    )
    tr = mocker.patch("tg_notes.mcp_server._transcribe.transcribe", return_value="hello world")
    add = mocker.patch(
        "tg_notes.mcp_server.telegram.note_add_file", return_value={"media_type": "voice"}
    )

    result = asyncio.run(mcp_server.note_add_file(f, notebook="daily"))

    tr.assert_called_once_with(f, cfg)
    add.assert_called_once_with(
        cfg, notebook="daily", file_path=f, caption="hello world", hashtags=None
    )
    assert result == {"media_type": "voice"}


def test_note_add_file_tool_explicit_caption_skips_transcription(mocker, tmp_path) -> None:
    f = _audio(tmp_path)
    cfg = object()
    mocker.patch("tg_notes.mcp_server.config.load", return_value=cfg)
    avail = mocker.patch("tg_notes.mcp_server._transcribe.available_transcriber")
    tr = mocker.patch("tg_notes.mcp_server._transcribe.transcribe")
    add = mocker.patch(
        "tg_notes.mcp_server.telegram.note_add_file", return_value={"media_type": "voice"}
    )

    asyncio.run(mcp_server.note_add_file(f, notebook="daily", caption="a photo of X"))

    tr.assert_not_called()
    avail.assert_not_called()  # a given caption short-circuits before any detection
    add.assert_called_once_with(
        cfg, notebook="daily", file_path=f, caption="a photo of X", hashtags=None
    )


def test_note_add_file_tool_transcribe_false_skips(mocker, tmp_path) -> None:
    f = _audio(tmp_path)
    cfg = object()
    mocker.patch("tg_notes.mcp_server.config.load", return_value=cfg)
    avail = mocker.patch("tg_notes.mcp_server._transcribe.available_transcriber")
    tr = mocker.patch("tg_notes.mcp_server._transcribe.transcribe")
    add = mocker.patch(
        "tg_notes.mcp_server.telegram.note_add_file", return_value={"media_type": "voice"}
    )

    asyncio.run(mcp_server.note_add_file(f, notebook="daily", transcribe=False))

    tr.assert_not_called()
    avail.assert_not_called()  # transcribe=False short-circuits before detection
    add.assert_called_once_with(
        cfg, notebook="daily", file_path=f, caption=None, hashtags=None
    )


def test_note_add_file_tool_unavailable_still_uploads(mocker, tmp_path) -> None:
    f = _audio(tmp_path)
    cfg = object()
    mocker.patch("tg_notes.mcp_server.config.load", return_value=cfg)
    mocker.patch(
        "tg_notes.mcp_server._transcribe.available_transcriber", return_value="faster-whisper"
    )
    mocker.patch(
        "tg_notes.mcp_server._transcribe.transcribe",
        side_effect=transcribe.TranscriptionUnavailable("no engine"),
    )
    add = mocker.patch(
        "tg_notes.mcp_server.telegram.note_add_file", return_value={"media_type": "voice"}
    )

    asyncio.run(mcp_server.note_add_file(f, notebook="daily"))

    add.assert_called_once_with(
        cfg, notebook="daily", file_path=f, caption=None, hashtags=None
    )  # best-effort: the upload still happens, without a caption


def test_note_add_file_tool_transcription_error_still_uploads(mocker, tmp_path) -> None:
    f = _audio(tmp_path)
    cfg = object()
    mocker.patch("tg_notes.mcp_server.config.load", return_value=cfg)
    mocker.patch(
        "tg_notes.mcp_server._transcribe.available_transcriber", return_value="faster-whisper"
    )
    mocker.patch(
        "tg_notes.mcp_server._transcribe.transcribe",
        side_effect=transcribe.TranscriptionError("bad audio"),
    )
    add = mocker.patch(
        "tg_notes.mcp_server.telegram.note_add_file", return_value={"media_type": "voice"}
    )

    asyncio.run(mcp_server.note_add_file(f, notebook="daily", hashtags=["v"]))

    add.assert_called_once_with(
        cfg, notebook="daily", file_path=f, caption=None, hashtags=["v"]
    )


def test_note_add_file_tool_missing_file_errors(mocker, tmp_path) -> None:
    add = mocker.patch("tg_notes.mcp_server.telegram.note_add_file")

    with pytest.raises(FileNotFoundError):
        asyncio.run(mcp_server.note_add_file(str(tmp_path / "nope.png")))

    add.assert_not_called()  # fail fast, before any core call


def test_note_add_file_registered_in_tools() -> None:
    assert mcp_server.note_add_file in mcp_server.TOOLS


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

    assert {t.name for t in tools} == {
        "note_add",
        "note_add_file",
        "notes_list",
        "contacts_list",
        "send",
    }
    assert all(t.description for t in tools)  # descriptions come from the docstrings


def test_main_reports_when_mcp_missing(mocker, capsys) -> None:
    mocker.patch("tg_notes.mcp_server.build_server", side_effect=ImportError("no mcp"))

    rc = mcp_server.main()

    assert rc == 1
    assert "tg-notes[mcp]" in capsys.readouterr().err


def test_build_server_accepts_host_port() -> None:
    """TGN-24: build_server can bind host/port for the streamable-HTTP transport."""
    pytest.importorskip("mcp")

    server = mcp_server.build_server(host="0.0.0.0", port=1234)

    assert server.settings.host == "0.0.0.0"
    assert server.settings.port == 1234


def test_streamable_http_app_builds() -> None:
    """TGN-24: the server can produce a remote streamable-HTTP ASGI app."""
    pytest.importorskip("mcp")

    app = mcp_server.build_server(host="0.0.0.0", port=1234).streamable_http_app()

    assert app is not None


def test_run_http_is_callable() -> None:
    """TGN-24: the tg-notes-mcp-http console entrypoint exists."""
    assert callable(mcp_server.run_http)


def test_run_http_reports_when_mcp_missing(mocker, capsys) -> None:
    mocker.patch("tg_notes.mcp_server.build_server", side_effect=ImportError("no mcp"))

    rc = mcp_server.run_http()

    assert rc == 1
    assert "tg-notes[mcp]" in capsys.readouterr().err
