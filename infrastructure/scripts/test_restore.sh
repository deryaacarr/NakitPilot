#!/usr/bin/env bash
# NP-155 — restore test: take (or use latest) dump, restore to temp DB, verify, drop.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}") && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups/postgres}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/docker-compose.yml}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-postgres}"
POSTGRES_USER="${POSTGRES_USER:-nakitpilot}"
TEST_DB="nakitpilot_restore_test"
KEEP_TEST_DB="${KEEP_TEST_DB:-0}"

notify_failure() {
  local msg="$1"
  echo "[restore-test] FAILURE: $msg" >&2
  if [[ -n "${BACKUP_FAILURE_WEBHOOK:-}" ]]; then
    curl -fsS -X POST \
      -H "Content-Type: application/json" \
      -d "{\"text\":\"NakitPilot restore test failed: ${msg}\"}" \
      "$BACKUP_FAILURE_WEBHOOK" >/dev/null || true
  fi
}

trap 'notify_failure "unexpected error (exit $?) at line $LINENO"' ERR

DUMP_FILE="${1:-}"
if [[ -z "$DUMP_FILE" ]]; then
  DUMP_FILE="$(ls -1t "$BACKUP_DIR"/nakitpilot_*.sql.gz 2>/dev/null | head -n1 || true)"
fi
if [[ -z "$DUMP_FILE" || ! -f "$DUMP_FILE" ]]; then
  echo "[restore-test] no dump found — running fresh backup first"
  "$SCRIPT_DIR/backup_postgres.sh"
  DUMP_FILE="$(ls -1t "$BACKUP_DIR"/nakitpilot_*.sql.gz | head -n1)"
fi

"$SCRIPT_DIR/restore_postgres.sh" "$DUMP_FILE" "$TEST_DB"

echo "[restore-test] verifying tables"
TABLE_COUNT="$(
  docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
    psql -U "$POSTGRES_USER" -d "$TEST_DB" -Atc \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';"
)"
if [[ "${TABLE_COUNT:-0}" -lt 1 ]]; then
  notify_failure "restored database has no public tables"
  exit 1
fi

echo "[restore-test] OK tables=$TABLE_COUNT dump=$(basename "$DUMP_FILE")"

if [[ "$KEEP_TEST_DB" != "1" ]]; then
  docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
    psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 \
    -c "DROP DATABASE IF EXISTS ${TEST_DB};" >/dev/null
  echo "[restore-test] dropped $TEST_DB"
fi
