"""NP-155 — invoke backup scripts from Celery / management command."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


def _scripts_dir() -> Path:
    # apps/api/apps/security → repo root / infrastructure/scripts
    return Path(settings.BASE_DIR).resolve().parent.parent / "infrastructure" / "scripts"


def _notify_failure(message: str) -> None:
    webhook = os.getenv("BACKUP_FAILURE_WEBHOOK", "").strip()
    logger.error("backup failure: %s", message)
    if not webhook:
        return
    try:
        import urllib.request

        req = urllib.request.Request(
            webhook,
            data=f'{{"text":"NakitPilot backup failed: {message}"}}'.encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)  # noqa: S310 — operator-configured webhook
    except Exception:  # noqa: BLE001
        logger.exception("backup failure webhook could not be delivered")


def run_script(name: str, *, timeout: int = 3600) -> dict:
    script = _scripts_dir() / name
    if not script.is_file():
        raise FileNotFoundError(f"Backup script missing: {script}")
    env = os.environ.copy()
    env.setdefault(
        "PRIVATE_UPLOAD_ROOT",
        str(getattr(settings, "PRIVATE_UPLOAD_ROOT", "")),
    )
    env.setdefault(
        "BACKUP_RETENTION_DAYS",
        str(getattr(settings, "BACKUP_RETENTION_DAYS", 14)),
    )
    completed = subprocess.run(  # noqa: S603
        ["/bin/bash", str(script)],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        cwd=str(script.parent.parent.parent),
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "unknown error")[:2000]
        _notify_failure(f"{name}: {detail}")
        raise RuntimeError(detail)
    logger.info("backup script %s ok", name)
    return {
        "script": name,
        "ok": True,
        "stdout": (completed.stdout or "")[-2000:],
    }


@shared_task(name="security.run_daily_backups")
def run_daily_backups_task(*, include_restore_test: bool = True) -> dict:
    """
    Optional Celery entrypoint for NP-155.
    Prefer host cron calling infrastructure/scripts/daily_backup.sh in production.
    """
    results = [
        run_script("backup_postgres.sh"),
        run_script("backup_uploads.sh"),
    ]
    if include_restore_test:
        results.append(run_script("test_restore.sh", timeout=7200))
    return {"steps": results}
