# Features

> Planned. Nothing is implemented yet — see [../TODO.md](../TODO.md) for status.

## Core

1. **Telegram-native storage.** Notes live in a private Telegram forum group; nothing
   is kept in local files.
2. **Posts as you.** Delivery uses the Telegram client API (userbot), so updates land
   under the user's own account — including in group chats and forum topics.
3. **Notebooks = topics.** Each note is filed into a chosen notebook topic (per project,
   audience, or any stream).
4. **Address book in Telegram.** A dedicated `contacts` topic holds one message per
   contact (chat, topic, mention, style); editable from the phone.
5. **Compile & publish.** Turn a subset of notes into a recipient-specific view and post
   it.
6. **Per-contact style.** Verbatim technical for a lead, simplified business language for
   a manager, etc. — driven by the contact's `style` prompt.
7. **Flexible targets.** Deliver to a plain chat or a specific forum topic, with an
   optional mention.

## Presets

8. **Daily work report.** Collect the day's notes, compile them, and send — one command
   on top of the core.

## Tooling & distribution

9. **Standalone CLI (`tg-notes`).** Does all Telegram I/O; usable on its own or from a
   scheduler. `tg-notes setup` provisions the store idempotently — creates or attaches
   the private forum supergroup, ensures the `contacts` topic and a default notebook,
   and pins a recovery marker so the group can be re-found if local config is lost.
10. **Agent Skills.** Drive the CLI and do the writing/summarizing — Claude Code first,
    portable to other agent runtimes.
11. **Easy to install.** Distributable as a Claude plugin via a git marketplace; the CLI
    via PyPI.
