# NP-155 — backup & restore runbook
#
# Cron (host, company timezone e.g. Europe/Istanbul):
#   15 2 * * * BACKUP_FAILURE_WEBHOOK=https://... /path/to/kobi/infrastructure/scripts/daily_backup.sh >>/var/log/nakitpilot-backup.log 2>&1
#
# Individual steps:
#   ./infrastructure/scripts/backup_postgres.sh
#   ./infrastructure/scripts/backup_uploads.sh
#   ./infrastructure/scripts/test_restore.sh
#
# Env:
#   BACKUP_DIR, BACKUP_RETENTION_DAYS (default 14)
#   PRIVATE_UPLOAD_ROOT
#   BACKUP_FAILURE_WEBHOOK — Slack/Discord/compatible POST JSON {text}
#   DATABASE_URL — optional fallback when docker compose is unavailable
#   KEEP_TEST_DB=1 — leave restore-test database around for inspection
