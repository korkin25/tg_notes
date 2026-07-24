# AGENTS.md

This file is the standard entry point that AI coding agents look for.

**The canonical rules for this repository live in [CLAUDE.md](CLAUDE.md).** Read it
first: it defines the language rules, the documentation-sync policy, the security
conventions, and the autonomous development workflow (TDD, feature branches,
Conventional Commits, CI, releases). Everything in `CLAUDE.md` applies to every
agent working here, not only to Claude Code.

## Cross-agent portability

This project follows the **Agent Skills** standard (<https://agentskills.io>) and its
`SKILL.md` format. Skills are authored once as plain `SKILL.md` files (standard core
frontmatter: `name`, `description`) so the same skill is read unchanged by any
Agent-Skills-compatible runtime — Claude Code, OpenCode, Hermes, and others — with no
per-agent rewrite. Only *distribution* differs per agent; the skill content stays portable.

### What ships

- **CLI — `tg-notes`** (on PyPI: `pipx install tg-notes`). Does all Telegram I/O; agent-
  neutral. Every skill below just shells out to it, so it must be on `PATH`.
- **Two skills** (`skills/`), portable as-is:
  - `tg-notes` — capture a note (`tg-notes note add`).
  - `tg-notes-send` — compile stored notes per a contact's style and send them
    (`tg-notes send`), with a mandatory confirmation; daily-report preset included.

### Per-agent distribution (skill content is identical everywhere)

- **Claude Code** — a plugin from the git marketplace in this repo
  (`.claude-plugin/`): `/plugin marketplace add korkin25/tg_notes` then
  `/plugin install tg-notes@tg-notes-marketplace`.
- **OpenCode / OpenClaw** — discover `~/.claude/skills/*/SKILL.md` and `.claude/skills/*`
  natively; drop or symlink the two `skills/` dirs there.
- **Hermes** (Nous Research) — agentskills.io-compatible but keeps skills in its own
  `~/.hermes/` store; import the same `SKILL.md` files unchanged (and it can call the
  `tg-notes` CLI via its terminal toolset / MCP).
- Keep the frontmatter to the standard core (`name`, `description`); avoid Claude-only
  fields so the files stay runtime-agnostic.

For anything an agent needs to know or do in this repo, defer to `CLAUDE.md`.
