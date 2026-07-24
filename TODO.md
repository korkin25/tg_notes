# TODO

Single list of **open** work on `tg_notes` (statuses ⬜/🟡). Architecture and design
live in `docs/`; stages, current status, and checklists are tracked here. Done tasks
(✅) move to [CHANGELOG.md](CHANGELOG.md) — see the rule below.

## Current state / next action

- Branch: `main` (feature/packaging merged).
- **Phases 1 (CLI core) and 2 (the Claude Code Skill) are COMPLETE**, in `CHANGELOG.md`,
  each verified end-to-end on @korkin25. Commands: `setup/login/whoami/note add/notes
  list/contacts/send/notebooks list`; skills: `tg-notes` (capture), `tg-notes-send`
  (compile & send + daily preset). 121 tests green, ruff + bandit clean.
- **Dev-installed** (done): `tg-notes` on PATH via `~/.local/bin/tg-notes` → repo `.venv`;
  both skills symlinked into `~/.claude/skills`. They load in new Claude Code sessions.
- **TGN-13/14 done:** plugin/marketplace manifests (`.claude-plugin/`), `claude plugin
  validate . --strict` passes. Version single-sourced from `tg_notes/__init__.py`.
- **TGN-12 done — `tg-notes 0.1.0` PUBLISHED to PyPI** (<https://pypi.org/project/tg-notes/>,
  wheel + sdist) via the `release.yml` Trusted-Publishing workflow on the `v0.1.0` tag.
  The one-time pending publisher is now an active Trusted Publisher on the project, so
  future `v*` tags publish with no extra setup. `pipx install tg-notes` works.
- CI is green on GitHub (fixed a pip-audit false-positive on the runner's `setuptools`).
- Logged TGN-18 (pluggable secrets backend — Secret Service/keyring incl. KeePassXC,
  `StringSession` in the vault) as later work; the file backend stays the default.
- TGN-16 done (Phase 4). TGN-17 done (MCP server; also fixed a `contacts_set`
  unchanged-content bug).
- TGN-18 done: pluggable secrets backend (`tg_notes/secrets.py`) — file (default) +
  opt-in keyring (Secret Service; session as `StringSession`), `tg-notes secrets
  status|doctor|migrate`. Verified end-to-end on an isolated session copy (file → keyring →
  `whoami` from the vault → back to file); the real file default was left untouched.
- Vault-prompt-name launcher done (`tg_notes/relaunch.py`): on Linux + keyring the CLI
  re-execs through `<venv>/libexec/tg-notes` (interpreter copy; venv packages via
  `site.addsitedir` under `-S`) so the KeePassXC/Secret Service prompt shows `tg-notes`,
  not `python3.12`. Best-effort (read-only venv → skipped); fully mocked unit tests.
- **Media notes — Phase 1 DONE (TGN-19)**, in `CHANGELOG.md`: `tg-notes note add --file
  <path> [--caption <text>]` uploads photo/video/audio/document as native Telegram media;
  `notes_list` now reports each note's `media` type + caption. Next: **TGN-20** (Phase 2 —
  auto-fill an audio note's caption from transcription) and **TGN-21** (Phase 3 — surface
  media in the MCP server + skills, and the D-Bus/DBUS env fix). See the Media notes phase
  below.
- Otherwise all earlier work is DONE. The only other open item is **TGN-15** (submit the
  plugin to a community marketplace) — a user web action, optional; the repo side already
  passes `claude plugin validate --strict` and the plugin installs from `korkin25/tg_notes`.

## Legend

⬜ Planned · 🟡 In progress · ✅ Done → moved to `CHANGELOG.md`

## Maintenance rule

- As soon as a task becomes ✅, move its row from `TODO.md` into `CHANGELOG.md` under
  the matching `## [Unreleased]` subsection.
- If a section has no open tasks left after the move, delete it from `TODO.md`.
- Never mark a task ✅ without confirmation that it actually works.

## Task IDs

Tasks use local identifiers `TGN-<n>` (no external tracker). Reference them in
discussions, commits, and PRs. Numbering is mandatory and IDs are never reused.
Decision items use `TGN-D<n>`.

## Current work

_Media notes — Phase 1 (TGN-19) is done and in `CHANGELOG.md`. Open: TGN-20 / TGN-21
(media Phases 2–3, below) and optional TGN-15 (community-marketplace submission, a user
web action)._

## Media notes

Upload arbitrary media (photo/video/audio/document) as notes, read them back, and — later
— transcribe audio into the caption.

| ID | Status | Task | Details |
| --- | --- | --- | --- |
| TGN-19 | ✅ | Phase 1 — upload media notes | Done → `CHANGELOG.md`. `note add --file <path> [--caption <text>]`; `note_add_file` posts native Telegram media (kind auto-detected), `notes_list` reports `media` type + caption. Captions passed explicitly. |
| TGN-20 | ⬜ | Phase 2 — audio transcription | Auto-fill an audio/voice note's caption from its transcription (speech-to-text), so a dictated voice note becomes searchable text without a manual `--caption`. |
| TGN-21 | ⬜ | Phase 3 — media surfaces + env fix | Expose media upload in the MCP server (`mcp_server.py`) and the `tg-notes` capture skill; mirror the `notes_list` `media`/caption shape in those surfaces. Includes the D-Bus/DBUS environment fix for media I/O. |

## Phase 1 — CLI core (`tg-notes`)

Complete — all rows moved to `CHANGELOG.md`.

## Phase 2 — Claude Code Skill

Complete — all rows moved to `CHANGELOG.md`.

## Phase 3 — Packaging & distribution

| ID | Status | Task | Details |
| --- | --- | --- | --- |
| TGN-15 | 🟡 | Submit to community marketplace | Repo-side ready: `claude plugin validate . --strict` passes, plugin is git-installable from `korkin25/tg_notes`. Remaining is a **user web action** — submit via the Anthropic console/marketplace form. Later, optional. |

## Phase 4 — Multi-agent portability

Complete — TGN-16 (`AGENTS.md` + per-agent distribution) moved to `CHANGELOG.md`.

## Deferred

_None — TGN-18 (pluggable secrets backend) is done, in `CHANGELOG.md`._
