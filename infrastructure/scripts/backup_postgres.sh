#!/usr/bin/env bash
# NP-155 — daily PostgreSQL backup with retention + failure webhook.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups/postgres}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/docker-compose.yml}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-postgres}"
POSTGRES_USER="${POSTGRES_USER:-nakitpilot}"
POSTGRES_DB="${POSTGRES_DB:-nakitpilot}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_FILE="$BACKUP_DIR/nakitpilot_${STAMP}.sql.gz"

notify_failure() {
  local msg="$1"
  echo "[backup] FAILURE: $msg" >&2
  if [[ -n "${BACKUP_FAILURE_WEBHOOK:-}" ]]; then
    curl -fsS -X POST \
      -H "Content-Type: application/json" \
      -d "{\"text\":\"NakitPilot Postgres backup failed: ${msg}\"}" \
      "$BACKUP_FAILURE_WEBHOOK" >/dev/null || true
  fi
}

trap 'notify_failure "unexpected error (exit $?) at line $LINENO"' ERR

mkdir -p "$BACKUP_DIR"

echo "[backup] dumping $POSTGRES_DB → $OUT_FILE"
if command -v docker >/dev/null 2>&1 && [[ -f "$COMPOSE_FILE" ]]; then
  docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
    pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl \
    | gzip -c > "$OUT_FILE"
elif [[ -n "${DATABASE_URL:-}" ]]; then
  pg_dump "$DATABASE_URL" --no-owner --no-acl | gzip -c > "$OUT_FILE"
else
  notify_failure "neither docker compose nor DATABASE_URL available"
  exit 1
fi

if [[ ! -s "$OUT_FILE" ]]; then
  notify_failure "backup file empty: $OUT_FILE"
  exit 1
fi

echo "[backup] pruning backups older than ${RETENTION_DAYS} days"
find "$BACKUP_DIR" -type f -name 'nakitpilot_*.sql.gz' -mtime "+${RETENTION_DAYS}" -print -delete || true

echo "[backup] OK $(du -h "$OUT_FILE" | awk '{print $1}')"
