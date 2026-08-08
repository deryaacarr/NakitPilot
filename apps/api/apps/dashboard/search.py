"""NP-382 — global search across customers, invoices, tasks, payments, promises."""

from __future__ import annotations

from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.mixins import RequireTenantContextPermission
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.organizations.tenancy import get_request_organization


class GlobalSearchView(APIView):
    """GET /api/search/?q= — grouped results, target <300ms for typical tenants."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS

    def get(self, request):
        org = get_request_organization(request)
        q = (request.query_params.get("q") or "").strip()
        if len(q) < 2:
            return Response(
                {
                    "q": q,
                    "customers": [],
                    "invoices": [],
                    "tasks": [],
                    "payments": [],
                    "promises": [],
                }
            )

        limit = 8
        from apps.collections.models import CollectionTask, PaymentPromise
        from apps.customers.models import Customer
        from apps.invoices.models import Invoice
        from apps.payments.models import Payment

        customers = list(
            Customer.objects.filter(organization=org)
            .filter(
                Q(name__icontains=q)
                | Q(code__icontains=q)
                | Q(tax_number__icontains=q)
                | Q(phone__icontains=q)
                | Q(email__icontains=q)
            )
            .order_by("name")[:limit]
            .values("id", "name", "code", "tax_number", "phone")
        )

        invoices = list(
            Invoice.objects.filter(organization=org)
            .filter(
                Q(number__icontains=q)
                | Q(customer__name__icontains=q)
                | Q(customer__tax_number__icontains=q)
            )
            .select_related("customer")
            .order_by("-id")[:limit]
            .values("id", "number", "customer_id", "customer__name", "status", "total_amount")
        )

        tasks = list(
            CollectionTask.objects.filter(organization=org)
            .filter(
                Q(title__icontains=q)
                | Q(description__icontains=q)
                | Q(customer__name__icontains=q)
                | Q(customer__phone__icontains=q)
            )
            .select_related("customer")
            .order_by("-id")[:limit]
            .values("id", "title", "status", "due_date", "customer_id", "customer__name")
        )

        payments = list(
            Payment.objects.filter(organization=org, cancelled_at__isnull=True)
            .filter(
                Q(reference__icontains=q)
                | Q(notes__icontains=q)
                | Q(customer__name__icontains=q)
                | Q(customer__tax_number__icontains=q)
            )
            .select_related("customer")
            .order_by("-id")[:limit]
            .values("id", "amount", "payment_date", "customer_id", "customer__name", "reference")
        )

        promises = list(
            PaymentPromise.objects.filter(organization=org)
            .filter(
                Q(notes__icontains=q)
                | Q(customer__name__icontains=q)
                | Q(customer__phone__icontains=q)
            )
            .select_related("customer")
            .order_by("-id")[:limit]
            .values(
                "id",
                "amount",
                "promised_date",
                "status",
                "customer_id",
                "customer__name",
            )
        )

        return Response(
            {
                "q": q,
                "customers": [
                    {
                        "id": c["id"],
                        "label": c["name"],
                        "subtitle": c["tax_number"] or c["phone"] or c["code"] or "",
                        "href": f"/customers/{c['id']}",
                    }
                    for c in customers
                ],
                "invoices": [
                    {
                        "id": i["id"],
                        "label": i["number"],
                        "subtitle": i["customer__name"],
                        "href": f"/invoices/{i['id']}",
                    }
                    for i in invoices
                ],
                "tasks": [
                    {
                        "id": t["id"],
                        "label": t["title"] or f"Görev #{t['id']}",
                        "subtitle": t["customer__name"],
                        "href": f"/collections/tasks?task={t['id']}",
                    }
                    for t in tasks
                ],
                "payments": [
                    {
                        "id": p["id"],
                        "label": f"{p['amount']} · {p['payment_date']}",
                        "subtitle": p["customer__name"],
                        "href": f"/payments?payment={p['id']}",
                    }
                    for p in payments
                ],
                "promises": [
                    {
                        "id": pr["id"],
                        "label": f"Söz #{pr['id']} · {pr['amount']}",
                        "subtitle": pr["customer__name"],
                        "href": f"/promises?promise={pr['id']}",
                    }
                    for pr in promises
                ],
            }
        )
