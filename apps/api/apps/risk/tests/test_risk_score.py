from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.collections.models import PaymentPromise, PaymentPromiseStatus
from apps.customers.models import Customer, RiskStatus
from apps.invoices.models import Invoice, InvoiceStatus
from apps.organizations.models import Organization
from apps.risk.rules import clamp_score, compute_customer_risk_score, risk_level_for_score
from apps.risk.services import calculate_customer_risk, recalculate_customer_risk

User = get_user_model()


@pytest.fixture
def org_customer(db):
    org = Organization.objects.create(name="Risk Co", slug="risk-co")
    customer = Customer.objects.create(
        organization=org,
        name="Riskli",
        code="R-1",
        credit_limit=Decimal("1000.00"),
        last_contact_at=timezone.now(),
    )
    return org, customer


def _invoice(org, customer, *, number, due, total, status, paid_on=None):
    inv = Invoice.objects.create(
        organization=org,
        customer=customer,
        number=number,
        invoice_date=due - timedelta(days=30),
        due_date=due,
        total_amount=Decimal(total),
        status=status,
        payment_completion_date=paid_on,
    )
    return inv


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0, RiskStatus.LOW),
        (24, RiskStatus.LOW),
        (25, RiskStatus.MEDIUM),
        (49, RiskStatus.MEDIUM),
        (50, RiskStatus.HIGH),
        (74, RiskStatus.HIGH),
        (75, RiskStatus.CRITICAL),
        (100, RiskStatus.CRITICAL),
    ],
)
def test_risk_level_bands_np101(score, expected):
    assert risk_level_for_score(score) == expected


@pytest.mark.django_db
def test_overdue_buckets_stack(org_customer):
    org, customer = org_customer
    today = date.today()
    _invoice(
        org,
        customer,
        number="O90",
        due=today - timedelta(days=95),
        total="500.00",
        status=InvoiceStatus.OVERDUE,
    )
    score, level, details = compute_customer_risk_score(customer, as_of=today)
    codes = {r["code"]: r["points"] for r in details["reasons"]}
    assert codes.get("OVERDUE_GT_30") == 20
    assert codes.get("OVERDUE_GT_60") == 15
    assert codes.get("OVERDUE_GT_90") == 15
    # + contact? last_contact is now → no +10. No broken. Over limit? remaining 500 < 1000
    assert score == 50
    assert level == RiskStatus.HIGH


@pytest.mark.django_db
def test_two_of_last_three_late_and_broken_promise(org_customer):
    org, customer = org_customer
    today = date.today()
    for i, delay in enumerate([5, 3, -1]):
        _invoice(
            org,
            customer,
            number=f"P{i}",
            due=today - timedelta(days=40 + i),
            total="100.00",
            status=InvoiceStatus.PAID,
            paid_on=today - timedelta(days=40 + i) + timedelta(days=delay),
        )
    PaymentPromise.objects.create(
        organization=org,
        customer=customer,
        promised_date=today - timedelta(days=2),
        amount=Decimal("50.00"),
        status=PaymentPromiseStatus.BROKEN,
    )
    score, _, details = compute_customer_risk_score(customer, as_of=today)
    codes = {r["code"]: r for r in details["reasons"]}
    assert codes["TWO_OF_LAST_THREE_LATE"]["points"] == 15
    assert codes["BROKEN_PROMISE"]["points"] == 25
    assert codes["BROKEN_PROMISE"]["label"] == "Ödeme sözü tutulmadı"
    assert score >= 40


@pytest.mark.django_db
def test_credits_and_clamp(org_customer):
    org, customer = org_customer
    today = date.today()
    for i in range(4):
        due = today - timedelta(days=20 * (i + 1))
        _invoice(
            org,
            customer,
            number=f"G{i}",
            due=due,
            total="100.00",
            status=InvoiceStatus.PAID,
            paid_on=due,
        )
    score, _, details = compute_customer_risk_score(customer, as_of=today)
    codes = {r["code"]: r["points"] for r in details["reasons"]}
    assert codes.get("REGULAR_PAYMENT_HISTORY") == -15
    assert codes.get("LAST_PAYMENT_ON_TIME") == -10
    assert score == clamp_score(score)
    assert 0 <= score <= 100

    snap = recalculate_customer_risk(customer)
    customer.refresh_from_db()
    assert customer.risk_score == snap.score
    assert snap.score_details["score"] == snap.score
    assert "reasons" in snap.score_details


@pytest.mark.django_db
def test_no_contact_and_over_limit(org_customer):
    org, customer = org_customer
    today = date.today()
    customer.last_contact_at = None
    customer.credit_limit = Decimal("100.00")
    customer.save()
    _invoice(
        org,
        customer,
        number="OL",
        due=today + timedelta(days=10),
        total="500.00",
        status=InvoiceStatus.OPEN,
    )
    score, level, details = compute_customer_risk_score(customer, as_of=today)
    codes = {r["code"]: r["points"] for r in details["reasons"]}
    assert codes.get("NO_CONTACT_7D") == 10
    assert codes.get("OVER_CREDIT_LIMIT") == 15
    assert score == 25
    assert level == RiskStatus.MEDIUM


@pytest.mark.django_db
def test_calculate_customer_risk_persists_reasons(org_customer):
    org, customer = org_customer
    today = date.today()
    PaymentPromise.objects.create(
        organization=org,
        customer=customer,
        promised_date=today - timedelta(days=1),
        amount=Decimal("100.00"),
        status=PaymentPromiseStatus.BROKEN,
    )
    result = calculate_customer_risk(customer.id, as_of=today)
    assert {"score", "level", "reasons", "rule_score", "model_score", "final_score", "prediction_id"} <= set(
        result.keys()
    )
    assert "explanation" in result
    assert result["score"] == result["final_score"]
    assert isinstance(result["reasons"], list)
    broken = next(r for r in result["reasons"] if r["code"] == "BROKEN_PROMISE")
    assert broken == {
        "code": "BROKEN_PROMISE",
        "label": "Ödeme sözü tutulmadı",
        "points": 25,
    }
    customer.refresh_from_db()
    assert customer.risk_score == result["score"]
    assert customer.risk_status == result["level"]
    from apps.risk.models import RiskSnapshot

    snap = RiskSnapshot.objects.filter(customer=customer).latest("calculated_at")
    assert snap.score_details["reasons"] == result["reasons"]
    assert snap.score == result["score"]
    assert snap.risk_level == result["level"]
