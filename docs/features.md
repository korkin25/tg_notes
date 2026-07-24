# Features

> Planned. Nothing is implemented yet — see [../TODO.md](../TODO.md) for status.

## Core

1. **Telegram-native storage.** Notes live in a private Telegram forum group; nothing
   is kept in local files.
2. **Posts as you.** Delivery uses the Telegram client API (userbot), so updates land
   under the user's own account — including in group chats and forum topics.
3. **Notebooks = topics.** Each note is filed into a chosen notebook topic (per project,
   audience, or any stream).
4. **Media notes.** A note can be a media file, not just text —
   `tg-notes note add --file <path> [--caption <text>]` uploads a photo, video, audio, or
   document into the notebook topic as native Telegram media (Telethon auto-detects the
   kind). The `--caption` is the note's searchable text; `notes list` reports each note's
   media type and returns the caption as its `text`. (Phase 2 will auto-fill the caption of
   an audio note from its transcription.)
5. **Address book in Telegram.** A dedicated `contacts` topic holds one message per
   contact (chat, topic, mention, style); editable from the phone.
6. **Compile & publish.** Turn a subset of notes into a recipient-specific view and post
   it.
7. **Per-contact style.** Verbatim technical for a lead, simplified business language for
   a manager, etc. — driven by the contact's `style` prompt.
8. **Flexible targets.** Deliver to a plain chat or a specific forum topic, with an
   optional mention.

## Presets

9. **Daily work report.** Collect the day's notes, compile them, and send — one command
   on top of the core.

## Tooling & distribution

10. **Standalone CLI (`tg-notes`).** Does all Telegram I/O; usable on its own or from a
    scheduler. `tg-notes setup` provisions the store idempotently — creates or attaches
    the private forum supergroup, ensures the `contacts` topic and a default notebook,
    and pins a recovery marker so the group can be re-found if local config is lost.
11. **Agent Skills.** Drive the CLI and do the writing/summarizing — Claude Code first,
    portable to other agent runtimes.
12. **Easy to install.** Distributable as a Claude plugin via a git marketplace; the CLI
    via PyPI.
13. **Interactive pickers.** Omitting the selected value on a human terminal opens a
    chooser — `send --contact`, `contacts remove`, `secrets migrate --to`, and `notes list
    --notebook` — using a fuzzy finder (`fzf`/`sk`/`fzy`) when installed, else a numbered
    menu. It engages only when both stdin and stdout are TTYs and the value was omitted, so
    scripted/agent invocations that pass the flag are unaffected.
