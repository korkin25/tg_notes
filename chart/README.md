# tg-notes Helm chart

Deploys [tg_notes](https://github.com/korkin25/tg_notes) — notes → compile →
publish via a private Telegram group — from the image published to GHCR
(`ghcr.io/korkin25/tg-notes`). The chart is packaged and pushed as an OCI
artifact to `ghcr.io/korkin25/charts/tg-notes` by CI.

Adapted from the BNPL "application" chart, stripped of platform coupling
(ArgoCD globals, ESO/Vault, GatewayAPI, Liquibase) for a portable GitHub/GHCR
deployment.

## Install

```bash
helm install tg-notes oci://ghcr.io/korkin25/charts/tg-notes --version 0.1.0
```

## Workload

A **single-replica** Deployment runs `tg-notes-mcp-http` (the MCP server over
remote streamable-HTTP) on port 8000, fronted by a ClusterIP Service.

> tg_notes is a **userbot** bound to ONE Telegram session — keep `replicaCount: 1`
> and leave `autoscaling` off. The Deployment uses the `Recreate` strategy so two
> pods never hold the session at once.

An optional daily-report **CronJob** (`cronJob.enabled`, off by default) runs the
report preset on a schedule.

## Telegram session (required credential)

The Telethon `*.session` file grants full access to the account. Seed it once
into the config PVC:

```bash
kubectl exec -it deploy/<release>-tg-notes -- tg-notes login
```

It persists on the `<release>-tg-notes-config` PVC. API credentials
(`TG_NOTES_API_ID` / `TG_NOTES_API_HASH`) can be provided via an existing Secret:

```yaml
envFrom:
  secret:
    enabled: true
    name: tg-notes-secrets
```

See [../docs/configuration.md](../docs/configuration.md) for the full env-var list.

## Voice / STT model

Audio-note transcription uses a local Whisper model. The model is **deliberately
not baked into the image**. Instead:

- `voiceModel.enabled: true` (default) creates a PVC (`<release>-tg-notes-models`,
  2Gi) mounted at `/models`;
- the ConfigMap points `HF_HOME` and `XDG_CACHE_HOME` at that mount, so the model
  is fetched **on first use** into the PVC and reused across restarts;
- alternatively **devops preloads** it, or set `voiceModel.existingClaim`.

To actually run STT the container also needs the `[transcribe]` extra
(faster-whisper) and `ffmpeg`. The default image ships without them to stay lean;
build a voice-enabled image with `EXTRAS=mcp,transcribe` and `WITH_FFMPEG=1`
(see `docker-compose.voice.yml`), then set `image.tag` to it. Identical pattern
in the jira_nano chart.

## Values of note

| Key | Default | Purpose |
|-----|---------|---------|
| `image.repository` / `image.tag` | `ghcr.io/korkin25/tg-notes` / appVersion | image |
| `command` | `["tg-notes-mcp-http"]` | which surface to serve |
| `persistence.size` | `256Mi` | config + session PVC |
| `voiceModel.enabled` / `.size` | `true` / `2Gi` | Whisper model cache PVC |
| `envFrom.secret.enabled` | `false` | inject an existing Secret |
| `cronJob.enabled` | `false` | daily-report schedule |

Probes are TCP on the serving port.
