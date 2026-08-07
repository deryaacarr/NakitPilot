"""NP-334 — alert rules evaluation."""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.ops.metrics import technical_metrics
from apps.ops.models import AlertEvent, AlertRule, AlertSeverity

DEFAULT_RULES = [
    {
        "key": "api_error_rate",
        "name": "API hata oranı yüksek",
        "description": "API hata oranı %5'i geçti",
        "severity": AlertSeverity.CRITICAL,
        "metric_name": "api.error_rate",
        "operator": ">",
        "threshold": 5.0,
        "runbook_key": "api_error_rate",
    },
    {
        "key": "kolaybi_sync_fail",
        "name": "KolayBi senkronizasyonu başarısız",
        "description": "KolayBi senkronizasyonu 3 kez başarısız",
        "severity": AlertSeverity.CRITICAL,
        "metric_name": "sync.consecutive_failures",
        "operator": ">=",
        "threshold": 3.0,
        "runbook_key": "kolaybi_sync_fail",
    },
    {
        "key": "celery_queue_depth",
        "name": "Celery kuyruk derinliği",
        "description": "Celery queue 10.000 görevi geçti",
        "severity": AlertSeverity.WARNING,
        "metric_name": "celery.queue_max",
        "operator": ">",
        "threshold": 10000.0,
        "runbook_key": "celery_queue_depth",
    },
    {
        "key": "backup_failed",
        "name": "Backup başarısız",
        "description": "Backup başarısız",
        "severity": AlertSeverity.CRITICAL,
        "metric_name": "backup.failed",
        "operator": ">=",
        "threshold": 1.0,
        "runbook_key": "backup_failed",
    },
    {
        "key": "disk_usage",
        "name": "Disk kullanımı yüksek",
        "description": "Disk kullanımı %80'i geçti",
        "severity": AlertSeverity.WARNING,
        "metric_name": "disk.usage_pct",
        "operator": ">",
        "threshold": 80.0,
        "runbook_key": "disk_usage",
    },
    {
        "key": "webhook_error_rate",
        "name": "Webhook hata oranı",
        "description": "Webhook hata oranı yükseldi",
        "severity": AlertSeverity.WARNING,
        "metric_name": "webhook.error_rate",
        "operator": ">",
        "threshold": 10.0,
        "runbook_key": "webhook_error_rate",
    },
    {
        "key": "payment_provider_down",
        "name": "Ödeme sağlayıcısı çalışmıyor",
        "description": "Ödeme sağlayıcısı çalışmıyor",
        "severity": AlertSeverity.CRITICAL,
        "metric_name": "billing.provider_down",
        "operator": ">=",
        "threshold": 1.0,
        "runbook_key": "payment_provider_down",
    },
]


def ensure_default_rules() -> None:
    for row in DEFAULT_RULES:
        AlertRule.objects.get_or_create(key=row["key"], defaults=row)


def _compare(op: str, value: float, threshold: float) -> bool:
    if op == ">":
        return value > threshold
    if op == ">=":
        return value >= threshold
    if op == "<":
        return value < threshold
    if op == "<=":
        return value <= threshold
    return False


def collect_metric_values() -> dict[str, float]:
    tech = technical_metrics()
    queues = tech.get("celery_queues") or {}
    max_q = max([v for v in queues.values() if isinstance(v, int) and v >= 0] or [0])
    from django.core.cache import cache

    return {
        "api.error_rate": float(tech.get("api", {}).get("error_rate") or 0),
        "celery.queue_max": float(max_q),
        "webhook.error_rate": 100.0 - float(tech.get("webhook_success_rate") or 100),
        "sync.consecutive_failures": float(cache.get("np:ops:sync_consecutive_failures") or 0),
        "backup.failed": float(cache.get("np:ops:backup_failed") or 0),
        "disk.usage_pct": float(cache.get("np:ops:disk_usage_pct") or 0),
        "billing.provider_down": float(cache.get("np:ops:billing_provider_down") or 0),
    }


def evaluate_alerts() -> list[dict[str, Any]]:
    ensure_default_rules()
    values = collect_metric_values()
    fired = []
    for rule in AlertRule.objects.filter(is_enabled=True):
        value = float(values.get(rule.metric_name, 0))
        if _compare(rule.operator, value, float(rule.threshold)):
            event, created = AlertEvent.objects.get_or_create(
                rule=rule,
                is_active=True,
                defaults={
                    "message": f"{rule.name}: {value} {rule.operator} {rule.threshold}",
                    "value": value,
                },
            )
            if not created:
                event.value = value
                event.message = f"{rule.name}: {value} {rule.operator} {rule.threshold}"
                event.save(update_fields=["value", "message"])
            fired.append(
                {
                    "key": rule.key,
                    "severity": rule.severity,
                    "message": event.message,
                    "value": value,
                    "runbook_key": rule.runbook_key,
                }
            )
        else:
            AlertEvent.objects.filter(rule=rule, is_active=True).update(
                is_active=False, resolved_at=timezone.now()
            )
    return fired
