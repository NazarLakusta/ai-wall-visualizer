#!/usr/bin/env sh
# PostgreSQL backup via Docker Compose. Keeps last 14 daily dumps in ./backups/
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mkdir -p backups
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="backups/wallviz_${STAMP}.sql.gz"

echo "Dumping database to ${OUT} ..."
docker compose exec -T postgres pg_dump -U wallviz -d wallviz --no-owner --no-acl | gzip > "$OUT"
echo "Done: $(du -h "$OUT" | cut -f1)"

find backups -name 'wallviz_*.sql.gz' -mtime +"$RETENTION_DAYS" -delete 2>/dev/null || true
echo "Retention: ${RETENTION_DAYS} days"
