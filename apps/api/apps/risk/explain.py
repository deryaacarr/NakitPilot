"""Human-readable risk explanations (NP-224)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.utils import timezone

from apps.collections.models import PaymentPromise, PaymentPromiseStatus
from apps.customers.features import extract_customer_features
from apps.customers.models import Customer, RiskStatus
from apps.risk.enums import LEVEL_LABELS_TR
from apps.risk.models import RiskPrediction, RiskSnapshot
from apps.risk.rules import compute_customer_risk_score, risk_level_for_score

LEVEL_DISPLAY = {
    RiskStatus.LOW: "Düşük",
    RiskStatus.MEDIUM: "Orta",
    RiskStatus.HIGH: "Yüksek",
    RiskStatus.CRITICAL: "Kritik",
}


def _sign(points: int) -> str:
    return "+" if points >= 0 else "-"


def _narrative_reasons(
    customer: Customer,
    *,
    reasons: list[dict[str, Any]],
    meta: dict[str, Any],
    features: dict[str, Any],
) -> list[dict[str, Any]]:
    """Turn rule reasons + features into NP-224 style narrative bullets."""
    out: list[dict[str, Any]] = []
    used_codes: set[str] = set()

    broken_count = PaymentPromise.objects.filter(
        customer=customer,
        status=PaymentPromiseStatus.BROKEN,
    ).count()

    for reason in reasons:
        code = reason.get("code") or ""
        points = int(reason.get("points") or 0)
        text = reason.get("label") or code
        used_codes.add(code)

        if code == "BROKEN_PROMISE":
            if broken_count <= 1:
                text = "Ödeme sözü bozuldu"
            elif broken_count == 2:
                text = "Son iki ödeme sözü bozuldu"
            else:
                text = f"Son {broken_count} ödeme sözü bozuldu"
        elif code == "OVER_CREDIT_LIMIT":
            open_bal = features.get("overdue_balance")
            # Prefer credit utilization ratio from features
            util = features.get("credit_utilization_ratio")
            if util is None:
                try:
                    limit = Decimal(str(meta.get("credit_limit") or 0))
                    open_amt = Decimal(str(meta.get("open_balance") or 0))
                    util = float(open_amt / limit) if limit > 0 else None
                except Exception:
                    util = None
            if util is not None:
                pct = int(round(float(util) * 100))
                text = f"Açık bakiye kredi limitinin %{pct}'i"
            else:
                text = "Kredi limitinin üzerinde açık bakiye"
        elif code == "OVERDUE_GT_30":
            days = meta.get("max_overdue_days") or features.get("maximum_overdue_days")
            text = (
                f"En uzun gecikme {int(days)} gün"
                if days is not None
                else "30 günden fazla gecikme"
            )
        elif code == "OVERDUE_GT_60":
            text = "60 günden fazla gecikme"
        elif code == "OVERDUE_GT_90":
            text = "90 günden fazla gecikme"
        elif code == "LAST_PAYMENT_ON_TIME":
            text = "Son ödeme zamanında yapıldı"
        elif code == "REGULAR_PAYMENT_HISTORY":
            text = "Düzenli ödeme geçmişi"
        elif code == "TWO_OF_LAST_THREE_LATE":
            text = "Son 3 faturadan 2'si geç ödendi"
        elif code == "NO_CONTACT_7D":
            text = "Son 7 günde iletişim kurulamadı"

        out.append(
            {
                "sign": _sign(points),
                "text": text,
                "code": code,
                "points": points,
            }
        )

    # Feature-driven extras not already covered by a rule code
    avg_delay = features.get("average_payment_delay")
    if avg_delay is not None and float(avg_delay) >= 7:
        if "AVG_PAYMENT_DELAY" not in used_codes:
            days = int(round(float(avg_delay)))
            out.append(
                {
                    "sign": "+",
                    "text": f"Ortalama ödeme gecikmesi {days} gün",
                    "code": "AVG_PAYMENT_DELAY",
                    "points": 0,
                }
            )

    on_time_ratio = features.get("on_time_payment_ratio")
    if (
        on_time_ratio is not None
        and 0 < float(on_time_ratio) < 1
        and "LAST_PAYMENT_ON_TIME" not in used_codes
        and "PARTIAL_ON_TIME" not in used_codes
    ):
        # Mild positive signal: some payments were on time
        if float(on_time_ratio) >= 0.4:
            out.append(
                {
                    "sign": "-",
                    "text": "Son ödeme kısmen zamanında yapıldı",
                    "code": "PARTIAL_ON_TIME",
                    "points": -5,
                }
            )

    # Sort: risk drivers first (positive points), then mitigations
    out.sort(key=lambda r: (-abs(int(r["points"] or 0)), r["sign"] != "+"))
    return out


def build_risk_explanation(
    customer: Customer,
    *,
    as_of: date | None = None,
    score: int | None = None,
    level: str | None = None,
    reasons: list[dict[str, Any]] | None = None,
    meta: dict[str, Any] | None = None,
    features: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    NP-224 explanation payload.

    Example headline: ``Risk skoru: 78 — Yüksek``
    """
    as_of = as_of or timezone.localdate()
    if score is None or level is None or reasons is None or meta is None:
        rule_score, rule_level, details = compute_customer_risk_score(
            customer, as_of=as_of
        )
        score = score if score is not None else rule_score
        level = level or rule_level
        reasons = reasons if reasons is not None else details.get("reasons", [])
        meta = meta if meta is not None else details.get("meta", {})

    if features is None:
        features = extract_customer_features(customer, as_of=as_of)["features"]

    level = level or risk_level_for_score(int(score or 0))
    level_label = LEVEL_DISPLAY.get(level) or LEVEL_LABELS_TR.get(level, level)
    narrative = _narrative_reasons(
        customer,
        reasons=list(reasons or []),
        meta=meta or {},
        features=features or {},
    )

    headline = f"Risk skoru: {int(score)} — {level_label}"
    return {
        "customer_id": customer.id,
        "score": int(score),
        "level": level,
        "level_label": level_label,
        "headline": headline,
        "reasons": narrative,
        "as_of": as_of.isoformat(),
    }


def explain_customer_risk(
    customer_id: int,
    *,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Prefer latest snapshot/prediction; fall back to live computation."""
    customer = Customer.objects.select_related("organization").get(pk=customer_id)
    as_of = as_of or timezone.localdate()

    snap = (
        RiskSnapshot.objects.filter(customer_id=customer_id)
        .order_by("-calculated_at", "-id")
        .first()
    )
    pred = (
        RiskPrediction.objects.filter(customer_id=customer_id)
        .order_by("-prediction_date", "-id")
        .first()
    )

    details = (snap.score_details if snap else {}) or {}
    features = (pred.feature_values if pred else None) or None
    score = snap.score if snap else customer.risk_score
    level = snap.risk_level if snap else customer.risk_status

    explanation = build_risk_explanation(
        customer,
        as_of=as_of,
        score=score,
        level=level,
        reasons=details.get("reasons"),
        meta=details.get("meta"),
        features=features,
    )
    if snap:
        explanation["snapshot_id"] = snap.id
        explanation["calculated_at"] = snap.calculated_at.isoformat().replace(
            "+00:00", "Z"
        )
    return explanation
