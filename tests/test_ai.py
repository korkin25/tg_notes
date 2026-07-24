"""Unit tests for the optional AI rewrite backend (TGN-26, feature #24).

Fully mocked and CI-safe: the ``anthropic`` SDK is never imported for real and no network
call is made. ``ai.rewrite`` is exercised by patching the client factory; ``available()`` is
driven by injecting/removing a fake ``anthropic`` module in ``sys.modules``.
"""
from __future__ import annotations

import sys
import types

import pytest

from tg_notes import ai

# --- availability + client resolution --------------------------------------------


def test_ai_available_false_without_extra(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "anthropic", None)  # force ImportError on import
    assert ai.available() is False


def test_ai_available_true_with_module(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "anthropic", types.ModuleType("anthropic"))
    assert ai.available() is True


def test_ai_client_raises_when_extra_missing(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "anthropic", None)
    with pytest.raises(ai.AIUnavailable):
        ai._client()


def test_ai_client_constructs_zero_arg_anthropic(monkeypatch) -> None:
    """`_client()` builds a bare `Anthropic()` — auth resolves from env / OAuth profile."""
    calls = {}
    fake = types.ModuleType("anthropic")

    class _FakeAnthropic:
        def __init__(self, *args, **kwargs):
            calls["args"] = args
            calls["kwargs"] = kwargs

    fake.Anthropic = _FakeAnthropic
    monkeypatch.setitem(sys.modules, "anthropic", fake)

    ai._client()
    assert calls == {"args": (), "kwargs": {}}  # no hardcoded api_key


# --- rewrite ----------------------------------------------------------------------


def _fake_response(text: str):
    """Mimic a Messages API response: a list of content blocks, some of type 'text'."""
    return types.SimpleNamespace(
        content=[
            types.SimpleNamespace(type="thinking", thinking="…"),  # ignored
            types.SimpleNamespace(type="text", text=text),
        ]
    )


def test_ai_rewrite_builds_request(mocker) -> None:
    client = mocker.Mock()
    client.messages.create.return_value = _fake_response("  переписано под менеджера ")
    mocker.patch.object(ai, "_client", return_value=client)

    out = ai.rewrite(
        "TGN-9 закрыт, деплой на прод",
        style="нетехнический менеджер: без жаргона",
        model="claude-sonnet-5",
        language="Russian",
    )

    assert out == "переписано под менеджера"  # trimmed, only text blocks
    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["model"] == "claude-sonnet-5"
    assert "нетехнический менеджер" in kwargs["system"]
    assert "Russian" in kwargs["system"]
    assert kwargs["messages"] == [
        {"role": "user", "content": "TGN-9 закрыт, деплой на прод"}
    ]


def test_ai_rewrite_defaults_to_opus(mocker) -> None:
    client = mocker.Mock()
    client.messages.create.return_value = _fake_response("x")
    mocker.patch.object(ai, "_client", return_value=client)

    ai.rewrite("note", style="tech lead")
    assert client.messages.create.call_args.kwargs["model"] == ai.DEFAULT_MODEL
    assert ai.DEFAULT_MODEL == "claude-opus-5"


def test_ai_rewrite_wraps_sdk_errors(mocker) -> None:
    client = mocker.Mock()
    client.messages.create.side_effect = RuntimeError("429 rate limited")
    mocker.patch.object(ai, "_client", return_value=client)

    with pytest.raises(ai.AIError):
        ai.rewrite("note", style="tech lead")


def test_ai_rewrite_empty_response_raises(mocker) -> None:
    """A response with no text blocks is an AIError, not a silent empty send."""
    client = mocker.Mock()
    client.messages.create.return_value = types.SimpleNamespace(content=[])
    mocker.patch.object(ai, "_client", return_value=client)

    with pytest.raises(ai.AIError):
        ai.rewrite("note", style="tech lead")
