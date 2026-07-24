# TODO

Single list of **open** work on `tg_notes` (statuses ⬜/🟡). Architecture and design
live in `docs/`; stages, current status, and checklists are tracked here. Done tasks
(✅) move to [CHANGELOG.md](CHANGELOG.md) — see the rule below.

## Current state / next action

- Branch: `main` (feature/tgn-8 merged).
- **Phase 1 (CLI core) is COMPLETE.** TGN-1..TGN-8 done, in `CHANGELOG.md`, each verified
  end-to-end on the real account (@korkin25). Full command surface: `setup`, `login`,
  `whoami`, `note add`, `notes list`, `contacts list/set/remove`, `send`, `notebooks list`.
  121 tests green, ruff + bandit clean.
- TGN-8 verified live: notebooks list excludes `General`/`contacts`, sorts, picks up a new
  notebook; not-set-up → 4. Temp notebook cleaned up.
- **Phase 2 (the Claude Code Skill) is COMPLETE.** TGN-9 capture (`skills/tg-notes/`),
  TGN-10 compile & send + TGN-11 daily preset (`skills/tg-notes-send/`) — all verified live
  on the real account. Together they replace the retired `report`/`report-send` pair,
  Telegram-native. Their orphaned `~/.claude/report-send.*` config/session were deleted.
- Logged TGN-18 (pluggable secrets backend — Secret Service/keyring incl. KeePassXC,
  `StringSession` in the vault) as later work; the file backend stays the default.
- **NEXT (agreed): dev-install** so the skills work in the user's own sessions — symlink
  `skills/tg-notes` + `skills/tg-notes-send` into `~/.claude/skills`, and put `tg-notes`
  on PATH (`pipx install -e .` or symlink `.venv/bin/tg-notes` → `~/.local/bin`). Then
  Phase 3 packaging (TGN-12 PyPI, TGN-13/14 plugin + marketplace).

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
| TGN-12 | ⬜ | Publish CLI to PyPI | Package `tg-notes` and publish to PyPI; the skill installs it via `pipx install tg-notes`. Decided (was TGN-D1). |
| TGN-13 | ⬜ | Claude plugin packaging | `.claude-plugin/plugin.json`, skill path, `${CLAUDE_PLUGIN_ROOT}` for bundled paths. |
| TGN-14 | ⬜ | Git plugin marketplace | `.claude-plugin/marketplace.json`; document `/plugin marketplace add` and install. |
| TGN-15 | ⬜ | Submit to community marketplace | Validate with `claude plugin validate .`, then submit via the console form. Later. |
| TGN-17 | ⬜ | Local MCP adapter | Expose the core as a local stdio MCP server (official mcp / FastMCP) alongside the CLI: tools note_add / notes_list / contacts_list / send. Same core, second frontend; broadens reach to GUI clients (Claude Desktop, ChatGPT) that cannot shell out. Session/secrets stay local (stdio only, not hosted). |

## Phase 4 — Multi-agent portability

| ID | Status | Task | Details |
| --- | --- | --- | --- |
| TGN-16 | ⬜ | `AGENTS.md` + other-agent portability | Add `AGENTS.md` (canonical cross-agent rules). Portability confirmed (was TGN-D3): the same `SKILL.md` is read unchanged by OpenCode and ~30 other Agent Skills runtimes, so no per-agent wrapper is needed for the skill — keep the frontmatter to the standard core (`name`, `description`), avoid Claude-only fields. Remaining: per-agent *distribution* only. OpenCode / OpenClaw discover `~/.claude/skills` from dirs (zero effort); Claude via plugin marketplace; Hermes (Nous Research `hermes-agent`) is agentskills.io-compatible but keeps skills in its own `~/.hermes/` store → import the same `SKILL.md` (no rewrite), and it can also call the `tg-notes` CLI via its terminal toolset / MCP. |

## Deferred

| ID | Status | Task | Details |
| --- | --- | --- | --- |
| TGN-18 | ⬜ | Pluggable secrets backend | Abstract secret storage behind a backend interface: **file** (default — `config.toml` 600 + `*.session`) and an **opt-in Secret Service** backend via `keyring`/`secretstorage`, auto-detected when a provider is present (KeePassXC, gnome-keyring, KWallet; macOS Keychain / Windows Cred Manager). Store the Telethon session as a `StringSession` in the vault (highest-value secret) instead of a file. Must keep unattended runs working (scheduled daily-report): the default path never requires an interactive master-password unlock. Deferred by agreement. |
