FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Dependencies first so code changes don't invalidate this layer
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY saflii_processor_yearly.py saflii_utils.py reconcile.py ragflow_sync.py main.py ./

# Crawlee state dir — world-writable so the container runs under any
# `user:` mapping; a named volume inherits these permissions on first use.
RUN mkdir -p /app/storage && chmod 1777 /app/storage

# Unbuffered so logs stream live into `docker logs`
ENV PYTHONUNBUFFERED=1

# Run the venv python directly (no uv at runtime): works under any
# `user:` mapping without needing a writable home/cache directory.
CMD ["/app/.venv/bin/python", "saflii_processor_yearly.py"]
