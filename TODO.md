# TODO

Single list of **open** work on `tg_notes` (statuses ⬜/🟡). Architecture and design
live in `docs/`; stages, current status, and checklists are tracked here. Done tasks
(✅) move to [CHANGELOG.md](CHANGELOG.md) — see the rule below.

## Current state / next action

- Branch: `feature/tgn-2`.
- TGN-1 (project scaffolding) — done, in `CHANGELOG.md`.
- **ACTIVE:** TGN-2 (Telethon client layer + one-time interactive login) — code and tests
  landed; the full suite is green (`pytest`, Telethon mocked/offline) and `ruff` is clean.
  Remaining before ✅: confirm an interactive `tg-notes login` against a real account.
- Next after TGN-2: TGN-3 (`tg-notes setup`).

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

| ID | Status | Task | Details |
| --- | --- | --- | --- |
| TGN-2 | 🟡 | Telegram client layer (TDD) | Client layer (`tg_notes/telegram.py`) + `login`/`whoami` CLI commands implemented; tests green (Telethon mocked) and ruff clean. Pending: verify interactive `login` against a real account before ✅. See Phase 1. |

## Phase 1 — CLI core (`tg-notes`)

| ID | Status | Task | Details |
| --- | --- | --- | --- |
| TGN-2 | ⬜ | Telegram client layer | Telethon client with the sync wrapper, one-time interactive login, session handling (`chmod 600`). |
| TGN-3 | ⬜ | `tg-notes setup` | Create or attach a private forum supergroup; ensure the `contacts` topic and a default notebook; persist the group id in local config; tag the group (fixed title + pinned marker) for recovery (TGN-D2). |
| TGN-4 | ⬜ | `tg-notes note add` | Append a note to a notebook topic (create the topic on demand); optional hashtags. |
| TGN-5 | ⬜ | `tg-notes notes list` | Fetch raw notes from a notebook within a time range (feeds compilation). |
| TGN-6 | ⬜ | Contacts (address book) | `contacts list/set/remove`; the message-per-contact schema in the `contacts` topic. |
| TGN-7 | ⬜ | `tg-notes send` | Post given text to a contact's chat/topic; optional mention; forum topic via `reply_to`. |
| TGN-8 | ⬜ | `tg-notes notebooks list` | List the notebook topics of the storage group. |

## Phase 2 — Claude Code Skill

| ID | Status | Task | Details |
| --- | --- | --- | --- |
| TGN-9 | ⬜ | `skills/tg-notes/SKILL.md` — capture | Compose a note from the current session and call `note add`. |
| TGN-10 | ⬜ | Compile & send flow | Read raw notes, rewrite per the contact `style`, confirm with the user, call `send`. |
| TGN-11 | ⬜ | Daily-report preset | Notes since 00:00 → compile → send. |

## Phase 3 — Packaging & distribution

| ID | Status | Task | Details |
| --- | --- | --- | --- |
| TGN-12 | ⬜ | Publish CLI to PyPI | Package `tg-notes` and publish to PyPI; the skill installs it via `pipx install tg-notes`. Decided (was TGN-D1). |
| TGN-13 | ⬜ | Claude plugin packaging | `.claude-plugin/plugin.json`, skill path, `${CLAUDE_PLUGIN_ROOT}` for bundled paths. |
| TGN-14 | ⬜ | Git plugin marketplace | `.claude-plugin/marketplace.json`; document `/plugin marketplace add` and install. |
| TGN-15 | ⬜ | Submit to community marketplace | Validate with `claude plugin validate .`, then submit via the console form. Later. |
| TGN-17 | ⬜ | Local MCP adapter | Expose the core as a local stdio MCP server (official mcp / FastMCP) alongside the CLI: tools note_add / notes_list / contacts_list / send. Same core, second frontend; broadens reach to GUI clients (Claude Desktop, ChatGPT) that cannot shell out. Session/secrets stay local (stdio only, not hosted). |

## Phase 4 — Multi-agent portability

| ID | Status | Task | Details |
| --- | --- | --- | --- |
| TGN-16 | ⬜ | `AGENTS.md` + other-agent portability | Add `AGENTS.md` (canonical cross-agent rules). Portability confirmed (was TGN-D3): the same `SKILL.md` is read unchanged by OpenCode and ~30 other Agent Skills runtimes, so no per-agent wrapper is needed for the skill — keep the frontmatter to the standard core (`name`, `description`), avoid Claude-only fields. Remaining: per-agent *distribution* only. OpenCode / OpenClaw discover `~/.claude/skills` from dirs (zero effort); Claude via plugin marketplace; Hermes (Nous Research `hermes-agent`) is agentskills.io-compatible but keeps skills in its own `~/.hermes/` store → import the same `SKILL.md` (no rewrite), and it can also call the `tg-notes` CLI via its terminal toolset / MCP. |
