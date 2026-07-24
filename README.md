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

Two pieces: the **CLI** (does the Telegram I/O) and the **Claude Code plugin** (the skills
that drive it).

```bash
# CLI — from PyPI (once published; see CHANGELOG for release status):
pipx install tg-notes

# Plugin (bundles the tg-notes and tg-notes-send skills) — from this git marketplace:
#   /plugin marketplace add korkin25/tg_notes
#   /plugin install tg-notes@tg-notes-marketplace
```

The skills drive the CLI, so `tg-notes` must be on `PATH`. The two skills:
- [`skills/tg-notes/`](skills/tg-notes/SKILL.md) — **capture**: compose a note (verbatim or
  a summary of real session facts) and file it with `tg-notes note add`.
- [`skills/tg-notes-send/`](skills/tg-notes-send/SKILL.md) — **compile & send**: rewrite
  stored notes per a contact's style, confirm, and publish with `tg-notes send` (daily
  report is a preset).

For agent hosts that can't shell out (Claude Desktop, …), a local **stdio MCP server**
exposes the same core (`note_add` / `notes_list` / `contacts_list` / `send`):

```bash
pipx install "tg-notes[mcp]"   # then point your MCP client at the `tg-notes-mcp` command
```

It runs over stdio only — the session and secrets never leave the machine.

Available so far:

```bash
# One-time: create (or attach to) the private forum supergroup that stores your notes.
# On first run it walks you through onboarding — prompts for your api_id/api_hash
# (get them at https://my.telegram.org), saves them to local config (chmod 600), and
# runs the interactive login (phone → code → 2FA). Then it ensures the `contacts` topic
# and a default `daily` notebook, pins a recovery marker, and saves the group id.
# Idempotent — safe to re-run.
tg-notes setup [--notebook <name>]

# Append a note to a notebook topic (creates the topic on demand). Read the text from a
# file or from stdin (-); attach optional #hashtags. Prints the posted note as JSON.
tg-notes note add --notebook daily --text-file note.txt --hashtag infra
echo "quick note" | tg-notes note add --text-file -

# Or attach a media file (photo/video/audio/document) as the note — stored as native
# Telegram media in the topic, kind auto-detected. --caption is the searchable text (any
# --hashtag is appended to it); Phase 2 will auto-fill it from audio transcription.
tg-notes note add --notebook daily --file ~/clips/demo.mp4 --caption "walkthrough" --hashtag demo

# List the raw notes of a notebook (oldest first) as JSON, optionally bounded by --since
# (today | HH:MM | YYYY-MM-DD | ISO datetime; local when no offset). Feeds compilation.
tg-notes notes list --notebook daily --since today

# Address book (one message per contact in the `contacts` topic). `set` creates or
# updates (only the given fields change; a new contact needs --chat-id). List/remove
# print JSON. chat_id is -100… | @username | me.
tg-notes contacts set boss --chat-id @alice --name Alice --style "verbatim technical"
tg-notes contacts list
tg-notes contacts remove boss

# Publish compiled text to a contact's chat, as you — into a forum topic when the contact
# has a topic_id, prepending its mention if set. Text from a file or stdin (-). Use
# --dry-run to print exactly what would be sent without sending.
tg-notes send --contact boss --text-file report.txt
echo "..." | tg-notes send --contact boss --text-file - --dry-run

# List the storage group's notebook topics as JSON (excludes General/contacts).
tg-notes notebooks list

# Secrets backend. By default the api_hash + session live in local files (config.toml
# 600 + *.session). Optionally move them into the OS Secret Service (gnome-keyring /
# KWallet / KeePassXC — whichever owns org.freedesktop.secrets; the session is stored as
# a StringSession). `secrets status` shows the active backend and which provider answers.
pipx install "tg-notes[keyring]"
tg-notes secrets status
tg-notes secrets doctor                    # diagnose the store + get setup/migration steps
tg-notes secrets migrate --to keyring     # or: --to file to move back
# Using KeePassXC as the store (serve Secret Service, dedicated group, the
# confirmation trade-off): see docs/keepassxc.md. On Linux + keyring, the CLI re-execs
# through a named launcher so the vault prompt shows "tg-notes", not "python3.12".
# Test setup/doctor/migrate end-to-end against a throwaway isolated install
# (never touches the real config/session/vault): see docs/sandbox-testing.md.

# Log in on its own (setup calls this for you; useful to re-authorize a new device).
# Requires api_id/api_hash in local config; writes a chmod-600 session file.
tg-notes login

# Print the logged-in account identity (id / username / first name).
tg-notes whoami
```

Omit `--contact` / `--to` / `--notebook` in an interactive terminal to pick from a list
(uses `fzf`/`sk`/`fzy` if installed, else a numbered menu); with the flag or when piped,
behavior is unchanged.

## Security & Telegram ToS

- Userbot automation is a **gray area of Telegram's ToS**; you run it on your own
  account at your own risk. The tool only publishes your own notes and reports.
- The Telethon session file grants **full access to your account**: it is `chmod 600`
  and never committed. `api_id`/`api_hash` and local config stay on your machine.

## License

[GPL-3.0](LICENSE).
