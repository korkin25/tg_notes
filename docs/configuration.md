# Configuration — environment variables

tg_notes is configured through a config file (`config.toml` in the config dir) plus
a few environment variables. The Telethon `*.session` file and `config.toml` hold
the account credentials and live only on disk (git-ignored); in the container they
sit on the config PVC / `config` volume. Notes and contacts live in Telegram.

## Runtime environment variables

| Variable | Default | Secret | Purpose |
|----------|---------|:------:|---------|
| `TG_NOTES_CONFIG_DIR` | `~/.config/tg-notes` | | Config dir holding `config.toml` + the `*.session` credential. In the image: `/config`. |
| `TG_NOTES_MCP_HOST` | `0.0.0.0` | | Bind host for `tg-notes-mcp-http`. |
| `TG_NOTES_MCP_PORT` | `8000` | | Bind port for `tg-notes-mcp-http`. |
| `TG_NOTES_KEYRING_SERVICE` | `tg-notes` | | Keyring namespace (only with the `keyring` secrets backend). |
| `HF_HOME` / `XDG_CACHE_HOME` | — | | Whisper model cache dir. In the chart: `/models` (the voice-model PVC). |

## Account credentials (`config.toml` in `TG_NOTES_CONFIG_DIR`)

Seed these once with `tg-notes login` (interactive); they are **full-account
credentials** — treat the session file like a private key.

| Key | Secret | Purpose |
|-----|:------:|---------|
| `api_id` | ✅ | Telegram API id (from <https://my.telegram.org>). |
| `api_hash` | ✅ | Telegram API hash. |
| `session_path` | ✅ | Path to the Telethon `*.session` (the login credential). |
| `secrets` | | Backend: `file` (default) or `keyring`. |

## AI rewrite (fan-out — feature #24)

`tg-notes fanout` rewrites a notebook's notes per each recipient's `style` before sending. The
rewrite is **optional and best-effort** — without it (or on any failure) the raw notes are sent.

- **Install** the backend: `pipx install "tg-notes[ai]"` (adds the `anthropic` SDK). The import
  is lazy, so tg-notes runs fine without it.
- **Authenticate** with **no static key in the repo**: an `ant auth login` OAuth profile (stored
  under `~/.config/anthropic`, picked up automatically) or `ANTHROPIC_API_KEY`. A consumer
  Claude.ai subscription is **not** an API credential for the CLI — billing is through the
  Anthropic API. (The interactive `tg-notes-send` skill needs none of this: it rewrites with the
  agent's own Claude Code model.)
- **Model:** `--model` on `fanout`, else the `ai_model` config key, else `claude-opus-5`.

| `config.toml` key | Secret | Purpose |
|-----|:------:|---------|
| `ai_model` | | Default rewrite model for `fanout` (e.g. `claude-opus-5` / `claude-sonnet-5`). Never holds a key. |

## Tests

| Variable | Default | Purpose |
|----------|---------|---------|
| `TG_NOTES_LIVE` | unset | Set to `1` to enable the gated live tests (run only in the sandbox — see [sandbox-testing.md](sandbox-testing.md)). |

## CI functional tests

Two CI jobs use the GitHub Actions environment `ci-functional`:

- **`functional`** boots the built image's `tg-notes-mcp-http` server and verifies it serves
  on the port. This needs **no account secret** (the MCP HTTP server starts without a
  Telegram session; only tool *calls* touch Telegram). It reads the variable
  `TG_NOTES_MCP_PORT` (default `8000`).
- **`live-functional`** (TGN-25) runs the real Telegram flow — `setup`, `secrets doctor`,
  `whoami`, and data round-trips (note add→list, contacts set→list, notebooks list,
  `send --dry-run`) — against a **dedicated test account + group**. It needs the account
  secrets below. When `TG_NOTES_SESSION` is unset the job **skips cleanly** (exit 0), so
  forks and not-yet-configured repos stay green.

### `live-functional` credentials

`scripts/sandbox.py` seeds a throwaway file-backend config under `RUNNER_TEMP` from these,
then runs the gated `tests/test_live_functional.py` with `TG_NOTES_LIVE=1`. The real store
is never touched — a guard refuses to run against it.

| Name | Kind | Purpose |
|------|------|---------|
| `TG_NOTES_API_ID` | secret | Test account's Telegram API id. |
| `TG_NOTES_API_HASH` | secret | Test account's Telegram API hash. |
| `TG_NOTES_SESSION` | secret | A Telethon `StringSession` for a **dedicated test account** — never a personal one. Absent ⇒ the job skips. |
| `TG_NOTES_TEST_GROUP` | variable | Optional. A pre-created dedicated group id so `setup` attaches to it every run (idempotent) instead of creating a fresh group; omit to let `setup` create one. |

Generate `TG_NOTES_SESSION` on a machine logged in as the test account with
`python -c "from telethon.sessions import StringSession; from telethon.sync import TelegramClient; print(StringSession.save(TelegramClient(StringSession(), API_ID, 'API_HASH').session))"`
after an interactive `.start()`, or export it from an existing session.

Set them with:

```bash
gh variable set TG_NOTES_MCP_PORT   --env ci-functional --body "8000"
gh variable set TG_NOTES_TEST_GROUP --env ci-functional --body "-1001234567890"  # optional
gh secret   set TG_NOTES_API_ID     --env ci-functional   # paste when prompted
gh secret   set TG_NOTES_API_HASH   --env ci-functional
gh secret   set TG_NOTES_SESSION    --env ci-functional
```
