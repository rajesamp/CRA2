# Build-only tooling. Linux/amd64 digests were resolved from their public
# registries on 2026-11-16; refresh deliberately with signature/scan evidence.
FROM ghcr.io/astral-sh/uv:0.12.16@sha256:6ac5600728c2219355bfd63b3d5e127e42d5ed27b7448b950d8a3573189fa250 AS uv
FROM gcr.io/distroless/python3-debian13:debug@sha256:6f42e208295668d74ce8bad281082b6f895cf27cd565b50bf71170d2d5f09ccd AS build
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_NO_BUILD=1 \
    PYTHONDONTWRITEBYTECODE=1 GRADIO_ANALYTICS_ENABLED=False \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 CRA2_LANGSMITH_ENABLED=false \
    LANGSMITH_TRACING=false LANGCHAIN_TRACING_V2=false

# Build with the same distro interpreter as the shell-free runtime. The stdio
# MCP child uses this same venv. All third-party packages must have locked wheels.
COPY pyproject.toml uv.lock README.md ./
COPY cra2 ./cra2
COPY data ./data
COPY evals ./evals
COPY week1 ./week1
COPY week2 ./week2
COPY week3 ./week3
COPY week4 ./week4
# CRA2 source is copied into /app and is importable by the host and MCP child.
# Skip building its wheel here; the third-party dependencies still use the lock.
RUN ["/usr/local/bin/uv", "sync", "--locked", "--no-dev", "--no-install-package", "cra2", "--project", "week2", "--python", "/usr/bin/python3"]
# The reviewed archive must be present in the build context. Setup verifies its
# exact size/SHA-256 and every extracted file; runtime never downloads a model.
RUN ["/busybox/sh", "-c", "/app/week2/.venv/bin/python -m week1.setup_index && /busybox/rm week1/.cache/models/fast-bge-small-en-v1.5.tar.gz && /busybox/chmod -R a=rX week1/.cache"]

FROM gcr.io/distroless/python3-debian13:nonroot@sha256:973adebb0daedf75c0542081edea2d45bd60ba413a9522011b478523f76b0d80
WORKDIR /app
COPY --from=build /app /app
ENV PORT=8080 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
    GRADIO_ANALYTICS_ENABLED=False GRADIO_TEMP_DIR=/tmp/gradio \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 CRA2_LANGSMITH_ENABLED=false \
    LANGSMITH_TRACING=false LANGCHAIN_TRACING_V2=false
USER 65532:65532
EXPOSE 8080
# Ephemeral paths are for container verification only. Durable state and IAP
# identity/isolation are deployment gates, not supplied by this image.
ENTRYPOINT ["/app/week2/.venv/bin/python", "-m", "week2.app", "--host", "0.0.0.0", "--memory-file", "/tmp/cra2-state/team-memory.sqlite3", "--audit-file", "/tmp/cra2-owner/audit.sqlite3"]
