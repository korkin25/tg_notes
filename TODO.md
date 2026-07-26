# TODO

Single list of **open** work on `tg_notes` (statuses ⬜/🟡). Architecture and design
live in `docs/`; stages, current status, and checklists are tracked here. Done tasks
(✅) move to [CHANGELOG.md](CHANGELOG.md) — see the rule below.

## Current state / next action

- **TGN-27 in progress** (2026-07-26): **adopt the `ai-project-template` engineering standard**
  (feature #25). Branch model migrated `main` → `dev`/`rc`/`release` (`dev` is default; `main`
  kept as legacy). Done on branch `feature/TGN-27-full-standard` off `dev`: CI recomposed on
  `korkin25/open-ci-actions@v1` (+ bespoke `live-functional`), `GitVersion.yml`, slimmed
  functional script, universal agent-rule symlinks + `.claude/settings.json` hook +
  `.cursor/rules/project.mdc`, `CLAUDE.md` hardened (context-map router / Versioning /
  Safe-autonomy / Agent-security / Design-before-code / cross-agent portability), `doc-sync.yml`,
  Dependabot, pre-commit (gitleaks-only), CODEOWNERS, PR/issue templates, SECURITY/CONTRIBUTING/
  CoC, `.gitlab-ci.yml`. **Next:** push branch → PR to `dev` → analyze CI logs (even if green) →
  merge with `--no-ff` once green. Then apply the same standard to `jira_nano`.
- **TGN-26 in progress** (2026-07-25): **fan-out forward with per-recipient AI rewriting**
  (feature #24, decision Hybrid A+B). Phase A extends the `tg-notes-send` skill to a
  multi-recipient flow (subscription, no keys). Phase B adds a headless **`tg-notes fanout`**
  + optional `tg_notes/ai.py` (Anthropic via `ant auth login` OAuth profile, `tg-notes[ai]`
  extra, default `claude-opus-5`). Branch `feature/TGN-26-fanout-ai-rewrite` off `main`.
- **TGN-25 done + merged** (2026-07-25, PR #2 → `main`): CI **live-functional** suite — the
  full data path via **CLI + MCP** (setup/doctor/whoami, text+media note add, notes/notebooks
  list, contacts CRUD, send dry-run + real self-send) against a dedicated test account+group,
  green in CI (19 live tests). `scripts/sandbox.py` gained an env-credential source;
  `scripts/cleanup_live.py` purges the group each run; secure-store is a dev-machine group-(b)
  test. Secrets `TG_NOTES_API_ID/API_HASH/SESSION` + var `TG_NOTES_TEST_GROUP=-1004422788484`
  set in the `ci-functional` environment. In `CHANGELOG.md` (`[Unreleased]`).
- **TGN-23 + TGN-24 done** (2026-07-25): containerisation + GHCR + CI suite. Added
  `tg-notes-mcp-http` (streamable-HTTP, TDD), multi-stage `Dockerfile`, `docker-compose.yml`
  + `docker-compose.voice.yml`, Helm `chart/` (Deployment + config/voice PVCs, optional
  daily-report CronJob), `docs/configuration.md`, and a full CI suite (checkov/hadolint/
  trivy/semgrep/radon-xenon + functional MCP-HTTP job) that pushes image & OCI chart to GHCR.
  `helm lint`/`template`, Docker build, MCP-HTTP boot, full pytest (324) all validated. In
  `CHANGELOG.md` (`[Unreleased]`).
- **TGN-22 done** (2026-07-25): governance docs mirrored with `jira_nano` — `CLAUDE.md`
  now carries the Documentation-sync table, the Testing policy (groups a/b/c, TDD-first,
  release gate) and the MANDATORY Per-task lifecycle; user-facing features documented in
  `README.md` `## Features`;
  `docs/tests.md` + `auto-tests/` scaffolds added. In `CHANGELOG.md` (`[Unreleased]`).
- **Release `0.1.2` cut** (2026-07-25): whisper engine auto-fetch on first use
  (`transcribe.ensure_engine`, best-effort, once per process, `pipx inject` vs `pip install`
  by context; disable with `transcriber_autoinstall = false`) + the `scripts/sandbox.py`
  testing helper rolled from `## [Unreleased]` into `## [0.1.2]`; version bumped in
  `tg_notes/__init__.py` + the plugin manifests. Maintainer tags `v0.1.2` for the
  Trusted-Publishing workflow.
- **Release `0.1.1`** (2026-07-25): **published to PyPI** via the Trusted-Publishing workflow
  on the `v0.1.1` tag. The **media feature is complete** and **TGN-1..21 are all done** (in
  `CHANGELOG.md`). Only optional **TGN-15** (community-marketplace submission, a user web
  action) remains open.
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
- **Media notes — Phases 1, 2 & 3 ALL DONE (TGN-19, TGN-20, TGN-21)**, in `CHANGELOG.md`.
  Phase 1: `tg-notes note add --file <path> [--caption <text>]` uploads
  photo/video/audio/document as native Telegram media; `notes_list` reports each note's
  `media` type + caption. Phase 2: audio note files **auto-transcribe to the caption** via a
  pluggable local transcriber (`tg_notes/transcribe.py`), best-effort. Phase 3: the MCP server
  gains a `note_add_file` tool (same best-effort audio transcription as the CLI), the capture
  skill documents media capture, and the keyring backend self-heals `DBUS_SESSION_BUS_ADDRESS`
  so a sanitized-env spawn (MCP host / cron) can still reach the Secret Service. The media
  feature is now complete.
- Otherwise all earlier work is DONE. The only other open item is **TGN-15** (submit the
  plugin to a community marketplace) — a user web action, optional; the repo side already
  passes `claude plugin validate --strict` and the plugin installs from `korkin25/tg_notes`.

## Planned / ideas

Backlog and brainstorm items (formerly a separate numbered backlog file, now removed).
Delivered, user-facing features live in `README.md`'s `## Features`; release history is in
`CHANGELOG.md`.

- **Fan-out forward with per-recipient AI rewriting** — deliver one source (a note or a
  notebook's notes) to **several contacts at once**, each rewritten for that recipient's level
  via their `style` (business summary for a manager, verbatim-technical for a tech lead).
  Hybrid A+B design. In progress as **TGN-26** (see *Phase 6* below).
- **Community-marketplace listing** — submit the Claude plugin to a community marketplace
  (a user web action; the repo side already passes `claude plugin validate . --strict` and
  git-installs from `korkin25/tg_notes`). Tracked as **TGN-15** (see *Phase 3* below).
- _Brainstorm: none yet._

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

_Media notes — Phases 1, 2 & 3 (TGN-19, TGN-20, TGN-21) are all done and in `CHANGELOG.md`;
the media feature is complete. The only open item is optional TGN-15
(community-marketplace submission, a user web action)._

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

## Phase 5 — CI live-functional (TGN-25)

Promote the gated live Telegram tests to run **under CI** against a dedicated test
account, so `setup` / `doctor` / data round-trips are exercised on every push once the
`ci-functional` secrets are set. Credentials are sourced from the environment; nothing
touches the real store (`-1004432534270`).

| ID | Status | Task | Details |
| --- | --- | --- | --- |
| TGN-25a | ✅ | Env-credential source in `scripts/sandbox.py` | `_read_ci_credentials()` reads `TG_NOTES_API_ID/HASH/SESSION[/TEST_GROUP]`; `_provision_sandbox` uses it when present, else the local keyring recipe. Mocked unit tests (group-a) green; CI seeding verified end-to-end locally. |
| TGN-25b | ✅ | Full CLI coverage — `tests/test_live_functional.py` | Every command: `setup`, `secrets status`/`doctor`, `whoami`, text+media `note add`, `notes list`, `notebooks list`, `contacts` CRUD, `send` dry-run **and** a real self-send (cleaned up). Guards the real store id. **12/12 green in CI** against the dedicated group `-1004422788484`. |
| TGN-25c | ✅ | MCP coverage — `tests/test_live_mcp.py` | Same data path through the MCP tools. **5/5 green in CI.** |
| TGN-25d | 🟡 | Secure-store (keyring) — `tests/test_live_secure_store.py` | file→keyring→file migration + `whoami` from the vault. **Group-(b)**, dev-machine only (no Secret Service in CI); opt-in `TG_NOTES_LIVE_KEYRING=1`. To be run on the maintainer's laptop. |
| TGN-25e | ✅ | CI job `live-functional` (env `ci-functional`) | Seeds config from the env secrets; runs functional+mcp+media via `sandbox.py pytest`; skips (exit 0) when `TG_NOTES_SESSION` is empty. Secrets + `TG_NOTES_TEST_GROUP=-1004422788484` set; **full suite (19) green in CI**. |
| TGN-25f | ✅ | Cleanup — `scripts/cleanup_live.py` | `purge` the test notebooks / `group` teardown; refuses the real store. Runs as an **always-run** CI step; mocked unit tests green; purged 24 stray notes locally. |
| TGN-25g | ✅ | Merge | PR #2 merged to `main` with a merge commit (CI green); recorded in `CHANGELOG.md`. |

## Phase 6 — Fan-out AI-rewrite forward (TGN-26, feature #24)

Deliver one source to several contacts at once, each rewritten per their `style`. Decision:
**Hybrid A+B** (skill layer for interactive; CLI-native `fanout` for headless/cron).

| ID | Status | Task | Details |
| --- | --- | --- | --- |
| TGN-26a | 🟡 | `tg_notes/ai.py` (Phase B core) | `rewrite(text, style, *, model, language)` via the Anthropic SDK, **lazy import**; auth from an `ant auth login` OAuth profile or `ANTHROPIC_API_KEY` (no static key). `available()` + `AIUnavailable`/`AIError`. Mocked unit tests (group-a). |
| TGN-26b | 🟡 | CLI `tg-notes fanout` (Phase B) | `--contact` (repeatable), `--notebook`/`--since`, `--rewrite/--no-rewrite` (auto), `--model`, `--dry-run`. Reads notes → per-contact rewrite (best-effort; falls back to raw) → `send` each. Mocked unit tests; new `ai_model` config + `[ai]` extra. |
| TGN-26c | 🟡 | Skill fan-out (Phase A) | `skills/tg-notes-send/SKILL.md`: first-class multi-recipient flow (pick contacts → per-`style` drafts → one confirmation → send each), using Claude Code auth; points at the headless `fanout` alternative. |
| TGN-26d | ⬜ | Live (group-b) + docs | Live `fanout` on a dev machine with an OAuth profile against self-contacts (methodology in `auto-tests/group-b/`); README + `docs/configuration.md` + `CHANGELOG.md`; CI green; PR → `main`. |

## Deferred

_None — TGN-18 (pluggable secrets backend) is done, in `CHANGELOG.md`._
