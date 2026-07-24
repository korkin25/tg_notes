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
