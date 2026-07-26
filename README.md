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
- A note can be text or a media file (photo/video/audio/document) — uploaded as native
  Telegram media; audio notes auto-transcribe **locally** to a searchable caption
  (best-effort, pluggable whisper engine).
- A dedicated contacts topic acts as the address book (one message per contact).
- Compile a subset of notes into a recipient-specific view and post it as you.
- Per-contact style (e.g. verbatim technical for a lead, simplified for a manager).
- Post to a plain chat or a specific forum topic; optional mention.
- Daily work-report preset.
- Interactive pickers when a selection flag is omitted on a terminal (`fzf`/`sk`/`fzy`,
  else a numbered menu); scripted/agent calls that pass the flag are unaffected.

See [CHANGELOG.md](CHANGELOG.md) for the full release history; backlog and ideas live in
[TODO.md](TODO.md).

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
exposes the same core (`note_add` / `note_add_file` / `notes_list` / `contacts_list` /
`send`). `note_add_file` uploads a local file as a media note — audio auto-transcribes to
the caption, or the agent passes its own `caption` (e.g. an image description) to skip it:

```bash
pipx install "tg-notes[mcp]"   # then point your MCP client at the `tg-notes-mcp` command
```

It runs over stdio only — the session and secrets never leave the machine. When the host
spawns the server with a sanitized environment, the (opt-in) keyring backend self-heals
`DBUS_SESSION_BUS_ADDRESS` so it can still reach the Secret Service.

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
# --hashtag is appended to it).
tg-notes note add --notebook daily --file ~/clips/demo.mp4 --caption "walkthrough" --hashtag demo

# Audio notes auto-transcribe: when --file is audio (.ogg/.opus/.mp3/.m4a/.wav/…) and no
# --caption is given, tg-notes transcribes it LOCALLY and uses the transcript as the caption
# (searchable text) — best-effort, so if no engine is installed the file still uploads
# without a caption. On the first transcription with no engine, tg-notes auto-fetches the
# faster-whisper engine (once, best-effort; disable with transcriber_autoinstall = false).
# Or pre-install a local engine yourself (both need `ffmpeg` to decode audio):
#   pipx inject tg-notes faster-whisper        # the faster-whisper backend
#   # …or set whisper_cmd in config.toml to a whisper.cpp/openai-whisper binary
# whisper_model (e.g. base/small) picks the model (downloads on first use).
# Force/skip with --transcribe/--no-transcribe.
tg-notes note add --notebook daily --file ~/voice/idea.ogg          # caption ← transcript
tg-notes note add --notebook daily --file ~/voice/idea.ogg --no-transcribe

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

# Fan out a notebook's notes to several contacts at once, rewritten per each contact's
# style (business summary for a manager, verbatim-technical for a tech lead). Headless
# companion to the tg-notes-send skill (cron/daily-report). AI rewrite is best-effort and
# needs the `ai` extra + Anthropic credentials (see below); --no-rewrite sends the raw
# notes, --dry-run composes per contact without sending.
tg-notes fanout --contact manager --contact lead --notebook daily --since today
tg-notes fanout --contact manager --contact lead --dry-run
pipx install "tg-notes[ai]"        # optional: enables the AI rewrite (else falls back to raw)

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
