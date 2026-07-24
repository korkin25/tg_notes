# KeePassXC as tg-notes' secret store

## Purpose

tg-notes has two real secrets: your Telegram `api_hash` and the Telethon session
(full account access). The **keyring** backend keeps both in the OS Secret Service
(`org.freedesktop.secrets`) instead of on-disk files, storing the session as a
Telethon `StringSession`. KeePassXC can *serve* that bus, so your secrets live in a
`.kdbx` you already unlock daily. `api_id` and the storage group id stay in config —
they are not secret.

## Make KeePassXC serve Secret Service

On most desktops gnome-keyring grabs `org.freedesktop.secrets` at login. Hand the bus
to KeePassXC with three reversible, user-level changes (no root, no system files):

1. **Disable gnome-keyring's secrets component** — a systemd user drop-in
   `~/.config/systemd/user/gnome-keyring-daemon.service.d/no-secrets.conf`:

   ```ini
   [Service]
   ExecStart=
   ExecStart=/usr/bin/gnome-keyring-daemon --foreground --components=pkcs11
   ```

   (The empty `ExecStart=` clears the unit's default; the second line restarts it
   without the `secrets` component.)

2. **Stop the secrets autostart** —
   `~/.config/autostart/gnome-keyring-secrets.desktop` containing `Hidden=true`.

3. **Override the D-Bus service activation** so nothing re-spawns gnome-keyring on the
   bus name — `~/.local/share/dbus-1/services/org.freedesktop.secrets.service`:

   ```ini
   [D-BUS Service]
   Name=org.freedesktop.secrets
   Exec=/bin/false
   ```

Then: `loginctl enable-linger "$USER"`, enable KeePassXC autostart with its Secret
Service integration on, and **re-login**. On some setups a PAM line
`pam_gnome_keyring.so auto_start` in `/etc/pam.d/plasmalogin` (or your display
manager's file) also needs commenting out.

**Revert:** delete the three files above and run `systemctl --user daemon-reload`,
then re-login — gnome-keyring reclaims the bus.

## Expose a dedicated group

In KeePassXC: **Database Settings → Secret Service Integration → "Expose entries under
this group"**, pointing at a NEW group (e.g. `SecretService`) that holds ONLY
tg-notes' secrets — ideally a separate `.kdbx`. Everything the Secret Service can read
is exactly what you put in that group, nothing else.

## Confirmation model (the key part)

KeePassXC's `ConfirmAccessItem` ("confirm when passwords are retrieved by clients") is
**application-global** — one switch for all open databases. With it **ON**, KeePassXC
binds each grant to the requesting **D-Bus connection address**, which dies when the
process exits. A short-lived CLI opens a fresh connection every run, so it re-prompts
every time and, through python-keyring/secretstorage, typically fails outright: items
are reported `Locked` (KeePassXC 2.7.0+). Persistent per-application authorization
(exe fingerprinting) is the still-open feature request **keepassxc#6458**.

So for a CLI on 2.7.x the practical choices are:

- **Confirmation OFF + a dedicated minimal exposed group** (recommended) — simple and
  reliable.
- **A persistent Secret Service agent** if you must keep confirmation ON — a
  `systemd --user` helper that holds one long-lived D-Bus connection, approved once, and
  proxies reads. More moving parts.

## Security model

With confirmation OFF, any process running as your user can read the **exposed group**
without a prompt. If that group holds only the tg-notes session, the blast radius
equals a `*.session` file that already sits on disk readable by your processes — the
same trust boundary. Do **not** leave your whole password database exposed with
confirmation off.

## Use it

```sh
tg-notes secrets doctor              # diagnose the store + get exact next steps
tg-notes secrets migrate --to keyring   # move api_hash + session into the vault
tg-notes secrets migrate --to file      # roll back to on-disk files
```

`secrets doctor` classifies the vault round-trip and tells you precisely what to fix
(expose a group, turn confirmation off, hand the bus over, or just migrate).

## Isolated / sandbox install

Two env vars carve out a fully isolated tg-notes install so you can exercise
`setup` / `secrets doctor` / `secrets migrate` end-to-end without ever touching your
real config, session, or vault:

- `TG_NOTES_CONFIG_DIR=/path/to/sandbox` — the exact config directory. `config.toml`
  and the default `*.session` live directly in it, bypassing XDG (`TG_NOTES_CONFIG_DIR`
  wins over `XDG_CONFIG_HOME`).
- `TG_NOTES_KEYRING_SERVICE=tg-notes-sandbox` — the keyring service namespace. A sandbox
  `secrets migrate --to keyring` then writes under `tg-notes-sandbox`, so it can never
  overwrite the real `tg-notes` vault entries.

With neither set, everything behaves exactly as before (config under
`~/.config/tg-notes`, keyring service `tg-notes`). `secrets doctor` / `secrets status`
print the active `config dir` and `keyring service`, so you can confirm the isolation.

## References

- keepassxc#6458 — persistent per-application authorization (open)
- keepassxc#7653 — Secret Service items always reported locked since 2.7.0
- keepassxc#8784 — re-prompts on every client restart
- [Freedesktop Secret Service specification](https://specifications.freedesktop.org/secret-service/)
