#!/usr/bin/env bash
# NP-155 — restore a Postgres dump into a target database.
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <backup.sql.gz> [target_db]" >&2
  exit 2
fi

DUMP_FILE="$1"
TARGET_DB="${2:-nakitpilot_restore_test}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/docker-compose.yml}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-postgres}"
POSTGRES_USER="${POSTGRES_USER:-nakitpilot}"

if [[ ! -f "$DUMP_FILE" ]]; then
  echo "Dump not found: $DUMP_FILE" >&2
  exit 1
fi

echo "[restore] recreating database $TARGET_DB"
docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 <<SQL
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${TARGET_DB}' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS ${TARGET_DB};
CREATE DATABASE ${TARGET_DB} OWNER ${POSTGRES_USER};
SQL

echo "[restore] loading $DUMP_FILE"
gunzip -c "$DUMP_FILE" | docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  psql -U "$POSTGRES_USER" -d "$TARGET_DB" -v ON_ERROR_STOP=1 >/dev/null

echo "[restore] OK into $TARGET_DB"
