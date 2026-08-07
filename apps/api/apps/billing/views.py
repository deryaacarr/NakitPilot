"""NP-280–286 billing API."""

from __future__ import annotations

import json

from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.billing.models import BillingInvoice, PlanCode, SubscriptionPlan, SubscriptionStatus
from apps.billing.payments import (
    PaymentError,
    cancel_subscription,
    invoice_download_payload,
    process_due_retries,
    process_webhook,
    schedule_downgrade,
    start_checkout,
    update_payment_method,
)
from apps.billing.revenue import revenue_metrics
from apps.billing.subscription_service import (
    can_use,
    ensure_default_plans,
    ensure_subscription,
    get_active_subscription,
    get_entitlements,
)
from apps.billing.trial import apply_trial_expiry, is_read_only, trial_progress
from apps.billing.usage import record_usage, usage_summary
from apps.organizations.mixins import RequireTenantContextPermission
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.organizations.tenancy import get_request_organization


def _sub_payload(organization, sub):
    apply_trial_expiry(organization)
    sub.refresh_from_db()
    return {
        "id": sub.id,
        "status": sub.status,
        "plan": {
            "code": sub.plan.code,
            "name": sub.plan.name,
            "price_monthly": str(sub.plan.price_monthly),
            "price_yearly": str(sub.plan.price_yearly),
        },
        "seats": sub.seats,
        "trial_ends_at": sub.trial_ends_at.isoformat() if sub.trial_ends_at else None,
        "card_required": sub.card_required,
        "current_period_end": (
            sub.current_period_end.isoformat() if sub.current_period_end else None
        ),
        "cancel_at_period_end": sub.cancel_at_period_end,
        "read_only": is_read_only(organization),
        "dunning_step": sub.dunning_step,
        "next_retry_at": sub.next_retry_at.isoformat() if sub.next_retry_at else None,
        "grace_ends_at": sub.grace_ends_at.isoformat() if sub.grace_ends_at else None,
        "scheduled_plan": (
            {"code": sub.scheduled_plan.code, "name": sub.scheduled_plan.name}
            if sub.scheduled_plan_id
            else None
        ),
        "scheduled_plan_at": (
            sub.scheduled_plan_at.isoformat() if sub.scheduled_plan_at else None
        ),
        "payment_method": {
            "brand": sub.payment_method_brand,
            "last4": sub.payment_method_last4,
            "provider": sub.payment_provider,
        },
        "entitlements": get_entitlements(organization),
        "usage": usage_summary(organization),
    }


class PlanListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ensure_default_plans()
        plans = SubscriptionPlan.objects.filter(is_active=True)
        return Response(
            {
                "results": [
                    {
                        "id": p.id,
                        "code": p.code,
                        "name": p.name,
                        "description": p.description,
                        "price_monthly": str(p.price_monthly),
                        "price_yearly": str(p.price_yearly),
                        "sort_order": p.sort_order,
                        "entitlements": p.entitlements,
                    }
                    for p in plans
                ]
            }
        )


class SubscriptionMeView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_SETTINGS

    def get(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        sub = ensure_subscription(organization)
        return Response(_sub_payload(organization, sub))

    def post(self, request):
        """Legacy immediate plan change (dev / admin). Prefer checkout for paid upgrades."""
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        ensure_default_plans()
        code = (request.data.get("plan_code") or "").strip().upper()
        if code not in PlanCode.values:
            return Response({"detail": "Invalid plan_code"}, status=400)
        plan = SubscriptionPlan.objects.get(code=code)
        sub = ensure_subscription(organization)
        sub.plan = plan
        sub.status = SubscriptionStatus.ACTIVE
        sub.read_only = False
        sub.trial_ends_at = None
        sub.save(update_fields=["plan", "status", "read_only", "trial_ends_at", "updated_at"])
        return Response(_sub_payload(organization, sub))


class CheckoutView(APIView):
    """NP-284 — Paket seç → ödeme oturumu."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.MANAGE_SETTINGS

    def post(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        try:
            result = start_checkout(
                organization,
                plan_code=request.data.get("plan_code") or "",
                payment_token=request.data.get("payment_token") or "",
            )
        except PaymentError as exc:
            return Response({"detail": exc.message, "code": exc.code}, status=400)
        return Response(result, status=status.HTTP_201_CREATED)


class PaymentWebhookView(APIView):
    """NP-284 — webhook doğrula → abonelik aktif / dunning."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        raw = request.body.decode("utf-8") if request.body else json.dumps(request.data)
        signature = request.headers.get("X-Billing-Signature") or request.data.get("signature") or ""
        try:
            result = process_webhook(
                event=request.data.get("event") or "",
                checkout_id=request.data.get("checkout_id") or "",
                plan_code=request.data.get("plan_code") or "",
                raw_body=raw,
                signature=signature,
            )
        except PaymentError as exc:
            code = 401 if exc.code == "invalid_signature" else 400
            return Response({"detail": exc.message, "code": exc.code}, status=code)
        return Response(result)


class SubscriptionCancelView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.MANAGE_SETTINGS

    def post(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        at_end = request.data.get("at_period_end", True)
        if isinstance(at_end, str):
            at_end = at_end.lower() not in ("0", "false", "no")
        sub = cancel_subscription(organization, at_period_end=bool(at_end))
        return Response(_sub_payload(organization, sub))


class ScheduleDowngradeView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.MANAGE_SETTINGS

    def post(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        try:
            sub = schedule_downgrade(organization, request.data.get("plan_code") or "")
        except PaymentError as exc:
            return Response({"detail": exc.message, "code": exc.code}, status=400)
        except SubscriptionPlan.DoesNotExist:
            return Response({"detail": "Plan bulunamadı."}, status=404)
        return Response(_sub_payload(organization, sub))


class PaymentMethodView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.MANAGE_SETTINGS

    def post(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        brand = (request.data.get("brand") or "").strip()
        last4 = (request.data.get("last4") or "").strip()
        if not brand or len(last4) != 4 or not last4.isdigit():
            return Response({"detail": "brand ve 4 haneli last4 gerekli."}, status=400)
        sub = update_payment_method(
            organization,
            brand=brand,
            last4=last4,
            provider_customer_id=request.data.get("provider_customer_id") or "",
        )
        return Response(_sub_payload(organization, sub))


class UsageView(APIView):
    """NP-282 — kullanım özeti."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS

    def get(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        return Response(usage_summary(organization))

    def post(self, request):
        """Internal/test meter increment."""
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        metric = (request.data.get("metric") or "").strip()
        quantity = int(request.data.get("quantity") or 1)
        if not metric:
            return Response({"detail": "metric required"}, status=400)
        rec = record_usage(organization, metric, quantity)
        return Response(
            {"metric": rec.metric, "quantity": rec.quantity, "period_start": rec.period_start.isoformat()}
        )


class TrialView(APIView):
    """NP-283 — deneme durumu + ilerleme checklist."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS

    def get(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        return Response(trial_progress(organization))


class BillingInvoiceListView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS

    def get(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        qs = BillingInvoice.objects.filter(organization=organization).order_by("-created_at")[:50]
        return Response({"results": [invoice_download_payload(i) for i in qs]})


class BillingInvoiceDownloadView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS

    def get(self, request, pk: int):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        inv = BillingInvoice.objects.filter(organization=organization, pk=pk).first()
        if inv is None:
            return Response({"detail": "Not found"}, status=404)
        payload = invoice_download_payload(inv)
        # Text downloadable representation (JSON invoice statement)
        body = json.dumps(payload, ensure_ascii=False, indent=2)
        response = HttpResponse(body, content_type="application/json; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{inv.number}.json"'
        return response


class EntitlementCheckView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.VIEW_REPORTS

    def get(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        feature = (request.query_params.get("feature") or "").strip()
        if not feature:
            return Response({"detail": "feature required"}, status=400)
        quantity = int(request.query_params.get("quantity") or 1)
        result = can_use(organization, feature, quantity=quantity)
        return Response(result.as_dict())

    def post(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        feature = (request.data.get("feature") or "").strip()
        quantity = int(request.data.get("quantity") or 1)
        result = can_use(organization, feature, quantity=quantity)
        return Response(
            result.as_dict(),
            status=status.HTTP_200_OK if result.allowed else status.HTTP_403_FORBIDDEN,
        )


class AdminRevenueView(APIView):
    """NP-286 — platform admin gelir paneli."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        return Response(revenue_metrics())


class DunningProcessView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        processed = process_due_retries()
        return Response({"processed": processed})
