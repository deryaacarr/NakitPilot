"""NP-403 — bulk actions on invoice selections."""

from __future__ import annotations

import csv
import io
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.collections.models import CollectionTaskType
from apps.collections.services import create_task
from apps.customers.models import Customer
from apps.invoices.models import Invoice
from apps.invoices.overdue import invoice_overdue_days
from apps.organizations.mixins import RequireTenantContextPermission, TenantQuerysetMixin
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.organizations.tenancy import get_request_organization
from apps.risk.services import recalculate_customer_risk

User = get_user_model()


class InvoiceBulkActionView(TenantQuerysetMixin, APIView):
    """POST /api/invoices/bulk/ — assign tasks, change assignee, tags, export, risk."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def post(self, request):
        org = get_request_organization(request)
        action = (request.data.get("action") or "").strip()
        ids = request.data.get("invoice_ids") or []
        if not isinstance(ids, list) or not ids:
            return Response({"detail": "invoice_ids required."}, status=400)
        try:
            ids = [int(x) for x in ids]
        except (TypeError, ValueError):
            return Response({"detail": "invoice_ids must be integers."}, status=400)

        invoices = list(
            Invoice.objects.filter(organization=org, id__in=ids).select_related("customer")
        )
        if not invoices:
            return Response({"detail": "No invoices found."}, status=404)

        if action == "assign_tasks":
            return self._assign_tasks(request, org, invoices)
        if action == "change_assignee":
            return self._change_assignee(request, org, invoices)
        if action == "add_tags":
            return self._add_tags(request, org, invoices)
        if action == "prepare_message":
            customer_ids = sorted({inv.customer_id for inv in invoices})
            return Response(
                {
                    "action": action,
                    "selected": len(invoices),
                    "customer_ids": customer_ids,
                    "href": f"/messages?customers={','.join(str(c) for c in customer_ids)}",
                    "summary": f"{len(customer_ids)} müşteri için mesaj hazırlama açıldı.",
                }
            )
        if action == "export_excel":
            return self._export_csv(invoices)
        if action == "recalculate_risk":
            return self._recalculate_risk(invoices)
        return Response({"detail": f"Unknown action: {action}"}, status=400)

    def _assign_tasks(self, request, org, invoices):
        today = timezone.localdate()
        due = today + timedelta(days=1)
        created = 0
        errors = []
        for inv in invoices:
            try:
                create_task(
                    organization=org,
                    customer=inv.customer,
                    due_date=due,
                    title=f"Tahsilat: {inv.number}",
                    description=f"Toplu görev — fatura {inv.number}",
                    task_type=CollectionTaskType.CALL,
                    assigned_to=inv.assigned_user or request.user,
                    created_by=request.user,
                    invoice=inv,
                )
                created += 1
            except Exception as exc:  # noqa: BLE001
                errors.append({"invoice_id": inv.id, "detail": str(exc)})
        return Response(
            {
                "action": "assign_tasks",
                "selected": len(invoices),
                "created": created,
                "errors": errors,
                "summary": f"{created}/{len(invoices)} görev oluşturuldu.",
            }
        )

    def _change_assignee(self, request, org, invoices):
        assignee_id = request.data.get("assigned_user")
        if assignee_id in (None, ""):
            return Response({"detail": "assigned_user required."}, status=400)
        try:
            user = User.objects.get(pk=int(assignee_id))
        except (User.DoesNotExist, TypeError, ValueError):
            return Response({"detail": "User not found."}, status=404)
        updated = Invoice.objects.filter(
            organization=org, id__in=[i.id for i in invoices]
        ).update(assigned_user=user)
        return Response(
            {
                "action": "change_assignee",
                "selected": len(invoices),
                "updated": updated,
                "assigned_user": user.id,
                "summary": f"{updated} faturanın sorumlusu güncellendi.",
            }
        )

    def _add_tags(self, request, org, invoices):
        tags = request.data.get("tags") or []
        if not isinstance(tags, list) or not tags:
            return Response({"detail": "tags required."}, status=400)
        tags = [str(t).strip() for t in tags if str(t).strip()]
        customer_ids = {inv.customer_id for inv in invoices}
        updated = 0
        for customer in Customer.objects.filter(organization=org, id__in=customer_ids):
            current = list(customer.tags or [])
            merged = list(dict.fromkeys([*current, *tags]))
            if merged != current:
                customer.tags = merged
                customer.save(update_fields=["tags", "updated_at"])
                updated += 1
        return Response(
            {
                "action": "add_tags",
                "selected": len(invoices),
                "customers_updated": updated,
                "tags": tags,
                "summary": f"{updated} müşteriye etiket eklendi.",
            }
        )

    def _export_csv(self, invoices):
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "id",
                "number",
                "customer",
                "due_date",
                "total_amount",
                "remaining_amount",
                "status",
                "overdue_days",
            ]
        )
        for inv in invoices:
            writer.writerow(
                [
                    inv.id,
                    inv.number,
                    inv.customer.name,
                    inv.due_date.isoformat(),
                    str(inv.total_amount),
                    str(inv.remaining_amount()),
                    inv.status,
                    max(invoice_overdue_days(inv), 0),
                ]
            )
        return Response(
            {
                "action": "export_excel",
                "selected": len(invoices),
                "filename": "faturalar.csv",
                "content_type": "text/csv",
                "csv": buf.getvalue(),
                "summary": f"{len(invoices)} satır dışa aktarıldı.",
            }
        )

    def _recalculate_risk(self, invoices):
        customer_ids = sorted({inv.customer_id for inv in invoices})
        done = 0
        errors = []
        for cid in customer_ids:
            try:
                customer = Customer.objects.get(pk=cid)
                recalculate_customer_risk(customer)
                done += 1
            except Exception as exc:  # noqa: BLE001
                errors.append({"customer_id": cid, "detail": str(exc)})
        return Response(
            {
                "action": "recalculate_risk",
                "selected": len(invoices),
                "customers": done,
                "errors": errors,
                "summary": f"{done} müşteri için risk yeniden hesaplandı.",
            }
        )
