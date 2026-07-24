# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Project documentation and rules: `README.md`, `CLAUDE.md` (language and doc-sync
  rules), `docs/architecture.md`, `docs/features.md`.
- Implementation plan in `TODO.md` (planning phase; no code yet).
- `GPL-3.0` license (`LICENSE`).
- Project scaffolding (TGN-1): `pyproject.toml` (CLI `tg-notes`, Telethon dependency,
  editable-installable), `tg_notes` package, argparse command tree (`setup`, `note add`,
  `notes list`, `contacts list/set/remove`, `send`, `notebooks list` — stubs so far),
  local TOML config module (XDG path, `chmod 600`), and `.gitignore` for secrets and
  `*.session`.
- Autonomous development-workflow rules in `CLAUDE.md` (TDD-first, feature branches,
  Conventional Commits, tag-based SemVer releases, CI expectations, security bar),
  replacing the previous minimal `Git` section.
- GitHub Actions workflows: CI (`.github/workflows/ci.yml`) running ruff, pytest
  (Python 3.11 and 3.12), bandit, and pip-audit on every push and pull request; and
  release (`.github/workflows/release.yml`) building and publishing to PyPI on `v*` tags.
- `dev` optional-dependency group in `pyproject.toml` (`pytest`, `pytest-mock`, `ruff`,
  `bandit`, `pip-audit`, `build`).
- `AGENTS.md` pointing agents to `CLAUDE.md` as the canonical rules and documenting the
  Agent Skills (`SKILL.md`) portability standard.
- Telegram client layer (TGN-2): `tg_notes/telegram.py` — a synchronous Telethon wrapper
  (`import telethon.sync`) with `build_client` / `connect_authorized` / `whoami` / `login`
  and typed `NotConfiguredError` / `NotAuthorizedError`. Sessions are locked to `chmod 600`
  after login.
- CLI commands `login` (one-time interactive phone/code/2FA login, stores the session) and
  `whoami` (prints the logged-in account identity as JSON); both report missing credentials
  or an unauthorized session with a clear message and a nonzero exit.
- Test suite under `tests/` (pytest + pytest-mock): config round-trip / file mode / session
  path, the Telegram layer with Telethon fully mocked (offline), and the CLI argument
  surface. Pytest and ruff config added to `pyproject.toml`.
- Storage provisioning (TGN-3): `tg-notes setup` creates (or idempotently attaches to) the
  private forum supergroup that stores notes. It ensures the `contacts` topic and a default
  `daily` notebook topic (override with `--notebook`), pins a recovery marker in the group
  so a lost store can be re-discovered, and persists the resolved group id to local config.
  New `telegram.setup` plus helpers (`_resolve_or_create` / `_create_storage_group` /
  `_ensure_topics` / `_pin_marker`) built on Telethon's forum raw API
  (`CreateChannelRequest(megagroup=True, forum=True)`, `CreateForumTopicRequest`,
  `GetForumTopicsRequest`); tests in `tests/test_setup.py` with Telethon fully mocked.
  When Telegram is not usable yet, `setup` self-instructs instead of failing tersely:
  missing credentials print step-by-step onboarding (get api_id/api_hash at
  my.telegram.org, where to save them, `chmod 600`, `tg-notes login`, re-run), and a
  missing login points at `tg-notes login`.
