# CLAUDE.md

Guidance for Claude Code (and other AI agents) working in this repository.

## What this project is

`tg_notes` — a general-purpose **notes → compile → publish** tool that uses a private
Telegram forum group as its store and posts under the user's own account (userbot).
Daily work reports are one preset built on top of it.

Architecture in one line: a standalone Python CLI (`tg-notes`, Telethon/MTProto) does
all Telegram I/O; thin per-agent Skill wrappers (Claude Code first) add the
intelligence (composing notes, compiling them per recipient). See
[docs/architecture.md](docs/architecture.md).

Status: **released** — published to PyPI. Versions live in [CHANGELOG.md](CHANGELOG.md);
open work in [TODO.md](TODO.md); the feature backlog in [Features.md](Features.md).

## Language rules (STRICT)

- **All repository content is English** — code, identifiers, comments, docstrings,
  commit messages, and every document (README, `docs/`, CHANGELOG, TODO, this file).
  No exceptions.
- **Conversation with the user is always Russian** — reply in Russian regardless of
  the language they wrote in. This applies only to the live chat, never to anything
  written into the repo.

## Feature backlog — `Features.md` (root)

- Everything the user asks to build, and every "add for brainstorm" idea, is a
  **numbered** entry in `Features.md` at the repository **root** (never under
  `docs/`). If a features doc lives under `docs/`, move it to the root.
- Numbers are **stable and never reused**. Entries are grouped by state:
  **Current** (in progress) · **Planned** · **Brainstorm** (ideas) · **Delivered**.
- A new idea from the user lands here first (as Brainstorm or Planned) before it
  becomes a task in `TODO.md`.

## Documentation sync (apply without being asked)

Keep docs in lockstep with the code, **in the same change** — never wait to be asked:

| What changed | Update |
|---|---|
| New/changed feature or behavior | `Features.md` (root) entry + `README.md` |
| CLI / API / MCP surface (commands, flags, tools) | `README.md` + relevant `docs/*.md` |
| Architecture, storage schema, data flow, security model | `docs/architecture.md` |
| A feature is picked up for implementation | its test section in `docs/tests.md` |
| Any user-visible change | `CHANGELOG.md` under `## [Unreleased]` |
| Task started / finished / blocked, or a test's pass status | `TODO.md` |
| User asks to build something, or "add for brainstorm" | numbered entry in `Features.md` |

- `CHANGELOG.md` follows [Keep a Changelog](https://keepachangelog.com/) + SemVer.
- `TODO.md` holds only open/in-progress work and the per-test pass status of the
  current feature; a done+verified task moves to `CHANGELOG.md` in the same change.
- Never mark a task done without proof it works — see **Testing policy**.

## Testing policy (apply without being asked)

**Three test groups:**

- **(a) Fully automated** — unit/integration tests plus all debugging. Run in
  GitHub Actions CI on every push/PR. Claude **must read and analyze the CI run
  logs** (`gh run view --log`) for every run — **even when the job is green**.
- **(b) Dev-machine / AI-sandbox** — tests runnable only on a developer machine
  (audio/whisper transcription, KeePassXC / Secret Service, live Telegram) or not
  fully automatable, run in an **isolated sandbox under Claude's control** (see
  *Testing in a sandbox* below). Claude runs these itself during development, and
  again after a release once full CI is green.
- **(c) Human-in-the-loop** — require a human. Claude writes a **methodology** and
  proposes it to the user to run.

**TDD & flow:**

- For every feature/bug write the automated tests **FIRST** (they must fail), then
  implement until green. No feature code without a test.
- A task is **done only when 100% of its features are tested** — every applicable
  group covered, group-(c) methodology proposed.
- **Do not start a new feature until the current one is fully tested.**

**Artifacts & structure:**

- When a feature is picked up, immediately add a section to `docs/tests.md` listing
  its concrete tests, each tagged `(a)`/`(b)`/`(c)`.
- All test scripts, scenarios, and methodologies (**every group**) live structured
  under `auto-tests/`. Group-(a) is wired into CI to run automatically. Every
  scenario/methodology is also **used during development**, not only in CI.
- `TODO.md` tracks the pass/fail status of each test of the current feature.

**Release gate:**

- Group-(a) must be **green in CI** to release. If CI fails → **no release**; keep
  fixing until CI is green.
- After a release (full CI green) Claude re-runs group-(b); any remaining group-(c)
  tests → methodology handed to the user.

## Build, artifacts & CI (apply without being asked)

CI (GitHub Actions) is the single release pipeline. Every push/PR runs the full
gate set; a version tag `v*` publishes the release artifacts. There is no GitLab
here — do not port GitLab CI / ArgoCD patterns from the BNPL platform.

**Gates (every push/PR):**

- Tests: ruff, pytest (3.11 & 3.12).
- Code quality: radon/xenon (cyclomatic complexity + maintainability index).
- Security: bandit, pip-audit, semgrep (SAST, isolated via `pipx run`).
- IaC/config: checkov + hadolint (Dockerfile) + trivy (config & image).
- Functional: boot the built image's `tg-notes-mcp-http` and verify it serves.
- Newly-added scanners start in report mode (soft-fail / `continue-on-error`);
  tighten to hard gates once the baseline is clean — never silently drop one.

**Published artifacts — all to the GitHub Container Registry (GHCR):**

- Python sdist+wheel → PyPI (pipx-installable) on a tag (`release.yml`, trusted publishing).
- Docker image → `ghcr.io/<owner>/tg-notes` — built every push, pushed on `main`
  (`:main`, `:sha-<sha>`) and tags (`:<version>`, `:latest`).
- Helm chart (OCI) → `ghcr.io/<owner>/charts/tg-notes` — linted every push, pushed on tags.

**Local dev:** `Dockerfile` (multi-stage, non-root uid 10000) + `docker-compose.yml`
run the stack locally; the Helm `chart/` deploys it (Deployment + config PVC).
Runtime env vars are documented in `docs/configuration.md`; the minimal CI set lives
in the GitHub Actions environment `ci-functional`.

**Voice/STT model:** never baked into the image. The Helm chart provisions a PVC
for the Whisper model cache (fetched on first use or preloaded by devops); the
default image stays lean. Identical pattern in `jira_nano` — always document it in
`chart/README.md`.

## Development workflow (autonomous — apply without being asked)

This project is developed by an AI agent under continuous, autonomous iteration.

- Continuous development: while open bugs or features remain (see `Features.md` / `TODO.md`), keep implementing autonomously through the per-task lifecycle below. Consult the user ONLY for architectural decisions — topology, data model, public API/contract, deployment shape, dependency/stack choices.
- Test-driven: for every agreed feature write the tests FIRST (they must fail), then implement until green. No feature code without a test.
- Feature branches: work on feature/<task-id>-<slug> off main; merge to main only when the full suite is green.
- Commit periodically in small logical units, Conventional Commits (feat:, fix:, test:, docs:, chore:, ci:). Never add a Co-Authored-By trailer. Push to `origin` after every commit.
- Releases only after green tests: tag vX.Y.Z (SemVer) after the full suite passes on main. Publishing to PyPI or marketplaces is a separate, later, explicit step.
- CI on every push (GitHub Actions): ruff lint, pytest (3.11 and 3.12), security scan (bandit + pip-audit). A tag triggers the build/release job.
- Security first: no secrets in git; least privilege; treat the Telethon session / bot token as full-access credentials.
- High bar: type hints, docstrings, ruff-clean, meaningful tests. Work like a top-tier engineer + DevOps.
- Auto-logging: started/ongoing work goes to TODO.md (Current state + phase tables); completed and verified work moves to CHANGELOG.md, in the same change. Never mark a task done without a passing test.
- Cold-start: keep the top of TODO.md a "Current state / next action" block so a fresh session knows exactly what to do next.

### Per-task lifecycle (MANDATORY — in this order)

1. **Log first.** The task exists in `TODO.md` as `TGN-<n>` before any work begins. If it is not logged, log it first.
2. **Backlog.** Ensure the feature is a numbered entry in root `Features.md`.
3. **Test plan.** Add the feature's section to `docs/tests.md` (groups a/b/c).
4. **Branch.** Create `feature/TGN-<n>-<slug>` off `main`.
5. **TDD.** Write the failing group-(a) test(s) first; implement until green; commit in small logical units on the branch and push after each.
6. **Verify.** Group-(a) green in CI (analyze the run logs even when green); run group-(b) in dev/sandbox; update each test's status in `TODO.md`.
7. **Record.** When done and the full suite is green, move the item from `TODO.md` to `CHANGELOG.md`.
8. **MR.** Open an MR/PR to `main`; merge with `--no-ff` only when CI is green, then push `main`.

## Conventions

- **Secrets never leave the machine.** `api_id`/`api_hash`, the Telethon `*.session`
  file, and local config are git-ignored. **Notes and contacts live only in Telegram.**
- The session file grants full account access: `chmod 600`, never committed.
- Userbot automation is a Telegram-ToS gray area; the tool only publishes the user's
  own notes/reports and must stay non-spammy.

### Testing in a sandbox (mandatory for live tests)

Any test that touches the real config, the real keyring, or Telegram MUST run in an
**isolated sandbox**, never against your day-to-day install. The real
`~/.config/tg-notes`, the real keyring (`tg-notes` namespace), and the real storage group
`-1004432534270` must stay untouched.

- Use `scripts/sandbox.py` — `setup` seeds a throwaway config dir (`$TG_NOTES_SANDBOX_DIR`
  or `~/.config/tg-notes-sandbox`, file backend, a copy of the real session) and creates a
  **dedicated test group** (a fresh `-100…` id, never the real one); `run -- <cmd>` runs a
  command against it; `pytest -- <args>` runs the gated live tests (`TG_NOTES_LIVE=1`)
  there; `reset` deletes it. All idempotent.
- Or follow the manual protocol: prefix every command with `TG_NOTES_CONFIG_DIR=<sandbox>`
  (and `TG_NOTES_KEYRING_SERVICE=tg-notes-sandbox` for keyring tests) against a dedicated
  group. See [docs/sandbox-testing.md](docs/sandbox-testing.md).
- Unit tests are mocked and already isolated — they must never reach real config, keyring,
  or network. The sandbox session file is a full-access credential: `chmod 600`, outside
  the repo, never committed.
