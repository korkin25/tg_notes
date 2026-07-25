# Autopilot log — tg_notes

Autonomous changes (user authorized full autopilot on these repos). Newest first.

## 2026-07-26 — TGN-27: adopt the ai-project-template standard

- **CI is now a composition of `korkin25/open-ci-actions@v1`** (`detect` → `version` →
  `python` / `sast` / `docker` / `helm` / `functional` / `release`), replacing the previous
  inline jobs, plus one bespoke `live-functional` job (real-Telegram suite, secret-gated).
  `.github/workflows/ci.yml` is now the reference composition. _Reverse:_ restore the previous
  inline `ci.yml` from git history.
- **GitVersion** added (`GitVersion.yml`, branch model `feature/*` → `dev` → `rc` → `release`);
  versions are auto-generated, never hardcoded.
- **Branch model migrated** `main` → `dev`/`rc`/`release`. `dev` is the default branch; `main`
  is kept only as legacy history. All governance text updated to the new model.
- **Functional script slimmed** (`auto-tests/group-a/validate-deploy.sh`) to image build + boot
  `tg-notes-mcp-http` + port probe. Contract exit 0/77/other. Probe host is portable
  (127.0.0.1 on GitHub/laptop, `docker` on GitLab DinD, derived from `DOCKER_HOST`).
- **Universal agent-rule pickup.** `CLAUDE.md` is the single source; `AGENTS.md`, `GEMINI.md`,
  `.cursorrules`, `.clinerules`, `.windsurfrules`, `.github/copilot-instructions.md` are
  symlinks to it, and `.cursor/rules/project.mdc` is a thin pointer. The old real `AGENTS.md`
  content (Agent-Skills portability) was folded into `CLAUDE.md`.
- **CLAUDE.md hardened** with the template's universal sections: "Start here — context map"
  router, "Versioning", "Safe autonomy", "Agent security working agreements", "Design before
  code", and a per-turn hook (`.claude/settings.json`) that re-injects the context map.
- **Doc-sync guard** (`.github/workflows/doc-sync.yml`) fails a PR that changes code without
  touching docs. **Dependabot**, **pre-commit** (gitleaks via Docker only), **CODEOWNERS**,
  PR/issue templates, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, and a
  `.gitlab-ci.yml` mirror (using `open_ci_cd/templates`) were added.

**Guardrails honored:** feature branch `feature/TGN-27-full-standard` off `dev`; no history
rewrite; no secret touched; no real Telegram send outside the sandbox test account.
