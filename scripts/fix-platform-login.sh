#!/bin/sh
set -e
cd "$(dirname "$0")/.."
docker compose exec -T api python /scripts/ensure-platform-admin.py
