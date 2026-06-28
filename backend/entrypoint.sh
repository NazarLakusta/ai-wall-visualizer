#!/bin/sh
set -e
alembic upgrade head
python /scripts/seed_test_project.py || true
exec "$@"
