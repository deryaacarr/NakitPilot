#!/usr/bin/env bash
# NP-155 — backup private upload / file storage tree.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
UPLOAD_ROOT="${PRIVATE_UPLOAD_ROOT:-$ROOT_DIR/apps/api/private_uploads}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups/uploads}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_FILE="$BACKUP_DIR/uploads_${STAMP}.tar.gz"

notify_failure() {
  local msg="$1"
  echo "[backup-uploads] FAILURE: $msg" >&2
  if [[ -n "${BACKUP_FAILURE_WEBHOOK:-}" ]]; then
    curl -fsS -X POST \
      -H "Content-Type: application/json" \
      -d "{\"text\":\"NakitPilot uploads backup failed: ${msg}\"}" \
      "$BACKUP_FAILURE_WEBHOOK" >/dev/null || true
  fi
}

trap 'notify_failure "unexpected error (exit $?) at line $LINENO"' ERR

mkdir -p "$BACKUP_DIR"

if [[ ! -d "$UPLOAD_ROOT" ]]; then
  mkdir -p "$UPLOAD_ROOT"
  echo "[backup-uploads] created empty $UPLOAD_ROOT"
fi

echo "[backup-uploads] archiving $UPLOAD_ROOT → $OUT_FILE"
tar -C "$(dirname "$UPLOAD_ROOT")" -czf "$OUT_FILE" "$(basename "$UPLOAD_ROOT")"

if [[ ! -s "$OUT_FILE" ]]; then
  notify_failure "archive empty: $OUT_FILE"
  exit 1
fi

find "$BACKUP_DIR" -type f -name 'uploads_*.tar.gz' -mtime "+${RETENTION_DAYS}" -print -delete || true
echo "[backup-uploads] OK $(du -h "$OUT_FILE" | awk '{print $1}')"
