from django.urls import path

from apps.payables.views import (
    BankAccountDetailView,
    BankAccountListCreateView,
    ExpectedExpenseDetailView,
    ExpectedExpenseListCreateView,
    ExpenseCategoryListCreateView,
    NetCashView,
    PayableDetailView,
    PayableListCreateView,
    RecurringExpenseDetailView,
    RecurringExpenseListCreateView,
)

urlpatterns = [
    path("bank-accounts/", BankAccountListCreateView.as_view(), name="bank-account-list"),
    path(
        "bank-accounts/<int:pk>/",
        BankAccountDetailView.as_view(),
        name="bank-account-detail",
    ),
    path("categories/", ExpenseCategoryListCreateView.as_view(), name="expense-categories"),
    path("payables/", PayableListCreateView.as_view(), name="payable-list"),
    path("payables/<int:pk>/", PayableDetailView.as_view(), name="payable-detail"),
    path(
        "recurring/",
        RecurringExpenseListCreateView.as_view(),
        name="recurring-expense-list",
    ),
    path(
        "recurring/<int:pk>/",
        RecurringExpenseDetailView.as_view(),
        name="recurring-expense-detail",
    ),
    path(
        "expected/",
        ExpectedExpenseListCreateView.as_view(),
        name="expected-expense-list",
    ),
    path(
        "expected/<int:pk>/",
        ExpectedExpenseDetailView.as_view(),
        name="expected-expense-detail",
    ),
    path("net-cash/", NetCashView.as_view(), name="net-cash"),
]
