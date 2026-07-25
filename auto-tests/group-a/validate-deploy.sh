#!/usr/bin/env bash
# Group-(a) functional smoke test (TGN-23/TGN-27). Runs in CI (open-ci-actions
# functional workflow) and locally. Chart linting lives in the helm CI job now, so this
# script only proves the IMAGE actually boots and serves:
#   - docker build of the image
#   - boot the MCP-HTTP server and probe the port
# Contract: exit 0 = pass, 77 = skip, other = fail. Fails on the first error.
set -euo pipefail
cd "$(dirname "$0")/../.."

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not available — skipping functional smoke test"
  exit 77
fi

PORT="${TG_NOTES_MCP_PORT:-8000}"

echo "== docker build =="
DOCKER_BUILDKIT=1 docker build -t tg-notes:ci-test .

echo "== boot MCP-HTTP and probe :${PORT} =="
docker rm -f tgn-ci >/dev/null 2>&1 || true
docker run -d --name tgn-ci -p "${PORT}:8000" tg-notes:ci-test >/dev/null
ok=0
for _ in $(seq 1 20); do
  if (echo > "/dev/tcp/127.0.0.1/${PORT}") 2>/dev/null; then ok=1; break; fi
  sleep 1
done
docker logs tgn-ci | tail -10 || true
docker rm -f tgn-ci >/dev/null 2>&1 || true
test "$ok" = "1"

echo "OK: image boots and serves on :${PORT}"
