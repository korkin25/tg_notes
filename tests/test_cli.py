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


def test_build_parser_exposes_all_commands() -> None:
    names = _command_names(cli.build_parser())

    assert {"setup", "note", "notes", "contacts", "send", "notebooks"} <= names


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
    mocker.patch("tg_notes.cli._interactive", return_value=False)
    lst = mocker.patch("tg_notes.cli.telegram.notes_list", return_value=[])

    rc = cli.main(["notes", "list", "--since", "2026-07-24"])

    assert rc == 0
    since = lst.call_args.kwargs["since"]
    assert (since.year, since.month, since.day) == (2026, 7, 24)
    assert since.tzinfo is not None  # made timezone-aware for comparison


def test_notes_list_command_invalid_since_returns_1(mocker) -> None:
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    mocker.patch("tg_notes.cli._interactive", return_value=False)
    lst = mocker.patch("tg_notes.cli.telegram.notes_list")

    rc = cli.main(["notes", "list", "--since", "not-a-date"])

    assert rc == 1
    lst.assert_not_called()  # never reach the network on a parse error


def test_notes_list_command_not_set_up_returns_4(mocker, capsys) -> None:
    mocker.patch("tg_notes.cli.config.load", return_value=config.Config())
    mocker.patch("tg_notes.cli._interactive", return_value=False)
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
    mocker.patch("tg_notes.cli._interactive", return_value=False)
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


# --- notebooks list (TGN-8) ------------------------------------------------------


def test_notebooks_list_command_prints_json(mocker, capsys) -> None:
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    items = [{"name": "daily", "topic_id": 5}]
    lst = mocker.patch("tg_notes.cli.telegram.notebooks_list", return_value=items)

    rc = cli.main(["notebooks", "list"])

    assert rc == 0
    lst.assert_called_once_with(cfg)
    import json as _json

    assert _json.loads(capsys.readouterr().out) == items


def test_notebooks_list_command_not_set_up_returns_4(mocker, capsys) -> None:
    mocker.patch("tg_notes.cli.config.load", return_value=config.Config())
    mocker.patch(
        "tg_notes.cli.telegram.notebooks_list",
        side_effect=telegram.NotSetUpError("run `tg-notes setup` first"),
    )

    assert cli.main(["notebooks", "list"]) == 4
    assert "setup" in capsys.readouterr().err


# --- secrets (TGN-18) ------------------------------------------------------------


def test_secrets_status_command_prints_json(mocker, capsys) -> None:
    mocker.patch("tg_notes.cli.config.load", return_value=config.Config(api_id=1, api_hash="h"))
    mocker.patch("tg_notes.cli.secrets.keyring_available", return_value=True)
    mocker.patch("tg_notes.cli._secret_service_provider", return_value="gnome-keyring-d")
    mocker.patch(
        "tg_notes.cli._available_secret_stores",
        return_value=["gnome-keyring (serves Secret Service)", "keepassxc (running)"],
    )

    rc = cli.main(["secrets", "status"])

    assert rc == 0
    import json as _json

    out = _json.loads(capsys.readouterr().out)
    assert out["backend"] == "file"
    assert out["keyring_available"] is True
    assert out["secret_service_provider"] == "gnome-keyring-d"
    assert "keepassxc (running)" in out["available_stores"]


def test_available_secret_stores_parses_busctl(mocker) -> None:
    busctl_out = (
        "org.freedesktop.secrets  2394 gnome-keyring-d csssr :1.3 x - -\n"
        "org.keepassxc.KeePassXC.MainWindow 5 keepassxc csssr :1.58 y - -\n"
        "org.kde.kwalletd6  9 kwalletd6 csssr :1.78 z - -\n"
    )
    mocker.patch("tg_notes.cli._busctl_list", return_value=busctl_out)

    stores = cli._available_secret_stores()

    assert "gnome-keyring (serves Secret Service)" in stores
    assert "keepassxc (running)" in stores
    assert "kwalletd (KDE) (running)" in stores


def test_secrets_migrate_to_keyring(mocker) -> None:
    cfg = config.Config(api_id=1, api_hash="h")
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    save = mocker.patch("tg_notes.cli.config.save")
    # mock the probe + migration so the test never touches a real keyring/vault
    mocker.patch("tg_notes.cli.secrets.keyring_probe", return_value=(True, None))
    mocker.patch("tg_notes.cli._secret_service_provider", return_value="keepassxc")
    mocker.patch("tg_notes.cli._available_secret_stores", return_value=[])
    mig = mocker.patch("tg_notes.cli.secrets.migrate_to_keyring")

    rc = cli.main(["secrets", "migrate", "--to", "keyring"])

    assert rc == 0
    mig.assert_called_once_with(cfg)
    save.assert_called_once_with(cfg)


def test_secrets_migrate_already_active_is_noop(mocker) -> None:
    mocker.patch("tg_notes.cli.config.load", return_value=config.Config(secrets_backend="file"))
    save = mocker.patch("tg_notes.cli.config.save")
    mig = mocker.patch("tg_notes.cli.secrets.migrate_to_file")

    assert cli.main(["secrets", "migrate", "--to", "file"]) == 0
    mig.assert_not_called()
    save.assert_not_called()


def test_secrets_migrate_keyring_unavailable_returns_1(mocker, capsys) -> None:
    mocker.patch("tg_notes.cli.config.load", return_value=config.Config(api_id=1, api_hash="h"))
    mocker.patch("tg_notes.cli.secrets.keyring_probe", return_value=(False, "not-installed"))
    mocker.patch("tg_notes.cli._secret_service_provider", return_value=None)
    mocker.patch("tg_notes.cli._available_secret_stores", return_value=[])
    mig = mocker.patch("tg_notes.cli.secrets.migrate_to_keyring")  # safety: never real-migrate

    assert cli.main(["secrets", "migrate", "--to", "keyring"]) == 1
    mig.assert_not_called()
    assert "keyring" in capsys.readouterr().err


# --- secrets doctor / recommendations (TGN-18) -----------------------------------


def _secrets_state(**over):
    base = {
        "backend": "file", "configured": True, "has_session": True,
        "keyring_installed": True, "probe_ok": True, "probe_kind": None,
        "provider": "keepassxc", "stores": ["keepassxc (serves Secret Service)"],
    }
    base.update(over)
    return base


def test_reco_ready_file_backend_suggests_migrate() -> None:
    recs = cli._secrets_recommendations(_secrets_state(backend="file", probe_ok=True))
    assert any("migrate --to keyring" in r for r in recs)


def test_reco_locked_suggests_confirm_off() -> None:
    recs = cli._secrets_recommendations(_secrets_state(probe_ok=False, probe_kind="locked"))
    assert any("confirm" in r.lower() for r in recs)
    assert any("dedicated" in r.lower() for r in recs)


def test_reco_no_collection_suggests_expose_group() -> None:
    recs = cli._secrets_recommendations(
        _secrets_state(probe_ok=False, probe_kind="no-collection")
    )
    assert any("Expose entries under this group" in r for r in recs)


def test_reco_not_installed() -> None:
    recs = cli._secrets_recommendations(_secrets_state(keyring_installed=False))
    assert any("tg-notes[keyring]" in r for r in recs)


def test_reco_gnome_holds_bus_keepassxc_running_offers_handover() -> None:
    recs = cli._secrets_recommendations(
        _secrets_state(
            provider="gnome-keyring-d", probe_ok=False, probe_kind="no-collection",
            stores=["gnome-keyring (serves Secret Service)", "keepassxc (running)"],
        )
    )
    assert any("hand it to" in r.lower() for r in recs)


def test_reco_not_configured() -> None:
    recs = cli._secrets_recommendations(_secrets_state(configured=False))
    assert any("tg-notes setup" in r for r in recs)


def test_secrets_doctor_command_json(mocker, capsys) -> None:
    mocker.patch("tg_notes.cli.config.load", return_value=config.Config(api_id=1, api_hash="h"))
    mocker.patch("tg_notes.cli.secrets.keyring_probe", return_value=(True, None))
    mocker.patch("tg_notes.cli._secret_service_provider", return_value="keepassxc")
    mocker.patch(
        "tg_notes.cli._available_secret_stores",
        return_value=["keepassxc (serves Secret Service)"],
    )

    rc = cli.main(["secrets", "doctor", "--json"])

    assert rc == 0
    import json as _json

    out = _json.loads(capsys.readouterr().out)
    assert out["backend"] == "file" and out["probe_ok"] is True
    assert "recommendations" in out
    assert out["keyring_service"] == "tg-notes"
    assert "config_dir" in out


def test_secrets_migrate_keyring_not_ready_shows_recommendations(mocker, capsys) -> None:
    mocker.patch("tg_notes.cli.config.load", return_value=config.Config(api_id=1, api_hash="h"))
    mocker.patch("tg_notes.cli.secrets.keyring_probe", return_value=(False, "locked"))
    mocker.patch("tg_notes.cli._secret_service_provider", return_value="keepassxc")
    mocker.patch("tg_notes.cli._available_secret_stores", return_value=["keepassxc (running)"])
    mig = mocker.patch("tg_notes.cli.secrets.migrate_to_keyring")

    rc = cli.main(["secrets", "migrate", "--to", "keyring"])

    assert rc == 1
    mig.assert_not_called()
    assert "confirm" in capsys.readouterr().err.lower()


# --- interactive pickers (TGN-fzf) -----------------------------------------------
#
# Safety contract: a picker fires ONLY when the value is omitted AND the session is
# interactive (both stdin and stdout are TTYs). The agent Skills always pass the value
# via a flag and run non-interactively, so those paths must never invoke `_pick`.


def _contact(key: str, name: str | None = None, chat_id: str | None = None) -> dict:
    return {
        "key": key, "name": name, "chat_id": chat_id, "topic_id": None,
        "mention": None, "style": None,
    }


# --- _pick unit tests ---


def test_pick_uses_fzf_when_available(mocker) -> None:
    mocker.patch("tg_notes.cli._interactive", return_value=True)
    mocker.patch(
        "shutil.which", side_effect=lambda name: "/usr/bin/fzf" if name == "fzf" else None
    )
    proc = mocker.Mock(returncode=0, stdout="boss — Alice\n")
    run = mocker.patch("subprocess.run", return_value=proc)

    options = [("boss", "boss — Alice"), ("mgr", "mgr — Bob")]
    assert cli._pick(options, "contact") == "boss"
    run.assert_called_once()


def test_pick_numbered_fallback_when_no_finder(mocker) -> None:
    mocker.patch("tg_notes.cli._interactive", return_value=True)
    mocker.patch("shutil.which", return_value=None)  # no fzf/sk/fzy on PATH
    run = mocker.patch("subprocess.run")
    inp = mocker.patch("builtins.input", return_value="2")

    options = [("boss", "boss — Alice"), ("mgr", "mgr — Bob")]
    assert cli._pick(options, "contact") == "mgr"
    run.assert_not_called()  # no finder → no subprocess
    inp.assert_called_once()


def test_pick_non_interactive_returns_none_without_prompting(mocker) -> None:
    mocker.patch("tg_notes.cli._interactive", return_value=False)
    which = mocker.patch("shutil.which")
    run = mocker.patch("subprocess.run")
    inp = mocker.patch("builtins.input")

    assert cli._pick([("boss", "boss — Alice")], "contact") is None
    which.assert_not_called()
    run.assert_not_called()
    inp.assert_not_called()


def test_pick_empty_options_returns_none(mocker) -> None:
    interactive = mocker.patch("tg_notes.cli._interactive", return_value=True)
    assert cli._pick([], "contact") is None
    interactive.assert_not_called()  # short-circuits before checking the session


def test_pick_fzf_cancel_returns_none(mocker) -> None:
    mocker.patch("tg_notes.cli._interactive", return_value=True)
    mocker.patch(
        "shutil.which", side_effect=lambda name: "/usr/bin/fzf" if name == "fzf" else None
    )
    mocker.patch("subprocess.run", return_value=mocker.Mock(returncode=1, stdout=""))

    assert cli._pick([("boss", "boss — Alice")], "contact") is None


def test_contact_label_composes_key_name_chat_id() -> None:
    label = cli._contact_label(_contact("boss", name="Alice", chat_id="@boss"))
    assert label == "boss — Alice (@boss)"
    assert cli._contact_label(_contact("plain")) == "plain"


# --- send: agent-safety + interactive path ---


def test_send_with_contact_flag_does_not_pick(mocker, tmp_path) -> None:
    out = tmp_path / "out.txt"
    out.write_text("compiled report", encoding="utf-8")
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    pick = mocker.patch("tg_notes.cli._pick")
    clist = mocker.patch("tg_notes.cli.telegram.contacts_list")
    snd = mocker.patch(
        "tg_notes.cli.telegram.send", return_value={"contact": "boss", "sent": True}
    )

    rc = cli.main(["send", "--contact", "boss", "--text-file", str(out)])

    assert rc == 0
    pick.assert_not_called()  # flag given → never prompt
    clist.assert_not_called()
    snd.assert_called_once_with(cfg, "boss", "compiled report", dry_run=False)


def test_send_without_contact_noninteractive_errors(mocker, capsys) -> None:
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    mocker.patch("tg_notes.cli._interactive", return_value=False)
    pick = mocker.patch("tg_notes.cli._pick")
    snd = mocker.patch("tg_notes.cli.telegram.send")

    rc = cli.main(["send", "--text-file", "-"])

    assert rc == 2
    pick.assert_not_called()  # non-interactive → never prompt
    snd.assert_not_called()
    assert "--contact" in capsys.readouterr().err


def test_send_without_contact_interactive_uses_pick(mocker, tmp_path) -> None:
    out = tmp_path / "out.txt"
    out.write_text("compiled report", encoding="utf-8")
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    mocker.patch("tg_notes.cli._interactive", return_value=True)
    clist = mocker.patch(
        "tg_notes.cli.telegram.contacts_list",
        return_value=[_contact("boss", name="Alice", chat_id="@boss")],
    )
    pick = mocker.patch("tg_notes.cli._pick", return_value="boss")
    snd = mocker.patch(
        "tg_notes.cli.telegram.send", return_value={"contact": "boss", "sent": True}
    )

    rc = cli.main(["send", "--text-file", str(out)])

    assert rc == 0
    clist.assert_called_once_with(cfg)
    pick.assert_called_once()
    snd.assert_called_once_with(cfg, "boss", "compiled report", dry_run=False)


def test_send_without_contact_interactive_no_contacts_errors(mocker, capsys) -> None:
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    mocker.patch("tg_notes.cli._interactive", return_value=True)
    mocker.patch("tg_notes.cli.telegram.contacts_list", return_value=[])
    snd = mocker.patch("tg_notes.cli.telegram.send")

    rc = cli.main(["send", "--text-file", "-"])

    assert rc == 2
    snd.assert_not_called()
    assert "contacts" in capsys.readouterr().err


def test_send_without_contact_interactive_cancel_errors(mocker, capsys) -> None:
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    mocker.patch("tg_notes.cli._interactive", return_value=True)
    mocker.patch(
        "tg_notes.cli.telegram.contacts_list", return_value=[_contact("boss")]
    )
    mocker.patch("tg_notes.cli._pick", return_value=None)  # user cancels
    snd = mocker.patch("tg_notes.cli.telegram.send")

    rc = cli.main(["send", "--text-file", "-"])

    assert rc == 2
    snd.assert_not_called()
    assert "no contact selected" in capsys.readouterr().err


# --- contacts remove: agent-safety + interactive path ---


def test_contacts_remove_with_key_does_not_pick(mocker) -> None:
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    pick = mocker.patch("tg_notes.cli._pick")
    clist = mocker.patch("tg_notes.cli.telegram.contacts_list")
    rm = mocker.patch(
        "tg_notes.cli.telegram.contacts_remove",
        return_value={"key": "boss", "removed": True},
    )

    rc = cli.main(["contacts", "remove", "boss"])

    assert rc == 0
    pick.assert_not_called()
    clist.assert_not_called()
    rm.assert_called_once_with(cfg, "boss")


def test_contacts_remove_without_key_noninteractive_errors(mocker, capsys) -> None:
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    mocker.patch("tg_notes.cli._interactive", return_value=False)
    pick = mocker.patch("tg_notes.cli._pick")
    rm = mocker.patch("tg_notes.cli.telegram.contacts_remove")

    rc = cli.main(["contacts", "remove"])

    assert rc == 2
    pick.assert_not_called()
    rm.assert_not_called()
    assert "contact key" in capsys.readouterr().err


def test_contacts_remove_without_key_interactive_uses_pick(mocker) -> None:
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    mocker.patch("tg_notes.cli._interactive", return_value=True)
    clist = mocker.patch(
        "tg_notes.cli.telegram.contacts_list", return_value=[_contact("boss")]
    )
    pick = mocker.patch("tg_notes.cli._pick", return_value="boss")
    rm = mocker.patch(
        "tg_notes.cli.telegram.contacts_remove",
        return_value={"key": "boss", "removed": True},
    )

    rc = cli.main(["contacts", "remove"])

    assert rc == 0
    clist.assert_called_once_with(cfg)
    pick.assert_called_once()
    rm.assert_called_once_with(cfg, "boss")


# --- secrets migrate: agent-safety + interactive path ---


def test_secrets_migrate_with_to_flag_does_not_pick(mocker) -> None:
    cfg = config.Config(api_id=1, api_hash="h")
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    mocker.patch("tg_notes.cli.config.save")
    mocker.patch("tg_notes.cli.secrets.keyring_probe", return_value=(True, None))
    mocker.patch("tg_notes.cli._secret_service_provider", return_value="keepassxc")
    mocker.patch("tg_notes.cli._available_secret_stores", return_value=[])
    pick = mocker.patch("tg_notes.cli._pick")
    mig = mocker.patch("tg_notes.cli.secrets.migrate_to_keyring")

    rc = cli.main(["secrets", "migrate", "--to", "keyring"])

    assert rc == 0
    pick.assert_not_called()
    mig.assert_called_once_with(cfg)


def test_secrets_migrate_without_to_noninteractive_errors(mocker, capsys) -> None:
    cfg = config.Config(api_id=1, api_hash="h")
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    mocker.patch("tg_notes.cli._interactive", return_value=False)
    pick = mocker.patch("tg_notes.cli._pick")
    migk = mocker.patch("tg_notes.cli.secrets.migrate_to_keyring")
    migf = mocker.patch("tg_notes.cli.secrets.migrate_to_file")

    rc = cli.main(["secrets", "migrate"])

    assert rc == 2
    pick.assert_not_called()
    migk.assert_not_called()
    migf.assert_not_called()
    assert "--to" in capsys.readouterr().err


def test_secrets_migrate_without_to_interactive_uses_pick(mocker) -> None:
    cfg = config.Config(api_id=1, api_hash="h")
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    mocker.patch("tg_notes.cli.config.save")
    mocker.patch("tg_notes.cli._interactive", return_value=True)
    mocker.patch("tg_notes.cli.secrets.keyring_probe", return_value=(True, None))
    mocker.patch("tg_notes.cli._secret_service_provider", return_value="keepassxc")
    mocker.patch("tg_notes.cli._available_secret_stores", return_value=[])
    pick = mocker.patch("tg_notes.cli._pick", return_value="keyring")
    mig = mocker.patch("tg_notes.cli.secrets.migrate_to_keyring")

    rc = cli.main(["secrets", "migrate"])

    assert rc == 0
    pick.assert_called_once()
    mig.assert_called_once_with(cfg)


# --- notes list: interactive picker + non-interactive default ---


def test_notes_list_without_notebook_noninteractive_defaults_daily(mocker) -> None:
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    mocker.patch("tg_notes.cli._interactive", return_value=False)
    nb = mocker.patch("tg_notes.cli.telegram.notebooks_list")
    lst = mocker.patch("tg_notes.cli.telegram.notes_list", return_value=[])

    rc = cli.main(["notes", "list"])

    assert rc == 0
    nb.assert_not_called()  # non-interactive → no picker, no notebooks probe
    lst.assert_called_once_with(cfg, notebook="daily", since=None)


def test_notes_list_without_notebook_interactive_uses_pick(mocker) -> None:
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    mocker.patch("tg_notes.cli._interactive", return_value=True)
    nb = mocker.patch(
        "tg_notes.cli.telegram.notebooks_list",
        return_value=[{"name": "weekly", "topic_id": 7}],
    )
    pick = mocker.patch("tg_notes.cli._pick", return_value="weekly")
    lst = mocker.patch("tg_notes.cli.telegram.notes_list", return_value=[])

    rc = cli.main(["notes", "list"])

    assert rc == 0
    nb.assert_called_once_with(cfg)
    pick.assert_called_once()
    lst.assert_called_once_with(cfg, notebook="weekly", since=None)


def test_notes_list_interactive_pick_cancel_falls_back_to_daily(mocker) -> None:
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    mocker.patch("tg_notes.cli._interactive", return_value=True)
    mocker.patch(
        "tg_notes.cli.telegram.notebooks_list",
        return_value=[{"name": "weekly", "topic_id": 7}],
    )
    mocker.patch("tg_notes.cli._pick", return_value=None)  # user cancels
    lst = mocker.patch("tg_notes.cli.telegram.notes_list", return_value=[])

    rc = cli.main(["notes", "list"])

    assert rc == 0
    lst.assert_called_once_with(cfg, notebook="daily", since=None)


def test_notes_list_interactive_empty_notebooks_falls_back_to_daily(mocker) -> None:
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100)
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    mocker.patch("tg_notes.cli._interactive", return_value=True)
    mocker.patch("tg_notes.cli.telegram.notebooks_list", return_value=[])
    pick = mocker.patch("tg_notes.cli._pick")
    lst = mocker.patch("tg_notes.cli.telegram.notes_list", return_value=[])

    rc = cli.main(["notes", "list"])

    assert rc == 0
    pick.assert_not_called()  # nothing to choose from
    lst.assert_called_once_with(cfg, notebook="daily", since=None)
