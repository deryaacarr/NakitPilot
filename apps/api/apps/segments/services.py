"""Segment bootstrap, evaluation, A/B metrics (NP-260–263)."""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.segments.models import (
    ABTestStatus,
    CollectionStrategy,
    CustomerSegment,
    MessageABTest,
    MessageABTestAssignment,
)
from apps.segments.rules import (
    DEFAULT_SEGMENTS,
    DEFAULT_STRATEGIES,
    evaluate_segment_customers,
    validate_rules,
)


def ensure_default_segments(organization) -> list[CustomerSegment]:
    created: list[CustomerSegment] = []
    for spec in DEFAULT_SEGMENTS:
        seg, was_created = CustomerSegment.objects.get_or_create(
            organization=organization,
            slug=spec["slug"],
            defaults={
                "name": spec["name"],
                "rules": spec["rules"],
                "is_system": True,
                "is_active": True,
                "description": "Sistem varsayılan segmenti",
            },
        )
        if was_created:
            created.append(seg)
        steps = DEFAULT_STRATEGIES.get(spec["slug"])
        if steps:
            CollectionStrategy.objects.get_or_create(
                organization=organization,
                segment=seg,
                name=f"{spec['name']} stratejisi",
                defaults={"steps": steps, "is_active": True},
            )
    return created


def serialize_segment(seg: CustomerSegment, *, with_count: bool = False) -> dict[str, Any]:
    data = {
        "id": seg.id,
        "organization": seg.organization_id,
        "name": seg.name,
        "slug": seg.slug,
        "description": seg.description,
        "rules": seg.rules,
        "is_system": seg.is_system,
        "is_active": seg.is_active,
        "created_at": seg.created_at.isoformat() if seg.created_at else None,
        "updated_at": seg.updated_at.isoformat() if seg.updated_at else None,
    }
    if with_count:
        members = evaluate_segment_customers(seg.organization, seg.rules or {})
        data["member_count"] = len(members)
        data["member_ids"] = [c.id for c in members[:200]]
    return data


def serialize_strategy(s: CollectionStrategy) -> dict[str, Any]:
    return {
        "id": s.id,
        "organization": s.organization_id,
        "name": s.name,
        "segment_id": s.segment_id,
        "steps": s.steps,
        "is_active": s.is_active,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def create_segment(
    organization,
    *,
    name: str,
    rules: dict,
    slug: str = "",
    description: str = "",
    actor=None,
) -> CustomerSegment:
    validate_rules(rules)
    base = slugify(slug or name) or "segment"
    unique = base
    i = 1
    while CustomerSegment.objects.filter(organization=organization, slug=unique).exists():
        unique = f"{base}-{i}"
        i += 1
    return CustomerSegment.objects.create(
        organization=organization,
        name=name,
        slug=unique,
        description=description or "",
        rules=rules,
        created_by=actor,
    )


def ab_test_metrics(test: MessageABTest) -> dict[str, Any]:
    assignments = MessageABTestAssignment.objects.filter(test=test)
    result: dict[str, Any] = {"variants": {}}
    for variant in ("A", "B"):
        qs = assignments.filter(variant=variant)
        total = qs.count()
        sent = qs.exclude(sent_at__isnull=True).count()
        replied = qs.filter(replied=True).count()
        promises = qs.filter(promise_within_7d=True).count()
        paid = qs.filter(paid_within_7d=True).count()
        denom = sent or total or 1
        result["variants"][variant] = {
            "assigned": total,
            "sent": sent,
            "reply_rate": round(replied / denom, 4),
            "promise_rate_7d": round(promises / denom, 4),
            "payment_rate_7d": round(paid / denom, 4),
        }
    return result


@transaction.atomic
def assign_ab_variants(test: MessageABTest, customer_ids: list[int]) -> int:
    count = 0
    for idx, cid in enumerate(customer_ids):
        variant = "A" if idx % 2 == 0 else "B"
        _, created = MessageABTestAssignment.objects.get_or_create(
            organization_id=test.organization_id,
            test=test,
            customer_id=cid,
            defaults={"variant": variant},
        )
        if created:
            count += 1
    if test.status == ABTestStatus.DRAFT:
        test.status = ABTestStatus.RUNNING
        test.started_at = timezone.now()
        test.save(update_fields=["status", "started_at", "updated_at"])
    return count


def serialize_ab_test(test: MessageABTest, *, with_metrics: bool = False) -> dict[str, Any]:
    data = {
        "id": test.id,
        "organization": test.organization_id,
        "name": test.name,
        "status": test.status,
        "segment_id": test.segment_id,
        "variant_a": test.variant_a,
        "variant_b": test.variant_b,
        "started_at": test.started_at.isoformat() if test.started_at else None,
        "ended_at": test.ended_at.isoformat() if test.ended_at else None,
        "created_at": test.created_at.isoformat() if test.created_at else None,
    }
    if with_metrics:
        data["metrics"] = ab_test_metrics(test)
    return data
