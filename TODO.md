# TODO

Single list of **open** work on `tg_notes` (statuses ⬜/🟡). Architecture and design
live in `docs/`; stages, current status, and checklists are tracked here. Done tasks
(✅) move to [CHANGELOG.md](CHANGELOG.md) — see the rule below.

## Current state / next action

- **TGN-25 in progress** (2026-07-25): CI **live-functional** job — run `setup` / `secrets
  doctor` / `whoami` / real data round-trips (note add→list, contacts set→list, notebooks
  list, send `--dry-run`) against a **dedicated test account + group** under GitHub Actions.
  Credentials come from the `ci-functional` environment secrets (`TG_NOTES_API_ID`,
  `TG_NOTES_API_HASH`, `TG_NOTES_SESSION`, `TG_NOTES_TEST_GROUP`); `scripts/sandbox.py` gains
  an env-credential source so `sandbox.py setup/pytest` seed a throwaway config from those
  vars via the file backend, and the gated `tests/test_live_functional.py` runs the flow.
  The job skips cleanly (exit 0) when the session secret is absent (forks / not-yet-configured).
- **TGN-23 + TGN-24 done** (2026-07-25): containerisation + GHCR + CI suite. Added
  `tg-notes-mcp-http` (streamable-HTTP, TDD), multi-stage `Dockerfile`, `docker-compose.yml`
  + `docker-compose.voice.yml`, Helm `chart/` (Deployment + config/voice PVCs, optional
  daily-report CronJob), `docs/configuration.md`, and a full CI suite (checkov/hadolint/
  trivy/semgrep/radon-xenon + functional MCP-HTTP job) that pushes image & OCI chart to GHCR.
  `helm lint`/`template`, Docker build, MCP-HTTP boot, full pytest (324) all validated. In
  `CHANGELOG.md` (`[Unreleased]`).
- **TGN-22 done** (2026-07-25): governance docs mirrored with `jira_nano` — `CLAUDE.md`
  now carries the Documentation-sync table, the Testing policy (groups a/b/c, TDD-first,
  release gate) and the MANDATORY Per-task lifecycle; features moved to root `Features.md`;
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
| TGN-25a | 🟡 | Env-credential source in `scripts/sandbox.py` | `_read_ci_credentials()` reads `TG_NOTES_API_ID/HASH/SESSION[/TEST_GROUP]`; `_provision_sandbox` uses it when present, else the local keyring recipe. Mocked unit tests (group-a). |
| TGN-25b | 🟡 | Gated `tests/test_live_functional.py` | `whoami`, `secrets doctor --json`, idempotent `setup`, note add→list, contacts set→list, notebooks list, `send --dry-run`; guards against the real store id. Runs only with `TG_NOTES_LIVE=1`. |
| TGN-25c | 🟡 | CI job `live-functional` (env `ci-functional`) | Seeds config from the env secrets, runs the gated suite via `sandbox.py pytest`; skips (exit 0) when `TG_NOTES_SESSION` is empty. |
| TGN-25d | ⬜ | Docs | `docs/configuration.md` + `docs/tests.md` + `Features.md` updated; verified green in CI once the maintainer sets the secrets. |

## Deferred

_None — TGN-18 (pluggable secrets backend) is done, in `CHANGELOG.md`._
