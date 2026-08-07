#!/usr/bin/env bash
# NP-155 — orchestrate daily Postgres + uploads backup, then restore test.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}") && pwd)"

notify_failure() {
  local msg="$1"
  echo "[daily-backup] FAILURE: $msg" >&2
  if [[ -n "${BACKUP_FAILURE_WEBHOOK:-}" ]]; then
    curl -fsS -X POST \
      -H "Content-Type: application/json" \
      -d "{\"text\":\"NakitPilot daily backup failed: ${msg}\"}" \
      "$BACKUP_FAILURE_WEBHOOK" >/dev/null || true
  fi
}

trap 'notify_failure "unexpected error (exit $?) at line $LINENO"' ERR

"$SCRIPT_DIR/backup_postgres.sh"
"$SCRIPT_DIR/backup_uploads.sh"
"$SCRIPT_DIR/test_restore.sh"

echo "[daily-backup] all steps OK"
