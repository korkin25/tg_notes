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
per-agent rewrite. Only *distribution* differs per agent (plugin marketplace, `~/.claude/skills`
discovery, or a runtime's own skill store); the skill content stays portable.

For anything an agent needs to know or do in this repo, defer to `CLAUDE.md`.
