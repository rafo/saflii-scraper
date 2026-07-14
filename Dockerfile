FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Dependencies first so code changes don't invalidate this layer
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY saflii_processor_yearly.py saflii_utils.py reconcile.py ragflow_sync.py main.py ./

# Unbuffered so logs stream live into `docker logs`
ENV PYTHONUNBUFFERED=1

CMD ["uv", "run", "--frozen", "python", "saflii_processor_yearly.py"]
