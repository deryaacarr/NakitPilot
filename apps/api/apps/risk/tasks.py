"""Celery tasks for risk (NP-100–102, NP-221, NP-222)."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="risk.calculate_customer_risk")
def calculate_customer_risk_task(
    customer_id: int | None = None, organization_id: int | None = None
) -> dict:
    from apps.customers.models import Customer
    from apps.risk.services import calculate_customer_risk

    qs = Customer.objects.filter(is_active=True)
    if customer_id is not None:
        qs = qs.filter(pk=customer_id)
    if organization_id is not None:
        qs = qs.filter(organization_id=organization_id)

    updated = 0
    for customer in qs.iterator(chunk_size=200):
        calculate_customer_risk(customer.pk)
        updated += 1
    logger.info("calculate_customer_risk updated=%s", updated)
    return {"updated": updated}


@shared_task(name="risk.resolve_outcomes")
def resolve_outcomes_task(organization_id: int | None = None) -> dict:
    """NP-221: backfill actual_outcome on matured predictions."""
    from apps.risk.dataset import resolve_pending_outcomes

    return resolve_pending_outcomes(organization_id=organization_id)


@shared_task(name="risk.train_models")
def train_models_task(
    organization_id: int,
    target_label: str | None = None,
    publish: bool = False,
    synthetic: bool = False,
) -> dict:
    """NP-222: run training pipeline for an organization."""
    from apps.organizations.models import Organization
    from apps.risk.enums import DEFAULT_TARGET_LABEL
    from apps.risk.training import run_training_pipeline, train_synthetic_smoke

    org = Organization.objects.get(pk=organization_id)
    label = target_label or DEFAULT_TARGET_LABEL
    if synthetic:
        return train_synthetic_smoke(org, publish=publish)
    return run_training_pipeline(org, target_label=label, publish=publish)
