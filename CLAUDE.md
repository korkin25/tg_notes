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

- **All repository content is English** — code, identifiers, comments, docstrings,
  commit messages, and every document (README, `docs/`, CHANGELOG, TODO, this file).
  No exceptions.
- **Conversation with the user is always Russian** — reply in Russian regardless of
  the language they wrote in. This applies only to the live chat, never to anything
  written into the repo.

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

## Development workflow (autonomous — apply without being asked)

This project is developed by an AI agent under continuous, autonomous iteration.

- Test-driven: for every agreed feature write the tests FIRST (they must fail), then implement until green. No feature code without a test.
- Feature branches: work on feature/<task-id>-<slug> off main; merge to main only when the full suite is green.
- Commit periodically in small logical units, Conventional Commits (feat:, fix:, test:, docs:, chore:, ci:). Never add a Co-Authored-By trailer.
- Releases only after green tests: tag vX.Y.Z (SemVer) after the full suite passes on main. Publishing to PyPI or marketplaces is a separate, later, explicit step.
- CI on every push (GitHub Actions): ruff lint, pytest (3.11 and 3.12), security scan (bandit + pip-audit). A tag triggers the build/release job.
- Security first: no secrets in git; least privilege; treat the Telethon session / bot token as full-access credentials.
- High bar: type hints, docstrings, ruff-clean, meaningful tests. Work like a top-tier engineer + DevOps.
- Auto-logging: started/ongoing work goes to TODO.md (Current state + phase tables); completed and verified work moves to CHANGELOG.md, in the same change. Never mark a task done without a passing test.
- Cold-start: keep the top of TODO.md a "Current state / next action" block so a fresh session knows exactly what to do next.
