# Features

The single **numbered backlog** for `tg_notes`: everything the user asks to build and
every brainstorm idea. Numbers are **stable and never reused**. Entries are grouped by
state — **Current** (in progress) · **Planned** · **Brainstorm** (ideas) · **Delivered**.
New requests and ideas land here first, then become tasks in [TODO.md](TODO.md).

## Current (in progress)

_None._

## Planned

15. **Community-marketplace listing.** Submit the Claude plugin to a community
    marketplace (a user web action; the repo side already passes
    `claude plugin validate . --strict` and installs from `korkin25/tg_notes`).

## Brainstorm (ideas)

_None yet._

## Delivered

### Core

1. **Telegram-native storage.** Notes live in a private Telegram forum group; nothing
   is kept in local files.
2. **Posts as you.** Delivery uses the Telegram client API (userbot), so updates land
   under the user's own account — including in group chats and forum topics.
3. **Notebooks = topics.** Each note is filed into a chosen notebook topic (per project,
   audience, or any stream).
4. **Media notes.** A note can be a media file, not just text —
   `tg-notes note add --file <path> [--caption <text>]` uploads a photo, video, audio, or
   document into the notebook topic as native Telegram media (Telethon auto-detects the
   kind). The `--caption` is the note's searchable text; `notes list` reports each note's
   media type and returns the caption as its `text`. The same media capture is available to
   agents from the capture skill and from the MCP `note_add_file` tool (audio auto-transcribes;
   an agent may pass its own caption, e.g. an image description, to skip transcription).
5. **Audio auto-transcription.** When the `--file` is audio (`.ogg`/`.opus`/`.mp3`/`.m4a`/
   `.wav`/…) and no `--caption` is given, tg-notes transcribes it **locally** and uses the
   transcript as the caption — so a dictated voice note becomes searchable text with no
   manual step. It is **pluggable and best-effort**: it uses a whisper CLI
   (whisper.cpp/openai-whisper via `whisper_cmd` or on `PATH`) or the `faster-whisper`
   package, and if no engine is installed (or transcription fails) the file still uploads,
   just without a caption. On the **first** transcription with no engine present, tg-notes
   **auto-fetches the whisper engine** (`faster-whisper`) — once per process, best-effort
   (via `pipx inject` in a pipx install, else `pip install`); disable it with
   `transcriber_autoinstall = false`, or pre-install the engine yourself with
   `pipx inject tg-notes faster-whisper` (or the `tg-notes[transcribe]` extra). You can also
   point `whisper_cmd` at a whisper binary instead; `ffmpeg` is required by the whisper
   engines to decode audio, and the model itself downloads on first use. Control it with
   `--transcribe`/`--no-transcribe`.
6. **Address book in Telegram.** A dedicated `contacts` topic holds one message per
   contact (chat, topic, mention, style); editable from the phone.
7. **Compile & publish.** Turn a subset of notes into a recipient-specific view and post
   it.
8. **Per-contact style.** Verbatim technical for a lead, simplified business language for
   a manager, etc. — driven by the contact's `style` prompt.
9. **Flexible targets.** Deliver to a plain chat or a specific forum topic, with an
   optional mention.

### Presets

10. **Daily work report.** Collect the day's notes, compile them, and send — one command
    on top of the core.

### Tooling & distribution

11. **Standalone CLI (`tg-notes`).** Does all Telegram I/O; usable on its own or from a
    scheduler. `tg-notes setup` provisions the store idempotently — creates or attaches
    the private forum supergroup, ensures the `contacts` topic and a default notebook,
    and pins a recovery marker so the group can be re-found if local config is lost. When
    spawned with a sanitized environment (a cron job, an MCP host), the opt-in keyring
    backend self-heals `DBUS_SESSION_BUS_ADDRESS` so it can still reach the Secret Service.
12. **Agent Skills.** Drive the CLI and do the writing/summarizing — Claude Code first,
    portable to other agent runtimes.
13. **Easy to install.** Distributable as a Claude plugin via a git marketplace; the CLI
    via PyPI.
14. **Interactive pickers.** Omitting the selected value on a human terminal opens a
    chooser — `send --contact`, `contacts remove`, `secrets migrate --to`, and `notes list
    --notebook` — using a fuzzy finder (`fzf`/`sk`/`fzy`) when installed, else a numbered
    menu. It engages only when both stdin and stdout are TTYs and the value was omitted, so
    scripted/agent invocations that pass the flag are unaffected.
