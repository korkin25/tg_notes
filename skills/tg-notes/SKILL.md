---
name: tg-notes
description: Capture a work note into a Telegram-backed notebook via the tg-notes CLI. Use when the user says "запиши в заметки", "залогируй сделанное", "добавь заметку", runs /tg-note, or dictates a note to save ("запиши: …"). Files either a verbatim note or a concise summary composed from real session facts (git commits, changed files, tickets), then runs `tg-notes note add`. Capture only — it never sends anything to anyone.
---

# tg-notes — capture

Append a note to the user's Telegram-backed store using the `tg-notes` CLI. Notes live
in a private Telegram forum group (one topic per notebook), not in local files. This
skill only **captures** — composing and filing a note. Compiling notes for a recipient
and sending them is a separate flow (`tg-notes send`), never done here.

Architecture: all Telegram I/O is done by the `tg-notes` CLI; this skill is a thin
wrapper that decides *what* to write and shells out. See the project README for the CLI.

## When to use

- The user runs `/tg-note`, or asks "запиши в заметки", "залогируй сделанное", "добавь
  заметку", "что я сегодня сделал" (to record it), or dictates "запиши: …".
- At the end of a substantive session, when there is something worth recording.

## Two capture modes

1. **Verbatim** — the user dictates the note ("запиши: …"). File the given text as-is;
   do not embellish it.
2. **Session summary** — the user wants the session logged without dictating it. Compose
   the note yourself from **real facts only** (see below), never invented.

## Steps

1. **Check the CLI is ready.** Notes require a configured store. If a `tg-notes` command
   later fails with `run \`tg-notes setup\` first` (exit 4) or a not-logged-in message,
   tell the user to run `tg-notes setup` and stop.

2. **Gather facts** (session-summary mode only — take from the real session, never guess):
   - `git -C <repo> log --oneline --since="00:00" --author="$(git -C <repo> config user.email)"`
     for each repo actually worked in (the working directory and any additional ones).
   - Changed/created files, applied migrations/manifests, tasks closed.
   - Related tickets (Jira, etc.), MRs/PRs.
   - Key outcomes from this session's dialog.

3. **Compose concisely, in the user's working language** (Russian for this user): 2–6
   bullet points — *what was done and why*, not how. Technical, no filler. If nothing
   substantive happened, say so and do not write a note.

4. **Choose the notebook.** Default `daily`. Use another `--notebook <name>` only when the
   user names a stream/project (the topic is created on demand). Optional `#hashtags` via
   repeatable `--hashtag`.

5. **File the note** via the CLI. Prefer stdin so nothing hits disk:

   ```bash
   printf '%s' "$NOTE_TEXT" | tg-notes note add --notebook daily --text-file - \
       --hashtag <tag>        # optional, repeatable
   ```

   Or from a temp file for multi-line text:

   ```bash
   tmp=$(mktemp); printf '%s\n' "$NOTE_TEXT" > "$tmp"
   tg-notes note add --notebook daily --text-file "$tmp"; rm -f "$tmp"
   ```

   On success the CLI prints JSON (`notebook` / `topic_id` / `message_id` / `date`).
   Confirm to the user with a one-line summary of what was filed and where.

## Notes

- **Capture only.** This skill never sends to a contact or chat. Publishing a compiled
  report is the send flow's job; keep them separate.
- Empty notes are rejected by the CLI — do not file a note when there is nothing to say.
- The `tg-notes` session grants full account access and userbot use is a Telegram-ToS
  gray area; only the user's own notes are stored, and nothing is sent from here.
