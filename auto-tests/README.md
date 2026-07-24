# auto-tests

Structured home for **all** test scripts, scenarios, and methodologies across the three
test groups defined in [../CLAUDE.md](../CLAUDE.md) (Testing policy). The catalog of what
each covers, per feature, lives in [../docs/tests.md](../docs/tests.md).

```
auto-tests/
  group-a/   # fully automated — wired into GitHub Actions CI, run on every push/PR
  group-b/   # dev-machine / AI-sandbox scenarios (audio, KeePassXC, live Telegram)
  group-c/   # human-in-the-loop methodologies (step-by-step docs for the user)
```

Rules:

- Group-(a) scripts must run headless in CI. Claude reads the CI logs even when green.
- Group-(b)/(c) scenarios are **also used during development**, not only after release.
- The bulk of automated coverage still lives in the top-level `tests/` (pytest) suite;
  `auto-tests/group-a/` holds end-to-end / scenario scripts that complement it and any
  glue CI invokes directly.
