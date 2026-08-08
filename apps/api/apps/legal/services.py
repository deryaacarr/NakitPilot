"""Legal case creation / handoff orchestration."""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.customers.metrics import OPEN_STATUSES, customer_financial_metrics
from apps.customers.models import Customer
from apps.governance.approvals import request_approval, requires_approval
from apps.governance.models import ApprovalActionType, ApprovalStatus
from apps.invoices.models import Invoice
from apps.legal.criteria import evaluate_legal_handoff_criteria
from apps.legal.models import (
    LegalCase,
    LegalCaseInvoice,
    LegalCaseStatus,
    LegalCaseStatusHistory,
)
from apps.legal.workflow import LegalWorkflowError, add_activity, transition_legal_case


@transaction.atomic
def create_legal_case(
    *,
    organization,
    customer: Customer,
    created_by=None,
    title: str = "",
    invoice_ids: list[int] | None = None,
    notes: str = "",
    request_manager_approval: bool = True,
) -> LegalCase:
    if customer.organization_id != organization.id:
        raise LegalWorkflowError("Müşteri organizasyona ait değil.", code="wrong_org")

    metrics = customer_financial_metrics(customer)
    criteria = evaluate_legal_handoff_criteria(
        customer,
        organization=organization,
        manager_approved=False,
    )
    case = LegalCase.objects.create(
        organization=organization,
        customer=customer,
        title=title or f"Hukuki dosya — {customer.name}",
        status=LegalCaseStatus.PREPARING,
        balance_at_open=Decimal(str(metrics.get("open_balance") or "0")),
        criteria_snapshot=criteria,
        notes=notes,
        created_by=created_by,
    )
    LegalCaseStatusHistory.objects.create(
        organization=organization,
        legal_case=case,
        from_status="",
        to_status=LegalCaseStatus.PREPARING,
        note="Dosya oluşturuldu",
        changed_by=created_by,
    )

    qs = Invoice.objects.filter(
        organization=organization, customer=customer, status__in=list(OPEN_STATUSES)
    )
    if invoice_ids:
        qs = qs.filter(id__in=invoice_ids)
    for inv in qs:
        LegalCaseInvoice.objects.create(
            organization=organization,
            legal_case=case,
            invoice=inv,
            amount_at_link=inv.remaining_amount(),
        )

    if request_manager_approval and requires_approval(ApprovalActionType.LEGAL_HANDOFF):
        approval = request_approval(
            organization,
            action_type=ApprovalActionType.LEGAL_HANDOFF,
            requested_by=created_by,
            payload={"legal_case_id": case.id, "customer_id": customer.id},
            reason="Hukuki sürece aktarım için yönetici onayı",
        )
        case.approval_request = approval
        case.save(update_fields=["approval_request", "updated_at"])

    add_activity(
        case,
        summary="Hukuki dosya hazırlığı başladı",
        notes=notes,
        created_by=created_by,
        is_lawyer_visible=False,
    )
    return case


@transaction.atomic
def approve_legal_case(case: LegalCase, *, approved_by) -> LegalCase:
    case.manager_approved = True
    case.manager_approved_at = timezone.now()
    case.manager_approved_by = approved_by
    case.criteria_snapshot = evaluate_legal_handoff_criteria(
        case.customer,
        organization=case.organization,
        manager_approved=True,
    )
    case.save(
        update_fields=[
            "manager_approved",
            "manager_approved_at",
            "manager_approved_by",
            "criteria_snapshot",
            "updated_at",
        ]
    )
    if case.approval_request_id:
        from apps.governance.approvals import ApprovalError, decide_approval

        if case.approval_request.status == ApprovalStatus.PENDING:
            try:
                decide_approval(
                    case.approval_request, decided_by=approved_by, approve=True
                )
            except ApprovalError as exc:
                # Dual-control: requester cannot approve their own governance request.
                raise LegalWorkflowError(exc.message, code=exc.code) from exc
    add_activity(
        case,
        summary="Yönetici onayı verildi",
        created_by=approved_by,
        is_lawyer_visible=False,
    )
    return case


@transaction.atomic
def handoff_to_lawyer(
    case: LegalCase,
    *,
    lawyer,
    changed_by=None,
    note: str = "",
) -> LegalCase:
    if not case.manager_approved:
        raise LegalWorkflowError(
            "Avukata aktarım için yönetici onayı gerekli.",
            code="approval_required",
        )
    criteria = evaluate_legal_handoff_criteria(
        case.customer,
        organization=case.organization,
        manager_approved=True,
    )
    if not criteria["operational_criteria_met"]:
        raise LegalWorkflowError(
            "Operasyonel aktarım kriterleri henüz karşılanmıyor.",
            code="criteria_not_met",
        )
    case.assigned_lawyer = lawyer
    case.criteria_snapshot = criteria
    case.save(update_fields=["assigned_lawyer", "criteria_snapshot", "updated_at"])
    if case.status == LegalCaseStatus.PREPARING:
        transition_legal_case(
            case,
            to_status=LegalCaseStatus.HANDED_TO_LAWYER,
            changed_by=changed_by,
            note=note or "Avukata aktarıldı",
        )
    add_activity(
        case,
        summary=f"Avukata aktarıldı: {getattr(lawyer, 'email', lawyer)}",
        notes=note,
        created_by=changed_by,
        is_lawyer_visible=True,
    )
    return case
