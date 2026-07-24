#!/usr/bin/env bash
# Group-(a) deploy artifacts smoke test (TGN-23). Runs in CI and locally:
#   - helm lint + template (default and toggled values)
#   - docker build of the image
#   - boot the MCP-HTTP server and probe the port
# Fails on the first error.
set -euo pipefail
cd "$(dirname "$0")/../.."

echo "== helm lint =="
helm lint chart

echo "== helm template (default) =="
helm template t chart >/dev/null

echo "== helm template (toggles: ingress/cronJob/serviceMonitor/pdb) =="
helm template t chart \
  --set ingress.enabled=true \
  --set cronJob.enabled=true --set 'cronJob.command[0]=tg-notes' \
  --set serviceMonitor.enabled=true \
  --set podDisruptionBudget.enabled=true >/dev/null

echo "== docker build =="
DOCKER_BUILDKIT=1 docker build -t tg-notes:ci-test .

echo "== boot MCP-HTTP and probe :8000 =="
docker run -d --name tgn-ci -p 8000:8000 tg-notes:ci-test >/dev/null
ok=0
for _ in $(seq 1 20); do
  if (echo > /dev/tcp/127.0.0.1/8000) 2>/dev/null; then ok=1; break; fi
  sleep 1
done
docker logs tgn-ci | tail -10 || true
docker rm -f tgn-ci >/dev/null 2>&1 || true
test "$ok" = "1"

echo "OK: deploy artifacts validated"
