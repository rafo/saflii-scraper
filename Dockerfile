FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Dependencies first so code changes don't invalidate this layer
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY saflii_processor_yearly.py saflii_utils.py reconcile.py ragflow_sync.py rules_collector.py scheduler.py main.py ./

# Crawlee state dir — world-writable so the container runs under any
# `user:` mapping; a named volume inherits these permissions on first use.
RUN mkdir -p /app/storage && chmod 1777 /app/storage

# Unbuffered so logs stream live into `docker logs`
ENV PYTHONUNBUFFERED=1

# Crawlee purges its local storage (the whole request queue) at the start
# of every process by default — verified empirically (2026-07) that a
# restart otherwise re-walks the entire site from the top, even though
# already-downloaded files are still skipped individually. With this
# disabled, an interrupted/redeployed crawl resumes where it left off
# instead of re-crawling from scratch. Set here (not just in compose) so
# it applies to every invocation of every script in this image.
ENV CRAWLEE_PURGE_ON_START=false

# Run the venv python directly (no uv at runtime): works under any
# `user:` mapping without needing a writable home/cache directory.
# Default is the in-container scheduler (periodic scrape jobs); override
# the command for a one-shot run of an individual script.
CMD ["/app/.venv/bin/python", "scheduler.py"]
