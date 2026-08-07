from django.urls import path

from apps.billing.views import EntitlementCheckView, PlanListView, SubscriptionMeView

urlpatterns = [
    path("plans/", PlanListView.as_view(), name="billing-plans"),
    path("subscription/", SubscriptionMeView.as_view(), name="billing-subscription"),
    path("can-use/", EntitlementCheckView.as_view(), name="billing-can-use"),
]
