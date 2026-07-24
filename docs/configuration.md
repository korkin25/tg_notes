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

## Tests

| Variable | Default | Purpose |
|----------|---------|---------|
| `TG_NOTES_LIVE` | unset | Set to `1` to enable the gated live tests (run only in the sandbox — see [sandbox-testing.md](sandbox-testing.md)). |

## CI functional tests

The `functional` CI job boots the built image's `tg-notes-mcp-http` server and
verifies it serves on the port — this needs **no account secret** (the MCP HTTP
server starts without a Telegram session; only tool *calls* touch Telegram).

Minimal set from the GitHub Actions environment `ci-functional`:

- **Variable** `TG_NOTES_MCP_PORT` — the port the functional job probes (default `8000`).
- **Secrets** (optional; deeper Telegram checks are skipped when absent):
  `TG_NOTES_API_ID`, `TG_NOTES_API_HASH`, `TG_NOTES_SESSION` (a `StringSession`
  for a **dedicated test account** — never a personal one), `TG_NOTES_TEST_GROUP`.

Set them with:

```bash
gh variable set TG_NOTES_MCP_PORT --env ci-functional --body "8000"
gh secret   set TG_NOTES_API_ID   --env ci-functional   # paste when prompted
gh secret   set TG_NOTES_API_HASH --env ci-functional
gh secret   set TG_NOTES_SESSION  --env ci-functional
```
