"""Tests for the CLI argument surface (TGN-2) and command wiring (TGN-3)."""
from __future__ import annotations

import argparse

import pytest

from tg_notes import cli, config, telegram


def _command_names(parser: argparse.ArgumentParser) -> set[str]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    return set()


def test_build_parser_exposes_login_and_whoami() -> None:
    names = _command_names(cli.build_parser())

    assert "login" in names
    assert "whoami" in names


def test_build_parser_still_exposes_stub_commands() -> None:
    names = _command_names(cli.build_parser())

    assert {"setup", "note", "notes", "contacts", "send", "notebooks"} <= names


@pytest.mark.parametrize(
    "argv",
    [
        ["notebooks", "list"],
    ],
)
def test_unimplemented_stubs_return_exit_code_2(argv: list[str]) -> None:
    assert cli.main(argv) == 2


def test_setup_command_ready_persists_group_id(mocker) -> None:
    cfg = config.Config(api_id=1, api_hash="h")
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    save = mocker.patch("tg_notes.cli.config.save")
    ask = mocker.patch("tg_notes.cli._ask")
    login = mocker.patch("tg_notes.cli.telegram.login")
    setup = mocker.patch(
        "tg_notes.cli.telegram.setup",
        return_value={"group_id": -100777, "created": True, "title": "t", "topics": {}},
    )

    rc = cli.main(["setup"])

    assert rc == 0
    setup.assert_called_once_with(cfg, notebook="daily")
    ask.assert_not_called()  # already configured → no credential prompt
    login.assert_not_called()  # already authorized → no login
    assert cfg.storage_group_id == -100777
    save.assert_called_once_with(cfg)


def test_setup_command_passes_custom_notebook(mocker) -> None:
    cfg = config.Config(api_id=1, api_hash="h")
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    mocker.patch("tg_notes.cli.config.save")
    setup = mocker.patch(
        "tg_notes.cli.telegram.setup",
        return_value={"group_id": -1, "created": True, "title": "t", "topics": {}},
    )

    assert cli.main(["setup", "--notebook", "weekly"]) == 0
    setup.assert_called_once_with(cfg, notebook="weekly")


def test_setup_command_prompts_credentials_then_logs_in(mocker) -> None:
    cfg = config.Config()  # nothing configured yet
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    save = mocker.patch("tg_notes.cli.config.save")
    mocker.patch("tg_notes.cli._ask", side_effect=["1234567", "hexhash"])
    login = mocker.patch("tg_notes.cli.telegram.login")
    setup = mocker.patch(
        "tg_notes.cli.telegram.setup",
        side_effect=[
            telegram.NotAuthorizedError("fresh session"),
            {"group_id": -100, "created": True, "title": "t", "topics": {}},
        ],
    )

    rc = cli.main(["setup"])

    assert rc == 0
    assert cfg.api_id == 1234567
    assert cfg.api_hash == "hexhash"
    login.assert_called_once_with(cfg)  # setup launches login after saving credentials
    assert setup.call_count == 2  # first raises NotAuthorized, retried after login
    assert save.call_count == 2  # creds saved (600) before login, group id after setup
    assert cfg.storage_group_id == -100


def test_setup_command_aborts_on_blank_credentials(mocker, capsys) -> None:
    cfg = config.Config()
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    save = mocker.patch("tg_notes.cli.config.save")
    mocker.patch("tg_notes.cli._ask", side_effect=["", ""])
    login = mocker.patch("tg_notes.cli.telegram.login")
    setup = mocker.patch("tg_notes.cli.telegram.setup")

    rc = cli.main(["setup"])

    assert rc == 1
    setup.assert_not_called()
    login.assert_not_called()
    save.assert_not_called()
    assert "my.telegram.org" in capsys.readouterr().err  # falls back to guidance


def test_setup_command_configured_but_not_logged_in_runs_login(mocker) -> None:
    cfg = config.Config(api_id=1, api_hash="h")
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    save = mocker.patch("tg_notes.cli.config.save")
    ask = mocker.patch("tg_notes.cli._ask")
    login = mocker.patch("tg_notes.cli.telegram.login")
    setup = mocker.patch(
        "tg_notes.cli.telegram.setup",
        side_effect=[
            telegram.NotAuthorizedError("no session"),
            {"group_id": -55, "created": False, "title": "t", "topics": {}},
        ],
    )

    rc = cli.main(["setup"])

    assert rc == 0
    ask.assert_not_called()  # already configured → no credential prompt
    login.assert_called_once_with(cfg)
    assert setup.call_count == 2
    assert cfg.storage_group_id == -55
    save.assert_called_once_with(cfg)  # only the group-id save (creds already present)


# --- note add (TGN-4) ------------------------------------------------------------


def test_note_add_command_posts_and_prints(mocker, tmp_path) -> None:
    note = tmp_path / "note.txt"
    note.write_text("hello", encoding="utf-8")
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    add = mocker.patch(
        "tg_notes.cli.telegram.note_add",
        return_value={"notebook": "daily", "topic_id": 5, "message_id": 99, "date": "d"},
    )

    rc = cli.main(["note", "add", "--notebook", "daily", "--text-file", str(note)])

    assert rc == 0
    add.assert_called_once_with(cfg, notebook="daily", text="hello", hashtags=None)


def test_note_add_command_passes_hashtags(mocker, tmp_path) -> None:
    note = tmp_path / "note.txt"
    note.write_text("hi", encoding="utf-8")
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    add = mocker.patch(
        "tg_notes.cli.telegram.note_add",
        return_value={"notebook": "daily", "topic_id": 5, "message_id": 1, "date": "d"},
    )

    rc = cli.main(
        ["note", "add", "--text-file", str(note), "--hashtag", "foo", "--hashtag", "bar"]
    )

    assert rc == 0
    add.assert_called_once_with(cfg, notebook="daily", text="hi", hashtags=["foo", "bar"])


def test_note_add_command_reads_stdin(mocker, monkeypatch) -> None:
    import io

    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    add = mocker.patch(
        "tg_notes.cli.telegram.note_add",
        return_value={"notebook": "daily", "topic_id": 5, "message_id": 1, "date": "d"},
    )
    monkeypatch.setattr("sys.stdin", io.StringIO("from stdin"))

    rc = cli.main(["note", "add", "--text-file", "-"])

    assert rc == 0
    add.assert_called_once_with(cfg, notebook="daily", text="from stdin", hashtags=None)


def test_note_add_command_unreadable_file_returns_1(mocker, tmp_path) -> None:
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    add = mocker.patch("tg_notes.cli.telegram.note_add")

    rc = cli.main(["note", "add", "--text-file", str(tmp_path / "missing.txt")])

    assert rc == 1
    add.assert_not_called()  # never reach the network on a read error


def test_note_add_command_not_set_up_returns_4(mocker, tmp_path, capsys) -> None:
    note = tmp_path / "note.txt"
    note.write_text("hi", encoding="utf-8")
    mocker.patch("tg_notes.cli.config.load", return_value=config.Config())
    mocker.patch(
        "tg_notes.cli.telegram.note_add",
        side_effect=telegram.NotSetUpError("run `tg-notes setup` first"),
    )

    rc = cli.main(["note", "add", "--text-file", str(note)])

    assert rc == 4
    assert "setup" in capsys.readouterr().err


def test_note_add_command_not_authorized_returns_3(mocker, tmp_path, capsys) -> None:
    note = tmp_path / "note.txt"
    note.write_text("hi", encoding="utf-8")
    mocker.patch(
        "tg_notes.cli.config.load", return_value=config.Config(api_id=1, api_hash="h")
    )
    mocker.patch(
        "tg_notes.cli.telegram.note_add",
        side_effect=telegram.NotAuthorizedError("not logged in"),
    )

    rc = cli.main(["note", "add", "--text-file", str(note)])

    assert rc == 3
    assert "login" in capsys.readouterr().err


# --- notes list (TGN-5) ----------------------------------------------------------


def test_notes_list_command_prints_json(mocker, capsys) -> None:
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    notes = [{"message_id": 6, "date": "2026-07-24T09:00:00+00:00", "text": "a"}]
    lst = mocker.patch("tg_notes.cli.telegram.notes_list", return_value=notes)

    rc = cli.main(["notes", "list", "--notebook", "daily"])

    assert rc == 0
    lst.assert_called_once_with(cfg, notebook="daily", since=None)
    import json as _json

    assert _json.loads(capsys.readouterr().out) == notes


def test_notes_list_command_parses_since(mocker) -> None:
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    lst = mocker.patch("tg_notes.cli.telegram.notes_list", return_value=[])

    rc = cli.main(["notes", "list", "--since", "2026-07-24"])

    assert rc == 0
    since = lst.call_args.kwargs["since"]
    assert (since.year, since.month, since.day) == (2026, 7, 24)
    assert since.tzinfo is not None  # made timezone-aware for comparison


def test_notes_list_command_invalid_since_returns_1(mocker) -> None:
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    lst = mocker.patch("tg_notes.cli.telegram.notes_list")

    rc = cli.main(["notes", "list", "--since", "not-a-date"])

    assert rc == 1
    lst.assert_not_called()  # never reach the network on a parse error


def test_notes_list_command_not_set_up_returns_4(mocker, capsys) -> None:
    mocker.patch("tg_notes.cli.config.load", return_value=config.Config())
    mocker.patch(
        "tg_notes.cli.telegram.notes_list",
        side_effect=telegram.NotSetUpError("run `tg-notes setup` first"),
    )

    rc = cli.main(["notes", "list"])

    assert rc == 4
    assert "setup" in capsys.readouterr().err


def test_notes_list_command_not_authorized_returns_3(mocker, capsys) -> None:
    mocker.patch(
        "tg_notes.cli.config.load", return_value=config.Config(api_id=1, api_hash="h")
    )
    mocker.patch(
        "tg_notes.cli.telegram.notes_list",
        side_effect=telegram.NotAuthorizedError("not logged in"),
    )

    rc = cli.main(["notes", "list"])

    assert rc == 3
    assert "login" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("value", "checks"),
    [
        ("2026-07-24", lambda d: (d.year, d.month, d.day, d.hour) == (2026, 7, 24, 0)),
        ("2026-07-24T09:30", lambda d: (d.hour, d.minute) == (9, 30)),
    ],
)
def test_parse_since_formats(value, checks) -> None:
    dt = cli._parse_since(value)
    assert dt.tzinfo is not None
    assert checks(dt)


def test_parse_since_hh_mm_uses_today() -> None:
    import datetime as _dt

    dt = cli._parse_since("09:30")
    assert (dt.hour, dt.minute) == (9, 30)
    assert dt.date() == _dt.datetime.now().astimezone().date()


def test_parse_since_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        cli._parse_since("not-a-date")


# --- contacts (TGN-6) ------------------------------------------------------------


def test_contacts_list_command_prints_json(mocker, capsys) -> None:
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    items = [{"key": "boss", "name": None, "chat_id": "@boss", "topic_id": None,
              "mention": None, "style": None}]
    lst = mocker.patch("tg_notes.cli.telegram.contacts_list", return_value=items)

    rc = cli.main(["contacts", "list"])

    assert rc == 0
    lst.assert_called_once_with(cfg)
    import json as _json

    assert _json.loads(capsys.readouterr().out) == items


def test_contacts_set_command_passes_all_fields(mocker) -> None:
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    setter = mocker.patch("tg_notes.cli.telegram.contacts_set", return_value={"created": True})

    rc = cli.main(
        [
            "contacts", "set", "boss",
            "--chat-id", "@boss", "--name", "Alice",
            "--topic-id", "42", "--mention", "@alice", "--style", "be brief",
        ]
    )

    assert rc == 0
    setter.assert_called_once_with(
        cfg, "boss", chat_id="@boss", name="Alice", topic_id=42,
        mention="@alice", style="be brief",
    )


def test_contacts_set_command_defaults_unset_fields_to_none(mocker) -> None:
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    setter = mocker.patch("tg_notes.cli.telegram.contacts_set", return_value={"created": False})

    rc = cli.main(["contacts", "set", "boss", "--style", "new"])

    assert rc == 0
    setter.assert_called_once_with(
        cfg, "boss", chat_id=None, name=None, topic_id=None, mention=None, style="new",
    )


def test_contacts_set_command_missing_chat_id_returns_1(mocker) -> None:
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    mocker.patch(
        "tg_notes.cli.telegram.contacts_set",
        side_effect=ValueError("a new contact needs --chat-id (where to send)"),
    )

    assert cli.main(["contacts", "set", "boss"]) == 1


def test_contacts_remove_command_prints_result(mocker, capsys) -> None:
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    rm = mocker.patch(
        "tg_notes.cli.telegram.contacts_remove",
        return_value={"key": "boss", "removed": True},
    )

    rc = cli.main(["contacts", "remove", "boss"])

    assert rc == 0
    rm.assert_called_once_with(cfg, "boss")
    import json as _json

    assert _json.loads(capsys.readouterr().out) == {"key": "boss", "removed": True}


def test_contacts_list_command_not_set_up_returns_4(mocker, capsys) -> None:
    mocker.patch("tg_notes.cli.config.load", return_value=config.Config())
    mocker.patch(
        "tg_notes.cli.telegram.contacts_list",
        side_effect=telegram.NotSetUpError("run `tg-notes setup` first"),
    )

    assert cli.main(["contacts", "list"]) == 4
    assert "setup" in capsys.readouterr().err


# --- send (TGN-7) ----------------------------------------------------------------


def test_send_command_posts_and_prints(mocker, tmp_path) -> None:
    out = tmp_path / "out.txt"
    out.write_text("compiled report", encoding="utf-8")
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    snd = mocker.patch(
        "tg_notes.cli.telegram.send",
        return_value={"contact": "boss", "sent": True, "message_id": 1},
    )

    rc = cli.main(["send", "--contact", "boss", "--text-file", str(out)])

    assert rc == 0
    snd.assert_called_once_with(cfg, "boss", "compiled report", dry_run=False)


def test_send_command_dry_run_passes_flag(mocker, tmp_path) -> None:
    out = tmp_path / "out.txt"
    out.write_text("x", encoding="utf-8")
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    snd = mocker.patch(
        "tg_notes.cli.telegram.send", return_value={"contact": "boss", "sent": False}
    )

    rc = cli.main(["send", "--contact", "boss", "--text-file", str(out), "--dry-run"])

    assert rc == 0
    snd.assert_called_once_with(cfg, "boss", "x", dry_run=True)


def test_send_command_reads_stdin(mocker, monkeypatch) -> None:
    import io

    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    snd = mocker.patch(
        "tg_notes.cli.telegram.send", return_value={"contact": "boss", "sent": True}
    )
    monkeypatch.setattr("sys.stdin", io.StringIO("piped text"))

    rc = cli.main(["send", "--contact", "boss", "--text-file", "-"])

    assert rc == 0
    snd.assert_called_once_with(cfg, "boss", "piped text", dry_run=False)


def test_send_command_contact_not_found_returns_5(mocker, tmp_path, capsys) -> None:
    out = tmp_path / "out.txt"
    out.write_text("x", encoding="utf-8")
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    mocker.patch(
        "tg_notes.cli.telegram.send",
        side_effect=telegram.ContactNotFoundError("no contact 'ghost'"),
    )

    rc = cli.main(["send", "--contact", "ghost", "--text-file", str(out)])

    assert rc == 5
    assert "ghost" in capsys.readouterr().err


def test_send_command_unreadable_file_returns_1(mocker, tmp_path) -> None:
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    snd = mocker.patch("tg_notes.cli.telegram.send")

    rc = cli.main(["send", "--contact", "boss", "--text-file", str(tmp_path / "no.txt")])

    assert rc == 1
    snd.assert_not_called()


def test_send_command_not_set_up_returns_4(mocker, tmp_path, capsys) -> None:
    out = tmp_path / "out.txt"
    out.write_text("x", encoding="utf-8")
    mocker.patch("tg_notes.cli.config.load", return_value=config.Config())
    mocker.patch(
        "tg_notes.cli.telegram.send",
        side_effect=telegram.NotSetUpError("run `tg-notes setup` first"),
    )

    rc = cli.main(["send", "--contact", "boss", "--text-file", str(out)])

    assert rc == 4
    assert "setup" in capsys.readouterr().err
