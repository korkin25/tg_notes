#!/usr/bin/env bash
# Group-(a) functional smoke test. Chart linting lives in the shared `helm` CI job, so this
# script only proves the IMAGE actually boots and serves:
#   - docker build of the image
#   - boot the MCP-HTTP server and probe the port
# Contract (open-ci-actions functional runner): exit 0 = pass, 77 = skip, other = fail.
set -euo pipefail
cd "$(dirname "$0")/../.."

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not available — skipping functional smoke test"
  exit 77
fi

PORT="${TG_NOTES_MCP_PORT:-8000}"

# Where the published port is reachable. On a laptop / GitHub Actions the daemon is local,
# so 127.0.0.1. On GitLab CI the container runs on the docker:dind *service* and its ports
# live in that service's netns — reachable at host `docker`, never localhost. Derive the
# host from DOCKER_HOST (e.g. tcp://docker:2376 -> docker) when the runner set it.
PROBE_HOST="127.0.0.1"
if [ -n "${DOCKER_HOST:-}" ]; then
  h="$(printf '%s' "${DOCKER_HOST}" | sed -E 's#^[a-z]+://##; s#:.*$##')"
  [ -n "${h}" ] && PROBE_HOST="${h}"
fi

echo "== docker build =="
DOCKER_BUILDKIT=1 docker build -t tg-notes:ci-test .

echo "== boot MCP-HTTP and probe ${PROBE_HOST}:${PORT} =="
docker rm -f tgn-ci >/dev/null 2>&1 || true
docker run -d --name tgn-ci -p "${PORT}:8000" tg-notes:ci-test >/dev/null
ok=0
for _ in $(seq 1 20); do
  if (echo > "/dev/tcp/${PROBE_HOST}/${PORT}") 2>/dev/null; then ok=1; break; fi
  sleep 1
done
docker logs tgn-ci | tail -10 || true
docker rm -f tgn-ci >/dev/null 2>&1 || true
test "${ok}" = "1"

echo "OK: image boots and serves on :${PORT}"
