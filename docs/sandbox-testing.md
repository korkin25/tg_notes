# Sandbox end-to-end testing

A reusable protocol for exercising `setup`, `secrets doctor`, `secrets migrate`, and the
interactive pickers **end-to-end** against a THROWAWAY, fully isolated tg-notes install
that never touches your real config, session, or vault. Use it whenever you want to
verify the onboarding / secrets flows on the real account without risking the crown-jewel
secrets you use day to day.

## Isolation via two env vars

Both are read at runtime; with neither set, tg-notes behaves exactly as before (config
under `~/.config/tg-notes`, keyring service `tg-notes`).

- `TG_NOTES_CONFIG_DIR=<dir>` — that directory becomes the **exact** config dir. Its own
  `config.toml` and `*.session` live directly inside it, taking precedence over
  `XDG_CONFIG_HOME` / `~/.config`. The real `~/.config/tg-notes` is never read or written.
- `TG_NOTES_KEYRING_SERVICE=tg-notes-sandbox` — a **separate keyring namespace**. A sandbox
  `secrets migrate --to keyring` writes under `tg-notes-sandbox`, so it can NEVER overwrite
  the real `tg-notes` vault entries (`api_hash`, `session`).

Throughout, prefix every command with both, e.g.:

```sh
env TG_NOTES_CONFIG_DIR="$SBX" TG_NOTES_KEYRING_SERVICE=tg-notes-sandbox tg-notes secrets status
```

## Invariants (check before and after — the safety guarantee)

- **I0** — the real `~/.config/tg-notes/config.toml` is unchanged:

  ```sh
  sha256sum ~/.config/tg-notes/config.toml
  ```

- **I1** — the real keyring `tg-notes` entries are unchanged:

  ```sh
  python3 -c 'import keyring,hashlib;
  print(*(f"{k}:"+(hashlib.sha256((keyring.get_password("tg-notes",k) or "").encode()).hexdigest())
  for k in ("api_hash","session")), sep="\n")'
  ```

Record both sha256 values before the run; re-run and compare after. They must match.

## Seeding a sandbox

```sh
SBX="$(mktemp -d /tmp/tgn-sbx.XXXX)"   # throwaway config dir
```

Two ways to populate it:

- **(a) From scratch** — run `tg-notes setup` inside the sandbox for a true from-scratch
  onboarding. This creates a fresh THROWAWAY storage group and needs an interactive login
  (phone → code → 2FA).
- **(b) Non-interactive** — write `config.toml` yourself (`api_id`, `api_hash`,
  `storage_group_id`, `secrets_backend = "file"`) and materialize the session from a
  `StringSession` via `tg_notes.secrets._write_file_session(cfg, session_str)`. No
  interactive login is needed and it attaches to an EXISTING group (e.g. the live test
  store) — ideal for scripted/agent runs.

## Protocol

| Step | Command | Expected |
|---|---|---|
| **T1** | `secrets status` | `backend=file`; `config_dir` = the sandbox dir; `keyring_service` = `tg-notes-sandbox`. |
| **T2** | `secrets doctor` | Prints the sandbox `config dir` + `keyring service` and the right recommendation for the current vault state. |
| **T3** | `whoami` (file backend, seeded session) | The real account identity (id / username / first name). |
| **T4** | `secrets migrate --to keyring` | Migrates `api_hash` + session into the `tg-notes-sandbox` namespace. Or, if the vault is locked / not ready, the pre-flight REFUSES with `secrets doctor` recommendations and writes nothing — both outcomes are safe. |
| **T5** | `whoami` + `notes list` (keyring backend) | Both work from the sandbox vault (`tg-notes-sandbox`). |
| **T6** | `secrets migrate --to file` | Back to the file backend; session materialized on disk again. |
| **T8** | `secrets migrate` (no `--to`) or `send` (no `--contact`) in a NON-TTY | Clear message + exit 2 (`specify --to file\|keyring` / `--contact is required …`). Pickers never fire without a TTY; scripted/agent use is unaffected. |
| **T9** | `setup` with the seeded group + session | Attaches idempotently (`created:false`), no new group is created. |
| **Final** | Re-check **I0** / **I1** | Real config + real keyring `tg-notes` entries unchanged (sha256 matches the pre-run values). |

## Cleanup

```sh
rm -rf "$SBX"
```

Then delete any `tg-notes-sandbox` keyring probe leftovers (`secrets doctor` / migrate
round-trip a `_probe` item). With KeePassXC per-access confirmation ON, a locked `_probe`
item may linger harmlessly — it holds no real secret and can be removed from the vault UI.

## Notes

- The fzf/menu pickers need a **real TTY**, so they cannot be exercised in a
  non-interactive run — only the agent-safe "value omitted + non-TTY → exit 2" path (T8)
  is testable there.
- A successful **keyring migration (T4/T5) needs the vault ready**: KeePassXC per-access
  confirmation OFF, or a dedicated exposed group holding only tg-notes' secrets. See
  [docs/keepassxc.md](keepassxc.md). If the vault isn't ready, T4 safely refuses and the
  protocol still passes I0/I1.
