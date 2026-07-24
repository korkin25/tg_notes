# Architecture

> Design document. Nothing is implemented yet; this describes the target design.

## Overview

`tg_notes` is a **CLI core plus agent Skills**. Telegram itself is the store, and
outbound messages are posted **as the user** (userbot). No product data is kept in
local files.

## Components

- **CLI (`tg-notes`)** — Python + Telethon (MTProto). Does all Telegram I/O with
  deterministic commands. Contains no AI logic.
- **Agent Skills** — thin wrappers, one per agent runtime (Claude Code first). They own
  the *intelligence*: composing a note from a working session, and compiling notes into
  a recipient-specific view. They shell out to `tg-notes`.
- **Store** — a private Telegram forum supergroup (see below).

Keeping the intelligence in the Skill and the I/O in the CLI is what makes the tool
portable: the CLI is reused unchanged, and each runtime only needs a thin wrapper.

## Storage topology

A private **forum supergroup** (Topics enabled) is the store:

- **`contacts` topic** — the address book; one message per contact.
- **notebook topics** — one topic per notebook (a stream: project, audience, …); raw
  notes are messages in the topic.

### Note message schema

- The message body is the note content (plain, Markdown-ish text).
- The timestamp is the Telegram message date — nothing is embedded.
- Optional `#hashtags` for filtering and search.
- The note is filed into the chosen notebook's topic.

### Contact message schema

One message per contact in the `contacts` topic, a parseable block:

```
#contact <key>
name: <human name, never sent>
chat_id: <-100… | @username | me>
topic_id: <forum topic id | empty>
mention: <@username | empty>
style: <prompt: how to compile notes for this recipient>
```

Editing a contact means editing its message — which is also possible from the phone.

## Data flow

- **Capture:** an agent composes a note → `tg-notes note add --notebook <nb>` posts it
  into the notebook topic.
- **Compile & publish:** `tg-notes notes list --notebook <nb> --since <t>` returns the
  raw notes → the agent rewrites them per the contact's `style` → `tg-notes send
  --contact <key>` posts the result into the contact's chat/topic.
- **Daily report:** a preset = notes since 00:00 → compile → send.

## Local state (secrets only, no data)

- `api_id` / `api_hash` and the Telethon `*.session` file live locally, git-ignored.
- The storage-group id is a pointer (not data) kept in local config.
- Notes and contacts live **only** in Telegram.

## Delivery mechanism (userbot)

Telethon logs in with the user's phone once (interactive) and produces a session.
Posting uses `send_message`; forum topics are targeted with `reply_to=<topic_id>`.
This posts **as the user**, including into group chats and topics — which a Telegram
Business bot cannot do (verified against the Bot API: Business bots are limited to
private 1:1 chats). That limitation is the reason the userbot path is required.

## Distribution

- **CLI:** PyPI (`pipx install tg-notes`) — pending decision vs. a venv bundled with
  the skill.
- **Claude Code Skill:** shipped as a plugin (`.claude-plugin/plugin.json` +
  `skills/tg-notes/SKILL.md`), installable from a git marketplace
  (`.claude-plugin/marketplace.json`). Bundled paths use `${CLAUDE_PLUGIN_ROOT}`, since
  plugin files are copied to a cache.

## Portability

The Skill targets the Agent Skills `SKILL.md` format, so the same skill can be reused
across compliant agent runtimes; runtime-specific wrappers stay thin because the CLI
carries the behavior. The exact standard and its adopters are to be verified before the
portability claim is relied upon.

## Security & Telegram ToS

- The session file grants **full account access**: `chmod 600`, never committed.
- Userbot automation is a **gray area of Telegram's ToS**; the tool publishes only the
  user's own content and must stay non-spammy.
