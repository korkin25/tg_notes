"""Tests for media notes — uploading files into a notebook topic (media Phase 1).

Telethon is fully mocked (offline). ``note_add_file`` is exercised against a mocked client
and a patched ``_ensure_topics``; media-type detection is driven by fake message objects
whose Telethon media properties are set truthy/falsey. NEVER hits the network.
"""
from __future__ import annotations

import datetime
import unittest.mock as um

import pytest

from tg_notes import cli, telegram
from tg_notes.config import Config

FIXED_DATE = datetime.datetime(2026, 7, 24, 12, 0, tzinfo=datetime.UTC)

#: The Telethon message properties `note_add_file` inspects to classify media.
_MEDIA_ATTRS = ("photo", "voice", "audio", "video", "video_note", "gif", "document")


def configured(**over) -> Config:
    base = {
        "api_id": 42,
        "api_hash": "cafe",
        "session_path": "/tmp/x.session",
        "storage_group_id": -1004432534270,
    }
    base.update(over)
    return Config(**base)


def _msg(mid: int = 100, date=FIXED_DATE, text: str = "caption", **media):
    """Fake Telethon message: every media property is None unless named in ``**media``."""
    attrs = {name: None for name in _MEDIA_ATTRS}
    attrs.update(media)
    return um.Mock(id=mid, date=date, text=text, **attrs)


def _authorized_client(mocker, message):
    fake_cls = mocker.patch("tg_notes.telegram.TelegramClient")
    instance = fake_cls.return_value
    instance.is_user_authorized.return_value = True
    instance.send_file.return_value = message
    return instance


# --- note_add_file(): the send_file call + returned metadata ----------------------


def test_note_add_file_sends_file_into_topic(mocker, tmp_path) -> None:
    f = tmp_path / "shot.png"
    f.write_bytes(b"\x89PNG")
    instance = _authorized_client(mocker, _msg(mid=101, photo=object()))
    entity = instance.get_entity.return_value
    ensure = mocker.patch("tg_notes.telegram._ensure_topics", return_value={"daily": 5})

    result = telegram.note_add_file(
        configured(), notebook="daily", file_path=str(f), caption="hi"
    )

    instance.get_entity.assert_called_once_with(-1004432534270)
    ensure.assert_called_once_with(instance, entity, ["daily"])
    # Telethon auto-detects the media kind; caption + reply_to (topic) are ours.
    instance.send_file.assert_called_once_with(entity, str(f), caption="hi", reply_to=5)
    assert result == {
        "notebook": "daily",
        "topic_id": 5,
        "message_id": 101,
        "date": FIXED_DATE.isoformat(),
        "media_type": "photo",
        "caption": "hi",
    }
    instance.disconnect.assert_called_once_with()


def test_note_add_file_appends_hashtags_to_caption(mocker, tmp_path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("x", encoding="utf-8")
    instance = _authorized_client(mocker, _msg(document=object()))
    mocker.patch("tg_notes.telegram._ensure_topics", return_value={"daily": 5})

    result = telegram.note_add_file(
        configured(),
        notebook="daily",
        file_path=str(f),
        caption="body",
        hashtags=["foo", "#bar"],
    )

    assert instance.send_file.call_args.kwargs["caption"] == "body\n\n#foo #bar"
    assert result["caption"] == "body\n\n#foo #bar"
    assert result["media_type"] == "document"


def test_note_add_file_without_caption_sends_empty_string(mocker, tmp_path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("x", encoding="utf-8")
    instance = _authorized_client(mocker, _msg(document=object()))
    mocker.patch("tg_notes.telegram._ensure_topics", return_value={"daily": 5})

    result = telegram.note_add_file(configured(), notebook="daily", file_path=str(f))

    assert instance.send_file.call_args.kwargs["caption"] == ""
    assert result["caption"] == ""


# --- note_add_file(): media-type detection ---------------------------------------


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        ({"photo": object()}, "photo"),
        ({"voice": object()}, "voice"),
        ({"audio": object()}, "audio"),
        ({"video": object()}, "video"),
        ({"video_note": object()}, "video"),
        ({"gif": object()}, "gif"),
        ({"document": object()}, "document"),
        ({}, "document"),  # no recognizable media → document fallback
        # precedence when Telethon exposes overlapping properties:
        ({"voice": object(), "audio": object(), "document": object()}, "voice"),
        ({"video": object(), "document": object()}, "video"),
        ({"audio": object(), "document": object()}, "audio"),
    ],
)
def test_note_add_file_media_type_detection(mocker, tmp_path, flags, expected) -> None:
    f = tmp_path / "m.bin"
    f.write_bytes(b"x")
    _authorized_client(mocker, _msg(**flags))
    mocker.patch("tg_notes.telegram._ensure_topics", return_value={"daily": 5})

    result = telegram.note_add_file(configured(), notebook="daily", file_path=str(f))

    assert result["media_type"] == expected


# --- note_add_file(): validation & error paths -----------------------------------


def test_note_add_file_missing_file_raises_before_connect(mocker, tmp_path) -> None:
    fake_cls = mocker.patch("tg_notes.telegram.TelegramClient")

    with pytest.raises(FileNotFoundError):
        telegram.note_add_file(
            configured(), notebook="daily", file_path=str(tmp_path / "nope.png")
        )

    fake_cls.assert_not_called()  # fail fast, before any connection or send_file


def test_note_add_file_directory_raises_value_error(mocker, tmp_path) -> None:
    d = tmp_path / "adir"
    d.mkdir()
    fake_cls = mocker.patch("tg_notes.telegram.TelegramClient")

    with pytest.raises(ValueError):
        telegram.note_add_file(configured(), notebook="daily", file_path=str(d))

    fake_cls.assert_not_called()


def test_note_add_file_raises_when_not_set_up(mocker, tmp_path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("x", encoding="utf-8")
    fake_cls = mocker.patch("tg_notes.telegram.TelegramClient")

    with pytest.raises(telegram.NotSetUpError):
        telegram.note_add_file(
            configured(storage_group_id=None), notebook="daily", file_path=str(f)
        )

    fake_cls.assert_not_called()


def test_note_add_file_group_unresolvable_raises_not_set_up(mocker, tmp_path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("x", encoding="utf-8")
    instance = _authorized_client(mocker, _msg(document=object()))
    instance.get_entity.side_effect = ValueError("gone")

    with pytest.raises(telegram.NotSetUpError):
        telegram.note_add_file(configured(), notebook="daily", file_path=str(f))

    instance.disconnect.assert_called_once_with()


def test_note_add_file_disconnects_when_send_fails(mocker, tmp_path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("x", encoding="utf-8")
    instance = _authorized_client(mocker, _msg(document=object()))
    mocker.patch("tg_notes.telegram._ensure_topics", return_value={"daily": 5})
    instance.send_file.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError):
        telegram.note_add_file(configured(), notebook="daily", file_path=str(f))

    instance.disconnect.assert_called_once_with()


def test_note_add_file_propagates_not_authorized(mocker, tmp_path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("x", encoding="utf-8")
    fake_cls = mocker.patch("tg_notes.telegram.TelegramClient")
    fake_cls.return_value.is_user_authorized.return_value = False

    with pytest.raises(telegram.NotAuthorizedError):
        telegram.note_add_file(configured(), notebook="daily", file_path=str(f))


# --- notes_list(): media type + caption surfaced ---------------------------------


def _listing_client(mocker, messages):
    fake_cls = mocker.patch("tg_notes.telegram.TelegramClient")
    instance = fake_cls.return_value
    instance.is_user_authorized.return_value = True
    instance.iter_messages.return_value = messages
    return instance


def test_notes_list_surfaces_media_and_caption(mocker) -> None:
    text_msg = _msg(mid=6, text="plain note")  # all media None
    photo_msg = _msg(mid=7, text="a picture", photo=object())
    _listing_client(mocker, [photo_msg, text_msg])  # iter yields newest-first
    mocker.patch("tg_notes.telegram._list_topics", return_value={"daily": 5})

    result = telegram.notes_list(configured(), notebook="daily")

    assert result == [
        {"message_id": 6, "date": FIXED_DATE.isoformat(), "text": "plain note", "media": None},
        {"message_id": 7, "date": FIXED_DATE.isoformat(), "text": "a picture", "media": "photo"},
    ]


def test_notes_list_includes_media_note_without_caption(mocker) -> None:
    doc = _msg(mid=8, text="", document=object())  # media, empty caption
    _listing_client(mocker, [doc])
    mocker.patch("tg_notes.telegram._list_topics", return_value={"daily": 5})

    result = telegram.notes_list(configured(), notebook="daily")

    assert result == [
        {"message_id": 8, "date": FIXED_DATE.isoformat(), "text": "", "media": "document"}
    ]


def test_notes_list_still_skips_service_message(mocker) -> None:
    service = _msg(mid=5, text="")  # topic opener: no text, no media
    real = _msg(mid=6, text="real note")
    _listing_client(mocker, [service, real])
    mocker.patch("tg_notes.telegram._list_topics", return_value={"daily": 5})

    result = telegram.notes_list(configured(), notebook="daily")

    assert [n["message_id"] for n in result] == [6]


# --- CLI: `note add --file` vs `note add --text-file` routing ---------------------


def test_cli_note_add_file_routes_to_note_add_file(mocker, tmp_path) -> None:
    f = tmp_path / "pic.png"
    f.write_bytes(b"x")
    cfg = Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    add_file = mocker.patch(
        "tg_notes.cli.telegram.note_add_file",
        return_value={
            "notebook": "daily",
            "topic_id": 5,
            "message_id": 1,
            "date": "d",
            "media_type": "photo",
            "caption": "cap",
        },
    )
    add = mocker.patch("tg_notes.cli.telegram.note_add")

    rc = cli.main(["note", "add", "--file", str(f), "--caption", "cap"])

    assert rc == 0
    add_file.assert_called_once_with(
        cfg, notebook="daily", file_path=str(f), caption="cap", hashtags=None
    )
    add.assert_not_called()


def test_cli_note_add_file_passes_notebook_and_hashtags(mocker, tmp_path) -> None:
    f = tmp_path / "v.mp4"
    f.write_bytes(b"x")
    cfg = Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    add_file = mocker.patch(
        "tg_notes.cli.telegram.note_add_file", return_value={"media_type": "video"}
    )

    rc = cli.main(
        ["note", "add", "--notebook", "clips", "--file", str(f), "--caption", "c",
         "--hashtag", "x"]
    )

    assert rc == 0
    add_file.assert_called_once_with(
        cfg, notebook="clips", file_path=str(f), caption="c", hashtags=["x"]
    )


def test_cli_note_add_text_still_routes_to_note_add(mocker, tmp_path) -> None:
    note = tmp_path / "n.txt"
    note.write_text("hello", encoding="utf-8")
    cfg = Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    add = mocker.patch(
        "tg_notes.cli.telegram.note_add",
        return_value={"notebook": "daily", "topic_id": 5, "message_id": 1, "date": "d"},
    )
    add_file = mocker.patch("tg_notes.cli.telegram.note_add_file")

    rc = cli.main(["note", "add", "--text-file", str(note)])

    assert rc == 0
    add.assert_called_once_with(cfg, notebook="daily", text="hello", hashtags=None)
    add_file.assert_not_called()


def test_cli_note_add_file_missing_returns_1_no_network(mocker, tmp_path, capsys) -> None:
    cfg = Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    fake_cls = mocker.patch("tg_notes.telegram.TelegramClient")

    rc = cli.main(["note", "add", "--file", str(tmp_path / "gone.png")])

    assert rc == 1
    fake_cls.assert_not_called()  # real validation aborts before any network
    assert "gone.png" in capsys.readouterr().err


def test_cli_note_add_requires_file_or_text(mocker, capsys) -> None:
    cfg = Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)

    rc = cli.main(["note", "add"])

    assert rc == 2
    assert "file" in capsys.readouterr().err


# --- CLI: audio `note add --file` auto-transcription (media Phase 2) --------------


def _cfg_and_load(mocker) -> Config:
    cfg = Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    return cfg


def test_cli_note_add_audio_auto_transcribes_to_caption(mocker, tmp_path) -> None:
    f = tmp_path / "voice.ogg"
    f.write_bytes(b"x")
    cfg = _cfg_and_load(mocker)
    mocker.patch(
        "tg_notes.cli.transcribe.available_transcriber", return_value="faster-whisper"
    )
    tr = mocker.patch("tg_notes.cli.transcribe.transcribe", return_value="hello world")
    add_file = mocker.patch(
        "tg_notes.cli.telegram.note_add_file", return_value={"media_type": "voice"}
    )

    rc = cli.main(["note", "add", "--file", str(f)])

    assert rc == 0
    tr.assert_called_once_with(str(f), cfg)
    add_file.assert_called_once_with(
        cfg, notebook="daily", file_path=str(f), caption="hello world", hashtags=None
    )


def test_cli_note_add_audio_auto_skips_when_no_engine(mocker, tmp_path) -> None:
    f = tmp_path / "voice.ogg"
    f.write_bytes(b"x")
    cfg = _cfg_and_load(mocker)
    mocker.patch("tg_notes.cli.transcribe.available_transcriber", return_value=None)
    tr = mocker.patch("tg_notes.cli.transcribe.transcribe")
    add_file = mocker.patch(
        "tg_notes.cli.telegram.note_add_file", return_value={"media_type": "voice"}
    )

    rc = cli.main(["note", "add", "--file", str(f)])

    assert rc == 0
    tr.assert_not_called()  # auto mode never attempts when no engine is available
    add_file.assert_called_once_with(
        cfg, notebook="daily", file_path=str(f), caption=None, hashtags=None
    )


def test_cli_note_add_no_transcribe_skips(mocker, tmp_path) -> None:
    f = tmp_path / "voice.ogg"
    f.write_bytes(b"x")
    cfg = _cfg_and_load(mocker)
    avail = mocker.patch("tg_notes.cli.transcribe.available_transcriber")
    tr = mocker.patch("tg_notes.cli.transcribe.transcribe")
    add_file = mocker.patch(
        "tg_notes.cli.telegram.note_add_file", return_value={"media_type": "voice"}
    )

    rc = cli.main(["note", "add", "--file", str(f), "--no-transcribe"])

    assert rc == 0
    tr.assert_not_called()
    avail.assert_not_called()  # --no-transcribe short-circuits before any detection
    add_file.assert_called_once_with(
        cfg, notebook="daily", file_path=str(f), caption=None, hashtags=None
    )


def test_cli_note_add_caption_given_skips_transcription(mocker, tmp_path) -> None:
    f = tmp_path / "voice.ogg"
    f.write_bytes(b"x")
    cfg = _cfg_and_load(mocker)
    tr = mocker.patch("tg_notes.cli.transcribe.transcribe")
    add_file = mocker.patch(
        "tg_notes.cli.telegram.note_add_file", return_value={"media_type": "voice"}
    )

    rc = cli.main(["note", "add", "--file", str(f), "--caption", "manual"])

    assert rc == 0
    tr.assert_not_called()
    add_file.assert_called_once_with(
        cfg, notebook="daily", file_path=str(f), caption="manual", hashtags=None
    )


def test_cli_note_add_non_audio_file_not_transcribed(mocker, tmp_path) -> None:
    f = tmp_path / "pic.png"
    f.write_bytes(b"x")
    cfg = _cfg_and_load(mocker)
    tr = mocker.patch("tg_notes.cli.transcribe.transcribe")
    add_file = mocker.patch(
        "tg_notes.cli.telegram.note_add_file", return_value={"media_type": "photo"}
    )

    rc = cli.main(["note", "add", "--file", str(f)])

    assert rc == 0
    tr.assert_not_called()
    add_file.assert_called_once_with(
        cfg, notebook="daily", file_path=str(f), caption=None, hashtags=None
    )


def test_cli_note_add_unavailable_still_uploads_with_hint(mocker, tmp_path, capsys) -> None:
    f = tmp_path / "voice.ogg"
    f.write_bytes(b"x")
    cfg = _cfg_and_load(mocker)
    # explicit --transcribe bypasses the availability gate, so transcribe() runs and raises.
    mocker.patch("tg_notes.cli.transcribe.available_transcriber", return_value=None)
    mocker.patch(
        "tg_notes.cli.transcribe.transcribe",
        side_effect=cli.transcribe.TranscriptionUnavailable("no engine"),
    )
    add_file = mocker.patch(
        "tg_notes.cli.telegram.note_add_file", return_value={"media_type": "voice"}
    )

    rc = cli.main(["note", "add", "--file", str(f), "--transcribe"])

    assert rc == 0  # best-effort: the upload still succeeds
    add_file.assert_called_once_with(
        cfg, notebook="daily", file_path=str(f), caption=None, hashtags=None
    )
    assert "faster-whisper" in capsys.readouterr().err  # hint on how to enable


def test_cli_note_add_transcription_error_still_uploads_with_warning(
    mocker, tmp_path, capsys
) -> None:
    f = tmp_path / "voice.ogg"
    f.write_bytes(b"x")
    cfg = _cfg_and_load(mocker)
    mocker.patch(
        "tg_notes.cli.transcribe.available_transcriber", return_value="faster-whisper"
    )
    mocker.patch(
        "tg_notes.cli.transcribe.transcribe",
        side_effect=cli.transcribe.TranscriptionError("bad audio"),
    )
    add_file = mocker.patch(
        "tg_notes.cli.telegram.note_add_file", return_value={"media_type": "voice"}
    )

    rc = cli.main(["note", "add", "--file", str(f)])

    assert rc == 0  # best-effort: transcription failure must not lose the upload
    add_file.assert_called_once_with(
        cfg, notebook="daily", file_path=str(f), caption=None, hashtags=None
    )
    err = capsys.readouterr().err
    assert "bad audio" in err
