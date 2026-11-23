# Build-only tooling. Linux/amd64 digests were resolved from their public
# registries on 2026-11-16; refresh deliberately with signature/scan evidence.
FROM ghcr.io/astral-sh/uv:0.12.16@sha256:6ac5600728c2219355bfd63b3d5e127e42d5ed27b7448b950d8a3573189fa250 AS uv
FROM cgr.dev/chainguard/wolfi-base@sha256:2c12da5496e21e99003b3db3b9246f025e53d533c4df334205391260f1e8f85b AS os
USER 0
# Direct and resolved package versions from the verified Wolfi candidate.
RUN ["/sbin/apk", "add", "--no-cache", \
    "gdbm=1.26-r10", "glibc-2.44=2.44-r20", \
    "libbz2-1=1.0.8-r31", "libexpat1=2.10.0-r1", \
    "libffi=3.8.1-r0", "libgomp=16.2.0-r4", \
    "libstdc++=16.2.0-r4", "libuuid=2.42.4-r3", \
    "mpdecimal=4.0.1-r6", "ncurses-terminfo-base=6.6.20261114-r0", \
    "ncurses=6.6.20261114-r0", "py3-pip-wheel=26.2.2-r3", \
    "python-3.13-base=3.13.18_git20261115-r1", "python-3.13=3.13.18_git20261115-r1", \
    "readline=8.3-r4", "sqlite-libs=3.54.1-r0", \
    "xz=5.8.4-r2"]
RUN ["/usr/bin/python3.13", "-c", "import ssl, sqlite3; print(ssl.OPENSSL_VERSION)"]

FROM os AS build
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_NO_BUILD=1 UV_CONCURRENT_DOWNLOADS=2 UV_CONCURRENT_INSTALLS=2 \
    PYTHONDONTWRITEBYTECODE=1 GRADIO_ANALYTICS_ENABLED=False \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 CRA2_LANGSMITH_ENABLED=false \
    LANGSMITH_TRACING=false LANGCHAIN_TRACING_V2=false

# Build with the same interpreter as the runtime. The stdio
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
RUN ["/usr/local/bin/uv", "sync", "--locked", "--no-dev", "--no-install-package", "cra2", "--project", "week2", "--python", "/usr/bin/python3.13"]
# The reviewed archive must be present in the build context. Setup verifies its
# exact size/SHA-256 and every extracted file; runtime never downloads a model.
RUN ["/bin/sh", "-c", "/app/week2/.venv/bin/python -m week1.setup_index && /app/week2/.venv/bin/python -m week2.release_info && rm week1/.cache/models/fast-bge-small-en-v1.5.tar.gz && chmod -R a=rX week1/.cache"]

FROM os
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
