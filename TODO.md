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
- **TGN-13/14 done + release prepped (this branch):** plugin/marketplace manifests
  (`.claude-plugin/`), `claude plugin validate . --strict` passes; version single-sourced
  from `tg_notes/__init__.py` and bumped to `0.1.0`; `python -m build` produces a clean
  sdist+wheel (`twine check` PASSED); `release.yml` switched to PyPI Trusted Publishing.
- Logged TGN-18 (pluggable secrets backend — Secret Service/keyring incl. KeePassXC,
  `StringSession` in the vault) as later work; the file backend stays the default.
- **NEXT — TGN-12 publish (gated, outward, needs the user):** one-time PyPI Trusted
  Publisher for `tg-notes` bound to `korkin25/tg_notes` (workflow `release.yml`, env
  `pypi`), then `git tag v0.1.0 && git push --tags` → CI builds & publishes. Do NOT publish
  without an explicit go. After that: TGN-15 (community marketplace, later), TGN-17 (MCP,
  optional).

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
| TGN-12 | 🟡 | Publish CLI to PyPI | Repo prepped (0.1.0, single-source version, `release.yml` → Trusted Publishing, build+`twine check` green). Remaining (gated, needs user): PyPI Trusted Publisher for `tg-notes`↔`korkin25/tg_notes`, then tag `v0.1.0`. Decided (was TGN-D1). |
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
