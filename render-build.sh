#!/usr/bin/env bash
# Render build for the one-service setup: website + API + background worker in a single web
# service (fits Render's free plan). Build Command: ./render-build.sh  (see docs/deploy-render.md)
set -euo pipefail
cd "$(dirname "$0")"

pip install --upgrade pip
pip install ./backend

node_major=$(node -p 'process.versions.node.split(".")[0]')
if [ "$node_major" -lt 20 ]; then
  echo "Node $(node -v) is too old for Next.js 16 (needs 20.9 or newer)." >&2
  exit 1
fi

cd frontend
npm ci --include=dev
# The website proxies /api/v1/* to the API running next to it in the same service
# (render-start.sh sets the same value at start).
export BACKEND_URL=http://127.0.0.1:8000
npm run build
