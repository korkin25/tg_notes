# TODO

Single list of **open** work on `tg_notes` (statuses ⬜/🟡). Architecture and design
live in `docs/`; stages, current status, and checklists are tracked here. Done tasks
(✅) move to [CHANGELOG.md](CHANGELOG.md) — see the rule below.

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

## Open decisions

| ID | Status | Decision | Details |
| --- | --- | --- | --- |
| TGN-D1 | ⬜ | CLI distribution: PyPI + pipx vs. bundled venv | Recommended: publish `tg-notes` to PyPI, the skill runs `pipx install tg-notes`. Alternative: bootstrap a venv inside the skill (as in the prototype). |
| TGN-D2 | ⬜ | Storage-group discovery | Keep the group id in local config, or resolve it by a well-known title? Config is simpler and explicit. |
| TGN-D3 | ⬜ | Verify the Agent Skills `SKILL.md` standard | Confirm the spec source and which runtimes actually consume it before relying on cross-agent portability. |
| TGN-D4 | ⬜ | License | Pick a license (MIT / Apache-2.0 / …) and add `LICENSE`. |

## Phase 1 — CLI core (`tg-notes`)

| ID | Status | Task | Details |
| --- | --- | --- | --- |
| TGN-1 | ⬜ | Project scaffolding | `pyproject.toml`, package layout (`tg_notes/`), CLI entrypoint, local config loader, `.gitignore` for secrets and `*.session`. |
| TGN-2 | ⬜ | Telegram client layer | Telethon client with the sync wrapper, one-time interactive login, session handling (`chmod 600`). |
| TGN-3 | ⬜ | `tg-notes setup` | Create or attach a private forum supergroup; ensure the `contacts` topic and a default notebook; persist the group id in local config. |
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
| TGN-12 | ⬜ | Publish CLI to PyPI | Depends on TGN-D1. |
| TGN-13 | ⬜ | Claude plugin packaging | `.claude-plugin/plugin.json`, skill path, `${CLAUDE_PLUGIN_ROOT}` for bundled paths. |
| TGN-14 | ⬜ | Git plugin marketplace | `.claude-plugin/marketplace.json`; document `/plugin marketplace add` and install. |
| TGN-15 | ⬜ | Submit to community marketplace | Validate with `claude plugin validate .`, then submit via the console form. Later. |

## Phase 4 — Multi-agent portability

| ID | Status | Task | Details |
| --- | --- | --- | --- |
| TGN-16 | ⬜ | `AGENTS.md` + other-agent wrappers | Canonical rules in `AGENTS.md`; thin wrappers for opencode / Hermes once TGN-D3 is confirmed. |
