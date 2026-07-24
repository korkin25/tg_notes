# Group-(b) methodology — live `tg-notes fanout` with AI rewrite (TGN-26)

Runs on a developer machine with **Anthropic credentials** (an `ant auth login` OAuth profile,
or `ANTHROPIC_API_KEY`) — CI has none, so the real rewrite can't run there. Never touches the
real store: run it against the sandbox (`scripts/sandbox.py`), which uses a dedicated test group.

```bash
# 0. Prereqs: the AI extra + credentials
pipx install "tg-notes[ai]"          # or: pip install anthropic (into the tg-notes env)
ant auth login                       # OAuth profile (no static key), or export ANTHROPIC_API_KEY

# 1. Sandbox (dedicated test group; file backend) + two self-contacts with distinct styles
export TG_NOTES_CONFIG_DIR="$(python scripts/sandbox.py setup | sed -n 's/^sandbox dir *: //p')"
tg-notes contacts set fan-mgr  --chat-id me --name "Manager"  --style "нетехнический менеджер: без жаргона, 3–5 деловых пунктов"
tg-notes contacts set fan-lead --chat-id me --name "Tech lead" --style "технический тимлид: дословно, тикеты и имена файлов"

# 2. A source note, then fan out (dry-run first to inspect per-recipient drafts)
printf 'TGN-42 закрыт: пофиксил гонку в voice PVC, деплой на прод, README обновлён' \
  | tg-notes note add --notebook fanouttest --text-file -
tg-notes fanout --contact fan-mgr --contact fan-lead --notebook fanouttest --dry-run

# 3. Assertions (dry-run JSON, one object per contact):
#    - two results, `sent: false`
#    - the manager text is simplified (no ticket ids / file names), the lead text keeps them
#    - both preserve only facts from the note (nothing invented)

# 4. (optional) Real send to your own Saved Messages, then delete the two messages:
tg-notes fanout --contact fan-mgr --contact fan-lead --notebook fanouttest   # sent: true ×2

# 5. Cleanup
tg-notes contacts remove fan-mgr && tg-notes contacts remove fan-lead
python scripts/cleanup_live.py purge --notebook fanouttest
python scripts/sandbox.py reset

# Fallback check (no AI): with the extra uninstalled, `fanout` must still send the raw notes.
tg-notes fanout --contact fan-mgr --notebook fanouttest --dry-run   # text == raw note
```

Record pass/fail per row in [../../docs/tests.md](../../docs/tests.md) (Feature 24).
