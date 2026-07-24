# Test plan

Per-feature test catalog for `tg_notes`. When a feature is picked up for
implementation, add a section here listing its concrete tests **before** writing code
(see the Testing policy in [../CLAUDE.md](../CLAUDE.md)). Each test is tagged by group:

- **(a) Fully automated** — runs in GitHub Actions CI on every push/PR. Scripts live in
  [../auto-tests/](../auto-tests/) and are wired into CI. Claude analyses the run logs
  even when green.
- **(b) Dev-machine / AI-sandbox** — runnable only on a developer machine (audio/whisper,
  KeePassXC / Secret Service, live Telegram) or not fully automatable; run in an isolated
  sandbox under Claude's control (`scripts/sandbox.py`, `TG_NOTES_LIVE=1`).
- **(c) Human-in-the-loop** — needs a human; Claude writes a methodology and hands it over.

Per-test pass/fail status for the **current** feature is tracked in
[../TODO.md](../TODO.md); a feature is done only when 100% of its tests pass (group-(c)
methodology proposed).

---

## Baseline (delivered features 1–14)

The shipped suite (`pytest`, 121+ tests) plus the gated live tests
(`TG_NOTES_LIVE=1`) already cover the delivered features. New feature sections are
appended below as work is picked up.

## Feature 16 — `tg-notes-mcp-http` (TGN-24)

| Test | Group | What it asserts | Status |
|------|-------|-----------------|--------|
| `test_build_server_accepts_host_port` | (a) | build_server binds host/port | ✅ |
| `test_streamable_http_app_builds` | (a) | streamable-HTTP ASGI app builds | ✅ |
| `test_run_http_is_callable` / `..._reports_when_mcp_missing` | (a) | entrypoint + error path | ✅ |

## Feature 17–22 — Container image + Helm chart + GHCR CI (TGN-23)

| Test | Group | What it asserts | Status |
|------|-------|-----------------|--------|
| `helm lint chart` + `helm template` (default+toggles) | (a) | chart valid for all permutations | ✅ |
| `docker build .` | (a) | image builds | ✅ |
| CI `functional` job — boot `tg-notes-mcp-http`, probe :8000 | (a) | MCP-HTTP server serves | ✅ |
| `auto-tests/group-a/validate-deploy.sh` | (a) | CI-runnable: helm + docker build + boot | ✅ |
| `helm install` on a kind cluster; session seed + probes | (b) | Deployment ready, PVCs bound | ⬜ |
| Voice model fetched to the PVC on first audio note | (b) | model on `/models`, survives restart | ⬜ |
| GHCR image + OCI chart pull post-release | (c) | manual `docker pull` / `helm pull` after a tag | ⬜ |

Group-(b) methodology: `auto-tests/group-b/kind-deploy.md`.

## Feature 23 — CI live-functional tests (TGN-25)

The gated live Telegram flow, promoted to run **under CI** against a dedicated test
account + group. Locally these run via `scripts/sandbox.py pytest -- tests/test_live_functional.py`;
in CI the `live-functional` job seeds config from the `ci-functional` environment secrets.

| Test | Group | What it asserts | Status |
|------|-------|-----------------|--------|
| `test_read_ci_credentials_*` (in `test_sandbox_script.py`) | (a) | env source parses `TG_NOTES_API_ID/HASH/SESSION[/TEST_GROUP]`; returns `None` when incomplete; errors on non-int id/group | ⬜ |
| `test_provision_uses_ci_credentials` / `..._falls_back_to_real` | (a) | `_provision_sandbox` seeds the file backend from env creds when present, else the local keyring recipe | ⬜ |
| `test_live_whoami` | (a)-in-CI¹ | `whoami` returns the dedicated account identity | ⬜ |
| `test_live_secrets_doctor` | (a)-in-CI¹ | `secrets doctor --json` reports `configured` + `has_session` true on the file backend | ⬜ |
| `test_live_setup_idempotent` | (a)-in-CI¹ | `setup` attaches/creates the store and re-running yields the same `group_id` + topics | ⬜ |
| `test_live_note_roundtrip` | (a)-in-CI¹ | `note add` → `notes list` returns the posted note | ⬜ |
| `test_live_contacts_roundtrip` | (a)-in-CI¹ | `contacts set` → `contacts list` returns the contact; `remove` clears it | ⬜ |
| `test_live_notebooks_list` / `test_live_send_dry_run` | (a)-in-CI¹ | notebooks listed; `send --dry-run` composes without posting | ⬜ |
| CI job `live-functional` skips when `TG_NOTES_SESSION` absent | (a) | forks / unconfigured repos stay green (exit 0, no Telegram I/O) | ⬜ |

¹ Gated by `TG_NOTES_LIVE=1`; runs in CI only once the maintainer sets the `ci-functional`
secrets, and locally via the sandbox. Never touches the real store (`-1004432534270`) — a
guard asserts the configured group id is a dedicated one.

<!-- Template — copy per new feature:

## Feature <n> — <title>

| Test | Group | What it asserts | Status |
|------|-------|-----------------|--------|
| ... | (a) | ... | ⬜ |
| ... | (b) | ... | ⬜ |
| ... | (c) | ... | ⬜ |
-->
