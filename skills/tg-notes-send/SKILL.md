---
name: tg-notes-send
description: Compile stored notes for a specific recipient and send them to that contact's Telegram chat AS THE USER (userbot), via the tg-notes CLI. Use when the user says "отправь отчёт в телегу", "отправь дневной отчёт", "скомпилируй и отправь", "отправь <кому>", or runs /tg-send or /tg-report. Reads notes with `tg-notes notes list`, rewrites them per the contact's style, ALWAYS shows a draft and asks for explicit confirmation, then runs `tg-notes send`. The daily-report preset compiles and sends today's notes (since 00:00).
---

# tg-notes-send — compile & send

Turn stored notes into a recipient-specific message and publish it to a contact's chat
**as the user** (userbot), using the `tg-notes` CLI. One source of notes → different
messages per recipient, driven by each contact's `style`.

> ⚠️ **Sends as the user.** `tg-notes send` posts under the user's own account, including
> into group chats and forum topics. Userbot use is a Telegram-ToS gray area. **Never send
> without an explicit confirmation** (see step 5); only the user's own content, non-spammy.

Architecture: the `tg-notes` CLI does all Telegram I/O; this skill decides *what* to send
to *whom* and shells out. Capture (writing notes) is the separate `tg-notes` skill.

## When to use

- The user runs `/tg-send [contact]`, or asks "отправь отчёт в телегу", "скомпилируй и
  отправь", "отправь <кому>", "отправь дневной отчёт".

## Steps

1. **Pick the recipient.** Contact key from the request, else ask. List options with
   `tg-notes contacts list` (JSON: `key`, `name`, `chat_id`, `topic_id`, `mention`,
   `style`). If the named contact is absent (`send` would exit 5), show the list and stop.

2. **Read the notes.** `tg-notes notes list --notebook <nb> [--since <t>]` (default
   notebook `daily`). Choose `--since` from the request (e.g. `today` for a daily report).
   Empty list → nothing to send; say so and stop.

3. **Compile for this recipient.** Rewrite the raw notes strictly per the contact's
   `style` prompt, in the user's language (Russian for this user), concise, no filler:
   - a technical lead / work chat → keep as-is: full technical detail, tickets, names;
   - a non-technical manager → simplify: drop jargon/ticket ids/file names, keep the
     business meaning (what was done and why, status, risks), 3–5 plain points.
   Do not invent anything not present in the notes. (The contact's `mention`, if any, is
   prepended automatically by `tg-notes send` — do not add it yourself.)

4. **Preview with a dry run.** Pipe the compiled text through `send --dry-run` to get the
   exact target/topic/text without sending:

   ```bash
   printf '%s' "$COMPILED" | tg-notes send --contact <key> --text-file - --dry-run
   ```

5. **Confirm — always, before sending.** Show the user: the final text, the recipient
   (contact `name`/`chat_id`, topic if any), and the warning that **it will be sent under
   their own account**. Send **only** on an explicit "да"/"send". On anything else, stop.

6. **Send** the same text for real:

   ```bash
   printf '%s' "$COMPILED" | tg-notes send --contact <key> --text-file -
   ```

   Success prints JSON with `sent: true` and `message_id`. Report it back in one line.
   On error: exit 5 (unknown contact) → list contacts; exit 4 (not set up) → run
   `tg-notes setup`; exit 3 (not logged in) → `tg-notes login`; other Telethon errors
   (e.g. no access to the chat / wrong `chat_id`) → show the message to the user.

## Daily-report preset

The common case — "send today's work report". Triggered by `/tg-report`, "отправь дневной
отчёт", "отчёт в телегу". It is the flow above with fixed defaults:

- **Notebook** `daily`, **since** `today` → `tg-notes notes list --notebook daily --since today`.
- Recipient: the contact from the request; if none is named, use the user's usual
  reporting contact (ask which one if unclear — `tg-notes contacts list` to choose).
- Then compile per the contact's `style`, preview, **confirm**, and send exactly as in the
  steps above. Multiple recipients → repeat per contact (each with its own compiled text
  and its own confirmation).

If there are no notes since 00:00, there is nothing to report — say so and stop.

## Notes

- **Confirmation is mandatory.** Never skip step 5, even if the user seems in a hurry —
  the message goes out under their name.
- Keep contacts (`tg-notes contacts set`) as the single source of chat/topic/mention/style;
  this skill reads them, it does not hardcode recipients.
