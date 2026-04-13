# Build context is the repo ROOT (so we can copy ../data alongside ./api).
# Local: `docker compose build api` — see docker-compose.yml.
# Prod:  `docker buildx build --file api/Dockerfile .` — see scripts/build-and-push.sh.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      curl \
    && rm -rf /var/lib/apt/lists/*

COPY api/pyproject.toml ./
COPY api/app ./app
COPY api/alembic.ini ./
COPY api/entrypoint.sh ./
COPY data ./data

RUN pip install --upgrade pip && pip install . \
    && chmod +x entrypoint.sh

RUN useradd --create-home --uid 1000 app && chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1

ENTRYPOINT ["./entrypoint.sh"]
