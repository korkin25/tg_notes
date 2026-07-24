"""Unit tests for the `tg-notes fanout` command (TGN-26, feature #24).

Fully mocked: `telegram.*` and `ai.rewrite` are patched, so no Telegram or Anthropic call is
made. Covers per-contact rewriting, the `--no-rewrite` / auto paths, best-effort AI fallback,
dry-run, empty notes, and the unknown-contact error.
"""
from __future__ import annotations

import json

from tg_notes import cli, config


def _cfg():
    return config.Config(api_id=1, api_hash="h", storage_group_id=-100)


def _note(text: str, mid: int = 1):
    return {"message_id": mid, "date": None, "text": text, "media": None}


def _contacts(mocker, entries):
    return mocker.patch("tg_notes.cli.telegram.contacts_list", return_value=entries)


def _sent(key: str, text: str, sent: bool = True):
    return {"contact": key, "chat_id": "me", "topic_id": None, "text": text, "sent": sent}


def test_fanout_rewrites_per_contact(mocker, capsys) -> None:
    mocker.patch("tg_notes.cli.config.load", return_value=_cfg())
    mocker.patch("tg_notes.cli.telegram.notes_list", return_value=[_note("raw note")])
    _contacts(mocker, [
        {"key": "mgr", "style": "manager"},
        {"key": "lead", "style": "tech lead"},
    ])
    mocker.patch("tg_notes.cli.ai.available", return_value=True)
    rewrite = mocker.patch(
        "tg_notes.cli.ai.rewrite", side_effect=lambda src, style, **kw: f"rw:{style}"
    )
    send = mocker.patch(
        "tg_notes.cli.telegram.send",
        side_effect=lambda cfg, key, text, dry_run=False: _sent(key, text),
    )

    rc = cli.main(["fanout", "--contact", "mgr", "--contact", "lead"])

    assert rc == 0
    # Each contact rewritten from the same source, per its own style.
    assert [c.args[1] for c in rewrite.call_args_list] == ["manager", "tech lead"]
    assert all(c.args[0] == "raw note" for c in rewrite.call_args_list)
    sent_texts = {c.args[1]: c.args[2] for c in send.call_args_list}
    assert sent_texts == {"mgr": "rw:manager", "lead": "rw:tech lead"}
    out = json.loads(capsys.readouterr().out)
    assert {r["contact"] for r in out} == {"mgr", "lead"}


def test_fanout_no_rewrite_sends_raw(mocker) -> None:
    mocker.patch("tg_notes.cli.config.load", return_value=_cfg())
    mocker.patch("tg_notes.cli.telegram.notes_list", return_value=[_note("raw note")])
    _contacts(mocker, [{"key": "mgr", "style": "manager"}])
    rewrite = mocker.patch("tg_notes.cli.ai.rewrite")
    send = mocker.patch(
        "tg_notes.cli.telegram.send",
        side_effect=lambda cfg, key, text, dry_run=False: _sent(key, text),
    )

    rc = cli.main(["fanout", "--contact", "mgr", "--no-rewrite"])

    assert rc == 0
    rewrite.assert_not_called()
    assert send.call_args.args[2] == "raw note"


def test_fanout_ai_failure_falls_back_to_raw(mocker) -> None:
    mocker.patch("tg_notes.cli.config.load", return_value=_cfg())
    mocker.patch("tg_notes.cli.telegram.notes_list", return_value=[_note("raw note")])
    _contacts(mocker, [{"key": "mgr", "style": "manager"}])
    mocker.patch("tg_notes.cli.ai.available", return_value=True)
    mocker.patch("tg_notes.cli.ai.rewrite", side_effect=cli.ai.AIError("boom"))
    send = mocker.patch(
        "tg_notes.cli.telegram.send",
        side_effect=lambda cfg, key, text, dry_run=False: _sent(key, text),
    )

    rc = cli.main(["fanout", "--contact", "mgr"])

    assert rc == 0  # never blocks the send
    assert send.call_args.args[2] == "raw note"


def test_fanout_auto_skips_ai_when_unavailable(mocker) -> None:
    mocker.patch("tg_notes.cli.config.load", return_value=_cfg())
    mocker.patch("tg_notes.cli.telegram.notes_list", return_value=[_note("raw note")])
    _contacts(mocker, [{"key": "mgr", "style": "manager"}])
    mocker.patch("tg_notes.cli.ai.available", return_value=False)
    rewrite = mocker.patch("tg_notes.cli.ai.rewrite")
    send = mocker.patch(
        "tg_notes.cli.telegram.send",
        side_effect=lambda cfg, key, text, dry_run=False: _sent(key, text),
    )

    rc = cli.main(["fanout", "--contact", "mgr"])

    assert rc == 0
    rewrite.assert_not_called()
    assert send.call_args.args[2] == "raw note"


def test_fanout_dry_run(mocker) -> None:
    mocker.patch("tg_notes.cli.config.load", return_value=_cfg())
    mocker.patch("tg_notes.cli.telegram.notes_list", return_value=[_note("raw note")])
    _contacts(mocker, [{"key": "mgr", "style": "manager"}])
    mocker.patch("tg_notes.cli.ai.available", return_value=False)
    send = mocker.patch(
        "tg_notes.cli.telegram.send",
        side_effect=lambda cfg, key, text, dry_run=False: _sent(key, text, sent=not dry_run),
    )

    rc = cli.main(["fanout", "--contact", "mgr", "--dry-run"])

    assert rc == 0
    assert send.call_args.kwargs["dry_run"] is True


def test_fanout_empty_notes_sends_nothing(mocker, capsys) -> None:
    mocker.patch("tg_notes.cli.config.load", return_value=_cfg())
    mocker.patch("tg_notes.cli.telegram.notes_list", return_value=[])
    send = mocker.patch("tg_notes.cli.telegram.send")

    rc = cli.main(["fanout", "--contact", "mgr"])

    assert rc == 0
    send.assert_not_called()
    assert json.loads(capsys.readouterr().out)["sent"] == []


def test_fanout_unknown_contact_exits_5(mocker) -> None:
    mocker.patch("tg_notes.cli.config.load", return_value=_cfg())
    mocker.patch("tg_notes.cli.telegram.notes_list", return_value=[_note("raw note")])
    _contacts(mocker, [{"key": "mgr", "style": "manager"}])
    send = mocker.patch("tg_notes.cli.telegram.send")

    rc = cli.main(["fanout", "--contact", "ghost"])

    assert rc == 5
    send.assert_not_called()


def test_fanout_model_precedence(mocker) -> None:
    """--model wins over config.ai_model wins over ai.DEFAULT_MODEL."""
    cfg = config.Config(api_id=1, api_hash="h", storage_group_id=-100, ai_model="cfg-model")
    mocker.patch("tg_notes.cli.config.load", return_value=cfg)
    mocker.patch("tg_notes.cli.telegram.notes_list", return_value=[_note("raw note")])
    _contacts(mocker, [{"key": "mgr", "style": "manager"}])
    mocker.patch("tg_notes.cli.ai.available", return_value=True)
    rewrite = mocker.patch("tg_notes.cli.ai.rewrite", return_value="x")
    mocker.patch(
        "tg_notes.cli.telegram.send",
        side_effect=lambda cfg, key, text, dry_run=False: _sent(key, text),
    )

    cli.main(["fanout", "--contact", "mgr", "--model", "flag-model"])
    assert rewrite.call_args.kwargs["model"] == "flag-model"

    cli.main(["fanout", "--contact", "mgr"])
    assert rewrite.call_args.kwargs["model"] == "cfg-model"
