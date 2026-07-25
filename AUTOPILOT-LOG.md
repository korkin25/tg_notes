# Autopilot log — tg_notes

Autonomous changes (full autopilot authority granted for this repo). What / why / how to reverse.

## 2026-07-26 — TGN-27: adopt open-ci-actions

- **CI replaced with a composition of `korkin25/open-ci-actions@v1`** (detect → python / sast /
  docker→GHCR / helm / functional). Every job self-activates from repo contents. The bespoke
  `live-functional` (real Telegram, secret-gated) stays inline. Done on a feature branch → PR →
  merge to `main` only when green. _Reverse:_ `git revert` the merge, or restore the previous
  `.github/workflows/ci.yml` from git history.
- **Kept `main` as the integration branch** (did NOT rename to dev/rc/release). Renaming the
  default branch of a published repo is a topology change left for the user to decide; the new
  ideology can be applied later. `docker` push-branches set to `main` accordingly.
- **`auto-tests/group-a/validate-deploy.sh` slimmed** to image boot+probe (chart lint moved to
  the shared `helm` job). Contract exit 0/77/other.
- **`release.yml` (PyPI trusted publishing) left untouched** — publishing is delicate and out of
  autopilot scope.
