# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **TGN-27 — adopt the `ai-project-template` engineering standard (feature #25).** Universal
  agent-rule pickup: `CLAUDE.md` is the single source and `AGENTS.md`, `GEMINI.md`,
  `.cursorrules`, `.clinerules`, `.windsurfrules`, `.github/copilot-instructions.md` are
  symlinks to it, with `.cursor/rules/project.mdc` as a thin pointer and a per-turn
  `.claude/settings.json` hook re-injecting the context map. `CLAUDE.md` gained the
  **Start-here context-map router**, **Versioning** (GitVersion), **Safe autonomy**,
  **Agent security working agreements**, **Design-before-code**, and the cross-agent
  portability section (folded in from the old real `AGENTS.md`). Added a **doc-sync** CI guard
  (`.github/workflows/doc-sync.yml`), **Dependabot**, **pre-commit** (gitleaks via Docker only),
  **CODEOWNERS**, PR/issue templates, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
  `GitVersion.yml`, and a `.gitlab-ci.yml` mirror (using `open_ci_cd/templates`).
- **TGN-26 — fan-out forward with per-recipient AI rewriting (feature #24).** Deliver one
  source (a notebook's notes) to **several contacts at once**, each rewritten for that
  recipient's level via their `style` — a business summary for a manager, verbatim-technical for
  a tech lead. **Hybrid A+B** design: the `tg-notes-send` skill now documents a first-class
  multi-recipient flow (pick contacts → per-`style` drafts → one confirmation → send each) that
  uses the agent's own Claude Code model (no API key); and a headless **`tg-notes fanout`**
  command (`--contact` repeatable, `--notebook`/`--since`, `--rewrite/--no-rewrite`, `--model`,
  `--dry-run`) for cron/automation. The optional `tg_notes/ai.py` rewrite backend calls the
  Anthropic API (lazy `anthropic` import via the new `tg-notes[ai]` extra; auth from an
  `ant auth login` OAuth profile or `ANTHROPIC_API_KEY` — **no static key in the repo**; default
  model `claude-opus-5`, override with `--model` or the `ai_model` config key). Rewrite is
  best-effort: `fanout` falls back to the raw notes when the backend is absent or errors, so a
  send is never blocked. Mocked, CI-safe unit tests (`test_ai.py`, `test_fanout.py`); the live
  rewrite is a dev-machine test (needs Anthropic credentials). TDD.

- **TGN-25 — CI live-functional tests.** A new `live-functional` CI job runs **every current
  feature's real data path — through the CLI and the MCP tools** — against a **dedicated test
  account + group**, on every push: `setup`, `secrets status`/`doctor`, `whoami`; text and
  media `note add`, `notes list`, `notebooks list`; the `contacts` CRUD; `send` (dry-run and a
  real self-send that is cleaned up); plus the MCP `note_add`/`note_add_file`/`notes_list`/
  `contacts_list`/`send` tools (`tests/test_live_functional.py`, `tests/test_live_mcp.py`,
  `tests/test_live_media.py`, gated by `TG_NOTES_LIVE`). Credentials come from the
  `ci-functional` environment (`TG_NOTES_API_ID`/`TG_NOTES_API_HASH`/`TG_NOTES_SESSION` secrets
  + optional `TG_NOTES_TEST_GROUP` variable); `scripts/sandbox.py` gained an env-credential
  source (`_read_ci_credentials`) so it seeds a throwaway file-backend config from them. The job
  **skips cleanly** when the session secret is absent (forks / unconfigured repos stay green)
  and a guard refuses to run against the real store. The **secure-store (keyring) round-trip**
  (`tests/test_live_secure_store.py`) needs a Secret Service CI lacks, so it is a dev-machine
  group-(b) test (opt-in `TG_NOTES_LIVE_KEYRING=1`). TDD for the env source (mocked units); the
  live suite is gated. A `scripts/cleanup_live.py` helper (`purge` the test notebooks / `group`
  teardown) — guarded to refuse the real store — runs as an always-run CI step so the dedicated
  test group never accumulates notes. Verified end-to-end: the full live suite (19 tests) passes
  in CI against a dedicated test group.
- **TGN-24 — `tg-notes-mcp-http`.** New console entry point serving the MCP server over
  remote **streamable-HTTP** (`build_server(host, port)` + `run(transport="streamable-http")`),
  host/port from `TG_NOTES_MCP_HOST`/`TG_NOTES_MCP_PORT` (default `0.0.0.0:8000`). Lets the
  MCP server run as a networked Deployment instead of only a local stdio subprocess. TDD.
- **TGN-23 — container image, Helm chart & GHCR publishing.** Multi-stage `Dockerfile`
  (non-root uid 10000; default serves `tg-notes-mcp-http` on :8000), `docker-compose.yml`
  (lean) + `docker-compose.voice.yml` (voice-enabled, non-CI), and a Helm `chart/` adapted
  from the BNPL "application" chart — single-replica Deployment (userbot = one session),
  config PVC (Telethon session), voice-model PVC, TCP probes, optional daily-report CronJob.
  The Whisper voice model is kept off the image (chart PVC, fetched on first use or
  preloaded), documented in `chart/README.md`. CI (GitHub Actions) gains a security & quality
  suite — checkov, hadolint, trivy, semgrep, radon/xenon — a functional MCP-HTTP boot job, and
  publishes the image to `ghcr.io/korkin25/tg-notes` and the OCI chart to
  `ghcr.io/korkin25/charts/tg-notes`. Runtime env vars documented in `docs/configuration.md`;
  a minimal CI env set lives in the GitHub Actions environment `ci-functional`.

### Changed

- **TGN-32 — stable releases now also cut a GitHub Release.** Mirrors the canonical
  `release.yml` merged in `ai-project-template`. A merge to `release` still publishes the clean
  `X.Y.Z` to PyPI and now **additionally** tags `vX.Y.Z` at that commit and cuts a GitHub Release
  with auto-generated notes and the built artifacts (sdist + wheel) attached
  (`gh release create --generate-notes dist/*`, gated `if: github.ref_name == 'release'`). The
  job's `permissions.contents` was raised from `read` to `write` so the workflow can create the
  tag and release. `rc` stays **registry-only** — a pre-release publish to PyPI with **no tag** —
  so pre-release tags never confuse GitVersion.

- **TGN-31 — set `next-version: 0.2.0`.** Without it the `rc` branch (Minor increment) and the `release` branch (Patch increment) diverged (0.2.0-rc vs 0.1.3). Pinning `next-version` to the target makes both channels agree: `rc` → `0.2.0rc.N`, `release` → `0.2.0`.

- **TGN-30 — release standard: publish on merge to `rc`/`release`, no git tags.** Mirrors the
  canonical files merged in `ai-project-template`. The release is now a **merge**, not a tag:
  `.github/workflows/release.yml` triggers `on: push: branches: [rc, release]` (was: `on: push:
  tags: v*`) — a merge to `rc` publishes a PyPI **pre-release** `X.Y.ZrcN`, a merge to `release`
  publishes a clean stable `X.Y.Z`. The version comes **entirely from GitVersion**, injected at
  build time (`hatch version <semver>`), never hardcoded — `tg_notes/__init__.py` now carries a
  `0.0.0` placeholder (the published wheel gets the injected version; local dev shows `0.0.0`).
  `GitVersion.yml` was rewritten to a clean **6.x-native** config with a single knob
  `next-version` (the old BNPL-style 5.x config made `next-version` fail to parse under GitVersion
  6.8+). `CLAUDE.md`'s **Versioning & releasing** section documents the merge-based flow and the
  `rc`/`release` semantics; a new **Feature-backlog scope rule** limits `Features.md` to
  user-facing product features (engineering/infra work lives in `TODO.md`/`CHANGELOG.md`), and the
  infra entry #25 was removed from `Features.md` accordingly.
- **TGN-29 — tamed Dependabot noise + doc-sync exemption.** The `doc-sync` guard now skips
  dependency PRs (the `dependencies` label / `dependabot[bot]` actor) — a version bump carries
  no doc change and should not be forced to fake one. `dependabot.yml` now opens **one grouped
  PR per ecosystem** and **ignores breaking major bumps**; only minor/patch updates are proposed
  (majors are a deliberate migration task, not a red auto-PR).
- **TGN-28 — dropped the reusable `release` job from `ci.yml`.** PyPI Trusted Publishing
  rejects a cross-repository reusable publish (the OIDC `job_workflow_ref` points at
  `open-ci-actions`, not this repo → `invalid-publisher`, pypi/warehouse#11096). Publishing
  stays in the vendored, self-contained `.github/workflows/release.yml` (tag-triggered), which
  PyPI's trusted-publisher record matches. On a `v*` tag the reusable job would otherwise fail
  even though the vendored one succeeds.
- **TGN-27 — CI is now a composition, and the branch model moved to `dev`/`rc`/`release`.**
  `.github/workflows/ci.yml` is wiring only — every job `uses:` a reusable workflow from
  `korkin25/open-ci-actions@v1` (`detect` → `version` → `python` / `sast` / `docker` / `helm` /
  `functional` / `release`), plus one bespoke `live-functional` job (the real-Telegram suite,
  kept). The functional smoke (`auto-tests/group-a/validate-deploy.sh`) was slimmed to image
  build + boot `tg-notes-mcp-http` + port probe (contract exit 0/77/other; probe host portable
  across GitHub and GitLab DinD). The old `main` branch is retired in favour of
  `feature/*` → `dev` → `rc` → `release`; `dev` is the default branch and versions come from
  GitVersion. All governance text updated to the new model. The bespoke `live-functional`
  job runs on `push` only (skips the duplicate same-repo `pull_request` run for the same SHA)
  and holds a serializing concurrency group, so two real-Telegram suites never hit the one
  test account at once (that concurrency was making media read-backs flaky).
- **TGN-22 — governance docs mirrored with `jira_nano`.** `CLAUDE.md` gains explicit,
  apply-without-being-asked sections: **Documentation sync** (trigger→update table),
  **Testing policy** (three test groups a/b/c, TDD-first, CI log analysis even on green,
  release gate), a **Feature backlog** rule (root `Features.md`), and a MANDATORY
  **Per-task lifecycle** (log → backlog → test-plan → branch → TDD → verify → record → MR).
  The features doc moved from `docs/features.md` to the root **`Features.md`** (numbered
  backlog: Current / Planned / Brainstorm / Delivered). New `docs/tests.md` (per-feature
  test catalog) and `auto-tests/` (group-a/b/c scripts + methodologies) scaffolds added.
  Stale "planning — nothing implemented" status lines corrected to "released".

## [0.1.2] - 2026-07-25

### Added

- Audio transcription now **auto-fetches the whisper engine on first use**. When a
  transcription is needed and no engine is present, `transcribe.ensure_engine(cfg)` installs
  `faster-whisper` once per process — best-effort: `pipx inject tg-notes faster-whisper`
  inside a pipx-managed venv (detected via `"pipx"` in `sys.prefix` + a `pipx` on `PATH`),
  otherwise `<python> -m pip install faster-whisper` — then re-checks and proceeds; the model
  itself still downloads on first `WhisperModel` use. It is **best-effort and never aborts the
  upload**: a failed or non-zero install logs a one-line stderr hint (`install it manually:
  pipx inject tg-notes faster-whisper`) and the file uploads with no caption, exactly as when
  no engine is available. A module-level guard attempts the install at most once per process.
  New non-secret config key `transcriber_autoinstall` (absent/`None` ⇒ enabled; set
  `transcriber_autoinstall = false` to disable — e.g. to always pre-install the engine
  yourself). No CLI/MCP surface change — the auto-fetch happens transparently inside the
  existing `transcribe()` path. Fully-mocked tests in `tests/test_transcribe.py` (existing
  engine short-circuit, disabled, pipx-inject vs pip-install argv, non-zero/raising install,
  the one-time guard) and a config round-trip in `tests/test_config.py`.
- Sandbox testing helper + mandatory-sandbox rule: new `scripts/sandbox.py` automates a
  THROWAWAY, fully isolated tg-notes install for all live/integration testing so the real
  `~/.config/tg-notes`, the real keyring, and the real storage group are never touched. It
  seeds a sandbox config dir (`$TG_NOTES_SANDBOX_DIR` or `~/.config/tg-notes-sandbox`) from
  the real credentials (real `api_id` from config, real `api_hash` + session from the keyring,
  read with overrides unset), uses the **file** secrets backend so `tg-notes setup` runs
  non-interactively, and creates a **dedicated test group** (a fresh `-100…` id, never the
  real one). Subcommands: `setup` (idempotent seed + prints the `export TG_NOTES_CONFIG_DIR`
  line), `run -- <cmd>` (exec a command against the sandbox), `pytest -- <args>` (run the
  gated live tests with `TG_NOTES_LIVE=1`), and `reset` (delete the sandbox). The sandbox
  session file is a full-access credential (`chmod 600`, outside the repo, never committed).
  CLAUDE.md now makes sandbox isolation **mandatory** for any test touching real
  config/keyring/Telegram, and `docs/sandbox-testing.md` documents the helper alongside the
  existing env-var protocol.

## [0.1.1] - 2026-07-25

### Added

- Media notes — Phase 3 (TGN-21): media capture is now exposed on the agent surfaces. The
  local MCP server gains a `note_add_file(file, notebook="daily", caption=None,
  transcribe=True, hashtags=None)` tool that uploads a **local file** as a note (native
  Telegram media, kind auto-detected) and returns the same dict as `telegram.note_add_file`.
  It mirrors the CLI handler's best-effort audio transcription: for an audio file with no
  `caption` and an available local engine it transcribes to the caption (offloaded via
  `asyncio.to_thread`), and on `TranscriptionUnavailable`/`TranscriptionError` it logs to
  stderr and uploads with no caption — transcription never aborts the upload; a missing file
  raises a clear error before any core call. An agent may pass its own `caption` (e.g. an
  image description) to skip transcription, or `transcribe=False`. The `notes_list` tool
  already surfaces each note's `media` key verbatim. The `tg-notes` capture skill documents
  media capture (`note add --file`, audio auto-transcription, agent-supplied captions), and
  `tg-notes-send` notes that media notes compile from their caption (`media` + caption-as-`text`).
- Media notes — Phase 2 (TGN-20): audio note files **auto-transcribe to the caption**. When
  `note add --file <path>` is an audio file (`.ogg`/`.oga`/`.opus`/`.mp3`/`.m4a`/`.wav`/
  `.flac`/`.aac`/`.webm`) and no `--caption` is given, tg-notes transcribes it **locally**
  and uses the transcript as the caption — so a dictated voice note becomes searchable text
  with no manual step. New `tg_notes/transcribe.py` provides a **pluggable** local
  transcriber detected on demand in order: a configured whisper CLI (`whisper_cmd`), a
  whisper CLI on `PATH` (`whisper-cli` / `whisper` / `main` — whisper.cpp or openai-whisper),
  then the `faster-whisper` package (imported lazily). It is **best-effort**: if no engine is
  installed (`TranscriptionUnavailable`) or transcription fails (`TranscriptionError`) the
  file **still uploads** without a caption and a one-line stderr hint/warning is printed —
  transcription never aborts the upload. `telegram.py` stays pure Telegram I/O; the CLI
  handler does the transcription and passes the text into the existing `note_add_file` as the
  caption. New `--transcribe`/`--no-transcribe` flag on `note add` (default = auto: only for
  an audio file with no `--caption` and an available engine); a non-audio file, an explicit
  `--caption`, or `--no-transcribe` skips it. New non-secret config keys `transcriber`,
  `whisper_cmd`, `whisper_model`, and a `tg-notes[transcribe]` extra
  (`pipx inject tg-notes faster-whisper`). The whisper engines need `ffmpeg` to decode audio.
  Fully-mocked tests in `tests/test_transcribe.py` (backends, detection order, CLI arg
  templates, error paths) and `tests/test_media.py` (CLI wiring); a gated live test in
  `tests/test_live_transcribe.py` (skipped unless `TG_NOTES_LIVE=1` and an engine is present).
- Media notes — Phase 1 (TGN-19): `tg-notes note add --file <path> [--caption <text>]`
  uploads a photo, video, audio, or document into the notebook topic as **native Telegram
  media** (Telethon auto-detects the kind), creating the topic on demand. The `--caption`
  (plus any repeatable `--hashtag`) becomes the message caption — the note's searchable
  text; a missing file is rejected with a clear error before any network call. New
  `telegram.note_add_file` returns `{notebook, topic_id, message_id, date, media_type,
  caption}` (`media_type` ∈ `photo`/`voice`/`audio`/`video`/`gif`/`document`). `notes_list`
  is now additive: every note dict carries a `media` key (the type, or `null` for text) and
  for a media note `text` is its caption, so text and media notes compile through the same
  path. `note add`'s `--text-file` is now optional (use it or `--file`). Fully-mocked tests
  in `tests/test_media.py`; a gated live round-trip in `tests/test_live_media.py` (skipped
  unless `TG_NOTES_LIVE=1`). Captions are passed explicitly for now — Phase 2 will auto-fill
  an audio note's caption from its transcription.
- On Linux with the keyring backend, the CLI re-execs through a named launcher
  (`<venv>/libexec/tg-notes`, a copy of the interpreter with the venv's site-packages
  re-added via `site.addsitedir` under `-S`) so the vault confirmation prompt
  (KeePassXC / Secret Service) identifies the app as `tg-notes` instead of `python3.12`.
  The launcher is created once and reused; best-effort — a read-only venv (or any
  copy/exec failure) silently skips it and the CLI keeps working (the prompt then shows
  `python`). `TG_NOTES_RELAUNCHED` is an internal loop guard. No-op on non-Linux, on the
  file backend, or in frozen builds.
- `docs/sandbox-testing.md` — a protocol for isolated end-to-end testing of
  `setup`/`secrets doctor`/`secrets migrate`/pickers via `TG_NOTES_CONFIG_DIR` +
  `TG_NOTES_KEYRING_SERVICE`, so a throwaway install never touches the real
  config/session/vault (with before/after invariants on the real config + `tg-notes`
  keyring entries).
- `TG_NOTES_CONFIG_DIR` and `TG_NOTES_KEYRING_SERVICE` env vars for an isolated sandbox
  install: `TG_NOTES_CONFIG_DIR` overrides the exact config directory (its own `config.toml`
  + `*.session`, taking precedence over XDG), and `TG_NOTES_KEYRING_SERVICE` overrides the
  keyring service namespace so a sandbox `secrets migrate` never overwrites the real
  `tg-notes` vault entries — safe end-to-end testing of `setup`/`secrets doctor`/`migrate`.
  With neither set, behavior is unchanged. `secrets doctor` and `secrets status` now show
  the active config dir and keyring service.
- Interactive pickers for `send --contact`, `contacts remove`, `secrets migrate --to`, and
  `notes list --notebook` — omit the value in an interactive terminal to choose from a list
  via a fuzzy finder (`fzf`/`sk`/`fzy`) when one is installed, else a numbered menu. The
  picker fires only when both stdin and stdout are TTYs *and* the value was not passed on the
  command line, so scripted/agent use with flags is byte-for-byte unchanged; a non-interactive
  run without the value fails fast with a clear message (exit 2). `notes list --notebook` still
  falls back to `daily` when non-interactive or when the pick is cancelled.
- `tg-notes secrets doctor` — diagnoses the secret store (active backend, a classified
  vault round-trip via `keyring_probe`, the process owning the Secret Service bus, and the
  detected stores) and prints ordered, actionable recommendations: install the
  `tg-notes[keyring]` extra, expose a KeePassXC group, turn off KeePassXC per-access
  confirmation, hand the Secret Service bus from gnome-keyring over to KeePassXC, or migrate
  when the vault is ready (`--json` for machine-readable output). `secrets migrate --to
  keyring` now runs the same pre-flight and prints those recommendations instead of a
  generic error when the vault isn't ready, and `setup` ends with a tip pointing at
  `secrets doctor`.
- `docs/keepassxc.md` — a guide to using KeePassXC as tg-notes' secret store: handing
  `org.freedesktop.secrets` over from gnome-keyring (three reversible user-level changes
  + revert), exposing a dedicated minimal group, the per-connection confirmation model
  (why a short-lived CLI re-prompts / locks under `ConfirmAccessItem`, keepassxc#6458),
  the resulting security model, and the `secrets doctor`/`migrate` workflow.
- `tg-notes secrets status` now lists the detected secret stores (`available_stores`),
  each annotated with whether it serves the Secret Service or is merely running —
  gnome-keyring, KeePassXC, KWallet/ksecretd — so it's clear which vault the keyring
  backend would actually use and what you could switch to.
- Pluggable secrets backend (TGN-18): `tg_notes/secrets.py` abstracts where the two real
  secrets — `api_hash` and the Telethon session — live. **file** (default, unchanged): in
  `config.toml` (600) + a `*.session` file. **keyring** (opt-in, `tg-notes[keyring]`): in
  the OS Secret Service via the `keyring` library (gnome-keyring / KWallet / KeePassXC —
  whichever owns `org.freedesktop.secrets`), the session stored as a Telethon
  `StringSession`; provider-agnostic, so enabling KeePassXC's Secret Service integration
  routes secrets there. `api_id`/`storage_group_id` stay in config (not secret). New CLI:
  `tg-notes secrets status` (active backend, whether configured/has-session, keyring
  availability, and which process owns the Secret Service bus) and `tg-notes secrets
  migrate --to file|keyring` (moves both secrets; keyring migration verifies the vault
  round-trip before removing the on-disk session). `build_client`/`login` in `telegram.py`
  now resolve credentials + session through the active backend. Verified end-to-end on the
  real account (isolated session copy: file → keyring → `whoami` from the vault → back to
  file), the file default untouched. Tests in `tests/test_secrets.py`.
- Local MCP server (TGN-17): `tg-notes-mcp` — a stdio MCP server (`mcp` / FastMCP) that
  exposes the core as tools `note_add` / `notes_list` / `contacts_list` / `send`, so agent
  hosts that can't shell out (Claude Desktop, …) can drive tg-notes. Same local core; the
  Telethon session/secrets stay on the machine (stdio only, nothing hosted). Tools are
  async and offload the blocking Telethon calls to a worker thread (the sync core can't run
  inside the server's event loop). Ships behind an optional extra:
  `pipx install "tg-notes[mcp]"`; new `tg_notes/mcp_server.py`, tests in `tests/test_mcp.py`.
  Verified end-to-end against the real account (all four tools via the server).

### Changed

- The keyring backend now reads/writes the vault via `secretstorage` with an explicit
  unlock-and-wait (plus a small re-request retry) instead of the plain `keyring` API, so a
  per-access-confirmation vault (KeePassXC) makes tg-notes **wait for the confirmation
  prompt** — like every other app — rather than failing outright with "locked". Locked
  collections/items are `unlock()`ed (which blocks until the user answers), retrying if the
  prompt is dismissed. Existing `keyring`-written entries remain compatible (looked up by
  the `{service, username}` attributes); where `secretstorage` is unavailable (non-Linux)
  it falls back to the plain `keyring` API. The `tg-notes[keyring]` extra now also pulls
  `secretstorage` on Linux.
- `secrets doctor`'s "locked" recommendation now explains the KeePassXC
  per-connection-grant limitation (each grant is bound to a short-lived D-Bus connection,
  so a fresh CLI run re-prompts and via keyring usually fails; persistent per-app
  authorization is unimplemented, keepassxc#6458) and steers to a dedicated exposed group
  holding only tg-notes' secrets plus confirmation OFF — the same trust boundary as the
  on-disk session file. Points at `docs/keepassxc.md`.
- Expanded `AGENTS.md` (TGN-16) with the concrete shipped pieces (the `tg-notes` CLI on
  PyPI + the `tg-notes` / `tg-notes-send` skills) and per-agent distribution notes (Claude
  Code plugin marketplace, OpenCode/OpenClaw `~/.claude/skills` discovery, Hermes import).
  Cross-agent portability confirmed (TGN-D3): the same `SKILL.md` files are read unchanged
  by every Agent-Skills runtime; only distribution differs.

### Fixed

- The keyring backend now self-heals `DBUS_SESSION_BUS_ADDRESS` when it is unset. A process
  spawned with a sanitized environment (an MCP host, a cron job) has no
  `DBUS_SESSION_BUS_ADDRESS`, so `secretstorage.dbus_init()` failed with "Environment variable
  DBUS_SESSION_BUS_ADDRESS is unset" and the Secret Service was unreachable. `_ss_collection`
  now calls `_ensure_dbus_env()` before `dbus_init()`: if the variable is unset and the
  standard per-user bus socket (`/run/user/<uid>/bus`) exists, it points the variable there.
  Best-effort — it never raises, and an already-set address always wins.
- The gated live media test's photo fixture used an invalid 1x1 PNG that Telegram's
  server-side image pipeline rejected with `ImageProcessFailedError`, so
  `TG_NOTES_LIVE=1 pytest tests/test_live_media.py` failed on the photo round-trip. It now
  generates a valid 160x160 8-bit truecolor PNG in-process (signature + IHDR + a
  zlib-compressed IDAT with per-row filter bytes + IEND, all via `struct`/`zlib`, no PIL),
  which round-trips cleanly.
- The keyring backend now reuses a single `secretstorage` D-Bus connection per process
  (`_ss_collection` lazily opens it once and caches it) instead of opening a new one on every
  vault read. A single command reads the vault several times (`api_hash`, session,
  `has_session`), and KeePassXC binds each per-access-confirmation grant to the requesting
  D-Bus connection — so this makes each command trigger **at most one** KeePassXC confirmation
  prompt instead of one per read.
- `secrets migrate --to keyring` no longer overwrites the vault with an empty
  (unauthorized) session: `migrate_to_keyring` aborts if the exported session string is
  empty, so a not-logged-in run can't clobber a good vault entry.
- `contacts set` no longer errors when re-setting a contact to unchanged values: the
  underlying `edit_message` `MessageNotModifiedError` is caught and treated as a successful
  no-op (found while exercising the MCP server).
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
