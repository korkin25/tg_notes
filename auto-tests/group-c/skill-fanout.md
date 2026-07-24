# Group-(c) methodology — `tg-notes-send` skill fan-out (human-in-the-loop, TGN-26)

Exercises the **interactive** half of feature #24 (Phase A): the `tg-notes-send` skill rewriting
one source into distinct per-recipient messages using the agent's own Claude Code model (no API
key). A human runs it in a Claude Code session and judges the drafts. Use the sandbox so nothing
touches the real store.

**Setup** (once): a sandbox with two self-contacts of different levels — a non-technical manager
and a technical lead (see `auto-tests/group-b/fanout-ai.md` steps 0–2 for the exact
`contacts set` + `note add`), pointing `TG_NOTES_CONFIG_DIR` at the sandbox.

**Steps for the human:**

1. In Claude Code, say: **"отправь отчёт обоим — менеджеру и тимлиду"** (or `/tg-send`).
2. The skill should: read the notes once, then compile a **separate** message per contact per
   its `style`, and show **both drafts** before sending.
3. Verify:
   - the manager's draft is simplified — no ticket ids / file names / jargon, 3–5 business points;
   - the lead's draft keeps the technical detail (tickets, names) verbatim;
   - both use only facts from the notes (nothing invented);
   - the skill asks for **one explicit confirmation** listing both recipients + texts, and warns
     that they go out **under your own account**.
4. Confirm with "да" → both messages are sent (to your own Saved Messages); each result reported
   in one line.
5. Cleanup: delete the two sent messages, `contacts remove` both, purge the notebook, reset the
   sandbox.

**Pass** when the two drafts are meaningfully different (level-appropriate), confirmation was
required, and both were delivered. Record the result in `docs/tests.md` (Feature 24, row (c)).
