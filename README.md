# tg_notes

Turn a private Telegram group into your notes store, then publish tailored updates
**under your own account**. Capture notes from anywhere — any AI-agent chat, the CLI,
or your phone — and compile a subset into a per-recipient view that gets posted as
you, into a real chat or forum topic. Daily work reports are one built-in preset.

> **Status: planning.** No implementation yet. See [TODO.md](TODO.md) for the plan and
> [docs/architecture.md](docs/architecture.md) for the design.

## Why

- **Your notes live in Telegram** — private, synced, reachable from your phone.
  Nothing is stored in local files.
- **Posts go out as you.** Delivery uses the Telegram client API (userbot), so an
  update can land in a real work group or topic under your own name, not a bot's.
- **Small CLI, portable Skill.** A single CLI does the Telegram work; AI-agent Skills
  (Claude Code first) drive it and do the writing/summarizing. The Skill is meant to
  be reused across other agent runtimes.

## Features

- Notes stored in a private Telegram forum group; one topic per notebook.
- A dedicated contacts topic acts as the address book (one message per contact).
- Compile a subset of notes into a recipient-specific view and post it as you.
- Per-contact style (e.g. verbatim technical for a lead, simplified for a manager).
- Post to a plain chat or a specific forum topic; optional mention.
- Daily work-report preset.

Full list: [docs/features.md](docs/features.md).

## How it works

A private **forum supergroup** is the store:

- `contacts` topic — the address book (chat/topic/style per recipient).
- one topic per **notebook** — the raw notes for a stream (project, audience, …).

The `tg-notes` CLI creates/attaches the group, appends notes, lists them for an agent
to compile, and publishes the result. See [docs/architecture.md](docs/architecture.md).

## Install & usage

The CLI will ship on PyPI; the Claude Code Skill will ship as a plugin installable from a
git marketplace. More usage lands here as commands are implemented.

Available so far:

```bash
# One-time interactive login (prompts for phone number, code, and 2FA if enabled).
# Requires api_id/api_hash in local config; writes a chmod-600 session file.
tg-notes login

# Print the logged-in account identity (id / username / first name).
tg-notes whoami
```

## Security & Telegram ToS

- Userbot automation is a **gray area of Telegram's ToS**; you run it on your own
  account at your own risk. The tool only publishes your own notes and reports.
- The Telethon session file grants **full access to your account**: it is `chmod 600`
  and never committed. `api_id`/`api_hash` and local config stay on your machine.

## License

[GPL-3.0](LICENSE).
