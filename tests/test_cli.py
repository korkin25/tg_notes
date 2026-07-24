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
        ["note", "add", "--text-file", "note.txt"],
        ["notes", "list"],
        ["contacts", "list"],
        ["contacts", "set", "boss"],
        ["contacts", "remove", "boss"],
        ["send", "--contact", "boss", "--text-file", "out.txt"],
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
