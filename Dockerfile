# syntax=docker/dockerfile:1
#
# Multi-stage image for tg_notes. Built and pushed to GHCR by CI
# (ghcr.io/korkin25/tg-notes). The default command runs the MCP server over
# remote streamable-HTTP (tg-notes-mcp-http) on :8000, so it can run as a
# networked Deployment; override the entrypoint for the CLI / daily report.
#
# The heavy `[transcribe]` STT stack (faster-whisper + model weights) is
# deliberately NOT baked in — see chart/README.md for the voice-model PVC pattern.

ARG PYTHON_VERSION=3.12

# ---- build: produce a wheel and a self-contained venv -----------------------
FROM python:${PYTHON_VERSION}-slim AS build
# EXTRAS selects installed optional-dependencies. Default is lean (no voice).
# The voice-enabled image is built with EXTRAS=mcp,transcribe — see
# docker-compose.voice.yml. Whisper model weights are NEVER baked in either way.
ARG EXTRAS=mcp
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /src
RUN python -m pip install --upgrade pip build
COPY pyproject.toml README.md LICENSE ./
COPY tg_notes ./tg_notes
RUN python -m build --wheel --outdir /dist \
 && python -m venv /opt/venv \
 && /opt/venv/bin/pip install "$(echo /dist/*.whl)[${EXTRAS}]"

# ---- final: slim runtime, non-root ------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS final
LABEL org.opencontainers.image.source="https://github.com/korkin25/tg_notes" \
      org.opencontainers.image.description="tg_notes — notes → compile → publish via a private Telegram group" \
      org.opencontainers.image.licenses="GPL-3.0-or-later"

# WITH_FFMPEG=1 installs ffmpeg (audio decoding for Whisper STT) — set by the
# voice-enabled build. The default lean image omits it.
ARG WITH_FFMPEG=0

# uid/gid 10000 matches the chart's securityContext (runAsNonRoot). Pre-create the
# config + model dirs owned by the app user so bare `docker run` and docker named
# volumes (which inherit the mountpoint's ownership) are writable; in k8s the PVCs
# mount over them (fsGroup 10000).
RUN groupadd -g 10000 app \
 && useradd -u 10000 -g 10000 -m -d /home/app -s /usr/sbin/nologin app \
 && mkdir -p /config /models \
 && chown 10000:10000 /config /models \
 && if [ "$WITH_FFMPEG" = "1" ]; then \
      apt-get update && apt-get install -y --no-install-recommends ffmpeg \
      && rm -rf /var/lib/apt/lists/*; \
    fi

COPY --from=build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/app \
    TG_NOTES_CONFIG_DIR=/config \
    TG_NOTES_MCP_HOST=0.0.0.0 \
    TG_NOTES_MCP_PORT=8000

WORKDIR /app
USER 10000
EXPOSE 8000

# Default: the MCP server over streamable-HTTP. Override CMD for `tg-notes ...`
# (e.g. the daily-report preset via a CronJob).
ENTRYPOINT ["tg-notes-mcp-http"]
