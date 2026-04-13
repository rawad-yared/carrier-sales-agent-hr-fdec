#!/usr/bin/env sh
set -e

echo "[entrypoint] running alembic upgrade head"
alembic upgrade head

echo "[entrypoint] seeding loads"
python -m app.seed || echo "[entrypoint] seed skipped or already applied"

echo "[entrypoint] starting uvicorn"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
