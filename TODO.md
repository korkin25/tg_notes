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
- **NEXT (optional):** TGN-17 (local stdio MCP adapter), TGN-15 (submit to a community
  marketplace, later), TGN-16 (`AGENTS.md` cross-agent), TGN-18 (secrets backend). Core
  product (Phases 1–3) is shipped; remaining items are reach/hardening.

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

_None in progress. Next up: dev-install, then Phase 3 (packaging)._

## Phase 1 — CLI core (`tg-notes`)

Complete — all rows moved to `CHANGELOG.md`.

## Phase 2 — Claude Code Skill

Complete — all rows moved to `CHANGELOG.md`.

## Phase 3 — Packaging & distribution

| ID | Status | Task | Details |
| --- | --- | --- | --- |
| TGN-15 | ⬜ | Submit to community marketplace | Validate with `claude plugin validate .` (done — passes), then submit via the console form. Later. |
| TGN-17 | ⬜ | Local MCP adapter | Expose the core as a local stdio MCP server (official mcp / FastMCP) alongside the CLI: tools note_add / notes_list / contacts_list / send. Same core, second frontend; broadens reach to GUI clients (Claude Desktop, ChatGPT) that cannot shell out. Session/secrets stay local (stdio only, not hosted). |

## Phase 4 — Multi-agent portability

| ID | Status | Task | Details |
| --- | --- | --- | --- |
| TGN-16 | ⬜ | `AGENTS.md` + other-agent portability | Add `AGENTS.md` (canonical cross-agent rules). Portability confirmed (was TGN-D3): the same `SKILL.md` is read unchanged by OpenCode and ~30 other Agent Skills runtimes, so no per-agent wrapper is needed for the skill — keep the frontmatter to the standard core (`name`, `description`), avoid Claude-only fields. Remaining: per-agent *distribution* only. OpenCode / OpenClaw discover `~/.claude/skills` from dirs (zero effort); Claude via plugin marketplace; Hermes (Nous Research `hermes-agent`) is agentskills.io-compatible but keeps skills in its own `~/.hermes/` store → import the same `SKILL.md` (no rewrite), and it can also call the `tg-notes` CLI via its terminal toolset / MCP. |

## Deferred

| ID | Status | Task | Details |
| --- | --- | --- | --- |
| TGN-18 | ⬜ | Pluggable secrets backend | Abstract secret storage behind a backend interface: **file** (default — `config.toml` 600 + `*.session`) and an **opt-in Secret Service** backend via `keyring`/`secretstorage`, auto-detected when a provider is present (KeePassXC, gnome-keyring, KWallet; macOS Keychain / Windows Cred Manager). Store the Telethon session as a `StringSession` in the vault (highest-value secret) instead of a file. Must keep unattended runs working (scheduled daily-report): the default path never requires an interactive master-password unlock. Deferred by agreement. |
