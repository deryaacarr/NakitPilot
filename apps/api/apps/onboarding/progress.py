"""NP-292 — onboarding ilerleme puanı."""

from __future__ import annotations

from typing import Any

from apps.onboarding.models import OnboardingState

# Weights from ticket
PROGRESS_WEIGHTS = {
    "company_completed": 10,
    "first_customer": 20,
    "first_invoice": 20,
    "integration_connected": 20,
    "first_task_completed": 15,
    "first_workflow_published": 15,
}


def ensure_state(organization) -> OnboardingState:
    org_id = organization.pk if hasattr(organization, "pk") else organization
    state, _ = OnboardingState.objects.get_or_create(organization_id=org_id)
    return state


def detect_flags(organization) -> dict[str, bool]:
    org_id = organization.pk if hasattr(organization, "pk") else organization
    flags: dict[str, bool] = {}

    from apps.organizations.models import Organization

    org = organization if hasattr(organization, "tax_number") else Organization.objects.get(pk=org_id)
    flags["company_completed"] = bool(org.name and (org.tax_number or org.email or org.phone))

    from apps.customers.models import Customer

    flags["first_customer"] = Customer.objects.filter(
        organization_id=org_id, is_sample=False
    ).exists()

    from apps.invoices.models import Invoice

    flags["first_invoice"] = Invoice.objects.filter(
        organization_id=org_id, is_sample=False
    ).exists()

    try:
        from apps.integrations.models import IntegrationConnection

        flags["integration_connected"] = IntegrationConnection.objects.filter(
            organization_id=org_id
        ).exists()
    except Exception:  # noqa: BLE001
        flags["integration_connected"] = False

    try:
        from apps.collections.models import CollectionTask

        flags["first_task_completed"] = CollectionTask.objects.filter(
            organization_id=org_id,
            status="COMPLETED",
        ).exists()
    except Exception:  # noqa: BLE001
        flags["first_task_completed"] = False

    try:
        from apps.workflows.enums import WorkflowLifecycleStatus
        from apps.workflows.models import CollectionWorkflow

        flags["first_workflow_published"] = CollectionWorkflow.objects.filter(
            organization_id=org_id,
            status=WorkflowLifecycleStatus.PUBLISHED,
        ).exists()
    except Exception:  # noqa: BLE001
        flags["first_workflow_published"] = False

    return flags


def compute_score(organization) -> dict[str, Any]:
    state = ensure_state(organization)
    live = detect_flags(organization)
    merged = {k: False for k in PROGRESS_WEIGHTS}
    merged.update(state.flags or {})
    # Live detection wins for true
    for k, v in live.items():
        merged[k] = bool(merged.get(k) or v)

    score = 0
    items = []
    for key, weight in PROGRESS_WEIGHTS.items():
        done = bool(merged.get(key))
        if done:
            score += weight
        items.append(
            {
                "key": key,
                "label": {
                    "company_completed": "Şirket bilgileri tamamlandı",
                    "first_customer": "İlk müşteri eklendi",
                    "first_invoice": "İlk fatura aktarıldı",
                    "integration_connected": "Entegrasyon bağlandı",
                    "first_task_completed": "İlk görev tamamlandı",
                    "first_workflow_published": "İlk workflow yayınlandı",
                }.get(key, key),
                "weight": weight,
                "done": done,
            }
        )

    state.flags = merged
    state.save(update_fields=["flags", "updated_at"])
    return {
        "score": score,
        "max_score": 100,
        "items": items,
        "wizard_completed": state.wizard_completed,
        "current_step": state.current_step,
        "sample_data_enabled": state.sample_data_enabled,
    }
