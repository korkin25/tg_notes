# CLAUDE.md

Guidance for Claude Code (and other AI agents) working in this repository.

## What this project is

`tg_notes` — a general-purpose **notes → compile → publish** tool that uses a private
Telegram forum group as its store and posts under the user's own account (userbot).
Daily work reports are one preset built on top of it.

Architecture in one line: a standalone Python CLI (`tg-notes`, Telethon/MTProto) does
all Telegram I/O; thin per-agent Skill wrappers (Claude Code first) add the
intelligence (composing notes, compiling them per recipient). See
[docs/architecture.md](docs/architecture.md).

Status: **planning** — no implementation yet. The plan lives in [TODO.md](TODO.md).

## Language rules (STRICT)

- **All repository content is English** — code, identifiers, comments, commit
  messages, and every document (README, `docs/`, CHANGELOG, TODO, this file).
  No exceptions.
- **Conversation with the user in Claude chats is always Russian.**
- The two are independent: reason and reply to the user in Russian, but everything
  written into the repo is English.

## Documentation sync (apply without being asked)

Keep docs in lockstep with the code, **in the same change**:

| What changed | Update |
|---|---|
| New or changed feature / behavior | `docs/features.md` + `README.md` |
| CLI surface (commands, flags) | `README.md` (usage) + `docs/architecture.md` |
| Architecture, storage schema, data flow, security model | `docs/architecture.md` |
| Any user-visible change | `CHANGELOG.md` under `## [Unreleased]` |
| Task started / finished / blocked | `TODO.md` status |

- `CHANGELOG.md` follows [Keep a Changelog](https://keepachangelog.com/) + SemVer.
- `TODO.md` holds only open/in-progress work; when a task is done and verified, move
  it out of `TODO.md` into `CHANGELOG.md`.
- Never mark a task done without confirmation that it actually works.

## Conventions

- **Secrets never leave the machine.** `api_id`/`api_hash`, the Telethon `*.session`
  file, and local config are git-ignored. **Notes and contacts live only in Telegram.**
- The session file grants full account access: `chmod 600`, never committed.
- Userbot automation is a Telegram-ToS gray area; the tool only publishes the user's
  own notes/reports and must stay non-spammy.

## Git

- Do **not** run `git commit` — the user commits themselves.
- Do not add a `Co-Authored-By` trailer for the AI agent.
