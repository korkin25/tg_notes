"""Optional AI rewrite backend for tg-notes (TGN-26, feature #24).

Rewrites note text for one recipient's level via the Anthropic API — a business summary for a
manager, verbatim-technical for a tech lead, etc. This is the **headless** half of the fan-out
feature (the interactive half lives in the ``tg-notes-send`` skill and uses the agent's own
model, no key). Keeping it out of the core: the CLI works with no AI at all; ``fanout`` falls
back to the raw notes when this backend is unavailable.

Optional dependency + credentials:

- Install the SDK with the ``ai`` extra: ``pipx install "tg-notes[ai]"`` (or ``pip install
  anthropic``). The import is **lazy**, so tg-notes runs fine without it.
- Authenticate with an ``ant auth login`` OAuth profile (stored under ``~/.config/anthropic``;
  the SDK's zero-arg client picks it up) or ``ANTHROPIC_API_KEY``. **No key is ever baked into
  the repo or config** — a bare ``Anthropic()`` resolves whatever the environment provides. A
  consumer Claude.ai subscription is not an API credential; billing is through the Anthropic API.
"""
from __future__ import annotations

#: Default model — the most capable Opus. ``fanout`` may override per invocation / config.
DEFAULT_MODEL = "claude-opus-5"
#: Default output language (this project's user writes/reads Russian; see CLAUDE.md).
DEFAULT_LANGUAGE = "Russian"


class AIUnavailable(RuntimeError):
    """The ``anthropic`` extra is not installed (callers fall back to the raw text)."""


class AIError(RuntimeError):
    """The rewrite request failed (bad credentials, rate limit, empty response, …)."""


def available() -> bool:
    """True when the optional ``anthropic`` SDK can be imported."""
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def _client():
    """Construct a zero-arg Anthropic client (auth from env / OAuth profile).

    Raises:
        AIUnavailable: if the ``anthropic`` extra is not installed.
    """
    try:
        import anthropic
    except ImportError as exc:  # optional dependency
        raise AIUnavailable(
            "the 'ai' extra is not installed — `pipx install \"tg-notes[ai]\"` "
            "(or `pip install anthropic`)"
        ) from exc
    return anthropic.Anthropic()  # resolves ANTHROPIC_API_KEY or an `ant auth login` profile


def _system_prompt(style: str | None, language: str) -> str:
    """Build the per-recipient rewrite instruction from the contact's ``style``."""
    audience = style.strip() if style and style.strip() else "a general audience"
    return (
        f"You rewrite work notes for one recipient. Rewrite the notes the user sends, in "
        f"{language}, strictly for this recipient: {audience}. Preserve only facts present in "
        "the notes — invent nothing. Be concise, drop filler, and do not add a preamble or "
        "sign-off. Output only the rewritten message text."
    )


def rewrite(
    text: str,
    style: str | None,
    *,
    model: str = DEFAULT_MODEL,
    language: str = DEFAULT_LANGUAGE,
) -> str:
    """Rewrite ``text`` for a recipient described by ``style``; return the message text.

    Uses adaptive thinking on the given ``model``. Non-streaming — rewrites are short.

    Raises:
        AIUnavailable: if the ``anthropic`` extra is not installed.
        AIError: if the request fails or the model returns no text.
    """
    client = _client()
    try:
        response = client.messages.create(
            model=model,
            max_tokens=4000,
            thinking={"type": "adaptive"},
            system=_system_prompt(style, language),
            messages=[{"role": "user", "content": text}],
        )
    except AIUnavailable:
        raise
    except Exception as exc:
        raise AIError(str(exc)) from exc

    parts = [
        getattr(block, "text", "")
        for block in getattr(response, "content", [])
        if getattr(block, "type", None) == "text"
    ]
    out = "".join(parts).strip()
    if not out:
        raise AIError("the model returned no text")
    return out
