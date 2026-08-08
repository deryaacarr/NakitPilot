from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

from apps.health.views import ReadyView
from apps.organizations.views import MyMembershipsView


def healthcheck(request):
    """Legacy probe — same as readiness (Docker / nginx)."""
    return ReadyView.as_view()(request)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", healthcheck, name="healthcheck"),
    path("api/health/", include("apps.health.urls")),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/organizations/", include("apps.organizations.urls")),
    path("api/memberships/me/", MyMembershipsView.as_view(), name="membership-me"),
    path("api/customers/", include("apps.customers.urls")),
    path("api/invoices/", include("apps.invoices.urls")),
    path("api/payments/", include("apps.payments.urls")),
    path("api/collection-tasks/", include("apps.collections.urls")),
    path("api/payment-promises/", include("apps.collections.promise_urls")),
    path("api/disputes/", include("apps.collections.dispute_urls")),
    path("api/notifications/", include("apps.notifications.urls")),
    path("api/imports/", include("apps.imports.urls")),
    path("api/integrations/", include("apps.integrations.urls")),
    path("api/api-keys/", include("apps.api_keys.urls")),
    path("api/webhooks/", include("apps.webhooks.urls")),
    path("api/workflows/", include("apps.workflows.urls")),
    path("api/developers/", include("apps.developers.urls")),
    path("api/v1/", include("apps.public_api.urls")),
    path("api/forecast/", include("apps.forecasting.urls")),
    path("api/dashboard/", include("apps.dashboard.urls")),
    path("api/search/", include("apps.dashboard.search_urls")),
    path("api/message-templates/", include("apps.messaging.urls")),
    path("api/public/email/", include("apps.messaging.public_urls")),
    path("api/ai-usage/", include("apps.ai_usage.urls")),
    path("api/reports/", include("apps.reports.urls")),
    path("api/risk/", include("apps.risk.urls")),
    path("api/segments/", include("apps.segments.urls")),
    path("api/payables/", include("apps.payables.urls")),
    path("api/billing/", include("apps.billing.urls")),
    path("api/onboarding/", include("apps.onboarding.urls")),
    path("api/governance/", include("apps.governance.urls")),
    path("api/ops/", include("apps.ops.urls")),
    path("api/legal/", include("apps.legal.urls")),
    path("api/platform/", include("apps.platform.urls")),
]
