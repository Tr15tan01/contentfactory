#!/usr/bin/env bash
# Render start for the one-service setup. Start Command: ./render-start.sh
# Runs the database migrations, then the API (with the background worker inside it) on a
# private port, and the website on Render's public $PORT. If either stops, the service exits
# and Render restarts it.
set -euo pipefail
cd "$(dirname "$0")"

# The website proxies /api/v1/* to the API next to it. next.config.ts is read again at start,
# so this must be set here as well as in render-build.sh.
export BACKEND_URL=http://127.0.0.1:8000
export RUN_WORKER_IN_API="${RUN_WORKER_IN_API:-1}"
export WORKER_MAX_JOBS="${WORKER_MAX_JOBS:-2}"

(cd backend && alembic upgrade head)

(cd backend && exec uvicorn app.main:app --host 127.0.0.1 --port 8000 \
  --proxy-headers --forwarded-allow-ips '*') &
api=$!
(cd frontend && exec node node_modules/next/dist/bin/next start -H 0.0.0.0 -p "${PORT:-3000}") &
web=$!

trap 'kill -TERM "$api" "$web" 2>/dev/null || true' TERM INT
set +e
wait -n "$api" "$web"
status=$?
kill -TERM "$api" "$web" 2>/dev/null
wait
exit "$status"
