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


def test_setup_command_persists_returned_group_id(mocker) -> None:
    cfg = config.Config(api_id=1, api_hash="h")
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    save = mocker.patch("tg_notes.cli.config.save")
    setup = mocker.patch(
        "tg_notes.cli.telegram.setup",
        return_value={"group_id": -100777, "created": True, "title": "t", "topics": {}},
    )

    rc = cli.main(["setup"])

    assert rc == 0
    setup.assert_called_once_with(cfg, notebook="daily")
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


def test_setup_command_not_configured_returns_1(mocker) -> None:
    mocker.patch("tg_notes.cli.config.load", return_value=config.Config())
    mocker.patch(
        "tg_notes.cli.telegram.setup", side_effect=telegram.NotConfiguredError("nope")
    )
    save = mocker.patch("tg_notes.cli.config.save")

    assert cli.main(["setup"]) == 1
    save.assert_not_called()  # nothing to persist on the failure path


def test_setup_command_not_authorized_returns_3(mocker) -> None:
    mocker.patch(
        "tg_notes.cli.config.load", return_value=config.Config(api_id=1, api_hash="h")
    )
    mocker.patch(
        "tg_notes.cli.telegram.setup", side_effect=telegram.NotAuthorizedError("login")
    )
    save = mocker.patch("tg_notes.cli.config.save")

    assert cli.main(["setup"]) == 3
    save.assert_not_called()
