# Group-(b) methodology — deploy tg-notes to a local kind cluster (TGN-23)

Runnable on a developer machine (needs `kind`, `kubectl`, `helm`, `docker`). Not
in CI (needs a cluster + a Telegram session). Claude runs this during development;
a human can repeat it.

```bash
# 1. Cluster + image
kind create cluster --name tg-notes
DOCKER_BUILDKIT=1 docker build -t tg-notes:kind .
kind load docker-image tg-notes:kind --name tg-notes

# 2. Install the chart with the local image
helm install tgn ./chart \
  --set image.repository=tg-notes --set image.tag=kind --set image.pullPolicy=Never

# 3. Assertions
kubectl rollout status deploy/tgn-tg-notes --timeout=120s   # becomes Ready
kubectl get pvc                                             # config + models PVCs Bound
kubectl port-forward svc/tgn-tg-notes 8000:80 &
# the MCP-HTTP server accepts connections (tool calls need a seeded session):
(echo > /dev/tcp/127.0.0.1/8000) && echo "MCP-HTTP up"

# 4. (optional) seed the Telegram session, then re-check tool calls
kubectl exec -it deploy/tgn-tg-notes -- tg-notes login

# 5. Cleanup
helm uninstall tgn && kind delete cluster --name tg-notes
```

Record pass/fail per row in [../../docs/tests.md](../../docs/tests.md).
