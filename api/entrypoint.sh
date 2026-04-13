#!/usr/bin/env sh
set -e

# Production (ECS) passes DB_HOST / DB_USER / DB_PASSWORD as separate env vars
# (password from Secrets Manager). Build DATABASE_URL from them here so the
# app's config.py stays simple. Local dev sets DATABASE_URL directly in .env
# and doesn't set DB_HOST, so this branch is a no-op.
if [ -n "${DB_HOST:-}" ]; then
  DATABASE_URL="postgresql+psycopg://${DB_USER:-carrier}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT:-5432}/${DB_NAME:-carrier_sales}"
  export DATABASE_URL
  echo "[entrypoint] built DATABASE_URL from DB_* components"
fi

echo "[entrypoint] running alembic upgrade head"
alembic upgrade head

echo "[entrypoint] seeding loads"
python -m app.seed || echo "[entrypoint] seed skipped or already applied"

echo "[entrypoint] starting uvicorn"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
