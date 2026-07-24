"""Tests for the CLI argument surface (TGN-2)."""
from __future__ import annotations

import argparse

import pytest

from tg_notes import cli


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
        ["setup"],
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
