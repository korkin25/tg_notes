# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- CI: upgrade `pip`/`setuptools` before `pip-audit` so it no longer flags the runner's
  incidental build tooling (`setuptools` PYSEC-2026-3447, absent on 3.12 but present on
  3.11), which was failing the pipeline. `tg-notes` does not depend on `setuptools`.

## [0.1.0] - 2026-07-24

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
  `setup` drives first-run onboarding itself: when `api_id`/`api_hash` are missing it
  prompts for them and saves them to local config (mode 600); when the device is not
  logged in it runs the interactive `login` (phone → code → 2FA) and retries the
  provisioning. If the prompt is left blank (or the values are unusable) it falls back to
  printing step-by-step manual guidance (my.telegram.org → config path → `chmod 600` →
  `login` → re-run) and exits nonzero.
- Note capture (TGN-4): `tg-notes note add --notebook <nb> --text-file <f>` appends a note
  to the notebook's forum topic, creating the topic on demand. Reads the note text from a
  file or stdin (`--text-file -`), appends optional `--hashtag TAG` tokens (repeatable) on
  a trailing line, refuses to post an empty note, and prints the posted note as JSON
  (`notebook` / `topic_id` / `message_id` / `date`). New `telegram.note_add` (+ helpers
  `_compose_note` / `_normalize_hashtag`) and a `NotSetUpError` that tells the user to run
  `setup` first; tests in `tests/test_notes.py` with Telethon fully mocked.
- Note listing (TGN-5): `tg-notes notes list --notebook <nb> [--since <t>]` returns a
  notebook's raw notes as a JSON array (oldest first), each `{message_id, date, text}`,
  skipping the topic-opening service message. `--since` accepts `today`, `HH:MM`,
  `YYYY-MM-DD`, or a full ISO datetime (interpreted as local time when it carries no
  offset) and bounds the messages by date; an unknown notebook yields `[]`. New
  `telegram.notes_list` and a CLI `_parse_since` parser; tests in `tests/test_notes.py`
  and `tests/test_cli.py` (Telethon mocked).
- Contacts address book (TGN-6): `tg-notes contacts list|set|remove` over the
  message-per-contact schema in the `contacts` topic. New pure `tg_notes.contacts` module
  ((de)serializes the `#contact <key>` block; single-line fields, colons preserved) plus
  `telegram.contacts_list` / `contacts_set` / `contacts_remove`. `set` creates or updates
  in place (only the given fields override an existing record; a new contact requires
  `--chat-id`; edits reuse the same message), `remove` deletes the contact's message
  (missing key is a no-op), `list` returns all contacts as JSON sorted by key. Tests in
  `tests/test_contacts.py` (pure + Telethon-mocked layer). Refactor: shared
  `_resolve_store` helper (in `tg_notes.telegram`) and `_handle_store_errors` /
  `_STORE_ERRORS` (in the CLI) deduplicate the not-set-up / not-configured / not-authorized
  handling across `note add`, `notes list`, and `contacts`.
- Publish (TGN-7): `tg-notes send --contact <key> --text-file <f>` posts compiled text to a
  contact's chat **as the user** — into a forum topic (`reply_to`) when the contact has a
  `topic_id`, prepending the contact's `mention` on its own line when set. Text comes from
  a file or stdin (`-`); `--dry-run` composes and prints the outgoing message (target,
  topic, text) without sending. New `telegram.send` (+ `_compose_outgoing` /
  `_target_from_chat_id`, resolving `chat_id` as `-100…` int or `@user` / `me`) and a
  `ContactNotFoundError` (CLI exit 5); empty text is refused. Tests in `tests/test_send.py`
  (Telethon mocked). This is the first command that posts outside the storage group.
- Notebook listing (TGN-8): `tg-notes notebooks list` returns the storage group's notebook
  topics as JSON (`{name, topic_id}`, sorted), excluding the reserved `General` and
  `contacts` topics. New `telegram.notebooks_list` and `RESERVED_TOPICS`; tests in
  `tests/test_notebooks.py`. Completes **Phase 1 (CLI core)** — all deterministic Telegram
  commands are implemented and verified end-to-end. Removed the leftover `_todo` stub
  handler now that no command is a stub.
- Capture skill (TGN-9): `skills/tg-notes/SKILL.md` — a portable Agent Skill (standard
  `name`/`description` frontmatter) that captures a work note into the Telegram-backed
  store by shelling out to `tg-notes note add`. Two modes: verbatim (user dictates) and
  session summary (composed from real facts — git commits since 00:00, changed files,
  tickets — never invented), 2–6 concise bullets in the user's language, default `daily`
  notebook, optional hashtags. Capture only — it never sends. Verified end-to-end against
  the real account (both modes filed and read back). Succeeds the retired local `report`
  skill, now Telegram-native.
- Compile & send skill (TGN-10): `skills/tg-notes-send/SKILL.md` — reads notes
  (`tg-notes notes list`), rewrites them per the target contact's `style`, previews with
  `tg-notes send --dry-run`, **always shows a draft and requires an explicit confirmation**
  (the message goes out under the user's own account), then `tg-notes send`. Contacts are
  the single source of chat/topic/mention/style. Verified end-to-end against the real
  account (dry-run → confirmed send to Saved Messages → read back; unknown-contact exit 5).
  Succeeds the retired local `report-send` skill, now driven by the `tg-notes` CLI.
- Daily-report preset (TGN-11): a first-class section of `skills/tg-notes-send/SKILL.md`
  (`/tg-report`, "отправь дневной отчёт") — the compile & send flow with fixed defaults
  (notebook `daily`, `--since today`), one confirmed send per recipient. Completes
  **Phase 2 (the Claude Code Skill)**: capture (`tg-notes`) + compile & send / daily report
  (`tg-notes-send`), the Telegram-native successor to the old `report`/`report-send` pair.
- Claude Code plugin packaging (TGN-13): `.claude-plugin/plugin.json` — plugin manifest
  (`name: tg-notes`, version, author, GPL-3.0-or-later) that bundles the two skills
  (auto-discovered from `skills/`). Passes `claude plugin validate . --strict`.
- Git plugin marketplace (TGN-14): `.claude-plugin/marketplace.json` — single-plugin
  marketplace (`tg-notes-marketplace`) with `source: "./"` (plugin is the repo root).
  Install: `/plugin marketplace add korkin25/tg_notes` then
  `/plugin install tg-notes@tg-notes-marketplace`. The bundled skills drive the `tg-notes`
  CLI, installed separately with `pipx install tg-notes`.

### Changed

- Single-source the package version: `pyproject.toml` reads it from
  `tg_notes/__init__.py` (`[tool.hatch.version]`, `dynamic = ["version"]`) so it can no
  longer drift between the two. Bumped to `0.1.0` for the first release.
- Release workflow (`.github/workflows/release.yml`) now publishes to PyPI via **Trusted
  Publishing** (OIDC, `id-token: write`, `pypi` environment) instead of a stored API
  token, and runs `twine check` on the built artifacts. Publishing still triggers only on
  a `v*` tag; it needs a one-time PyPI Trusted Publisher bound to `korkin25/tg_notes`.
