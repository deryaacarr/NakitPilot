"""ForecastSnapshot — weekly cash collection forecast (NP-112)."""

from __future__ import annotations

from decimal import Decimal

from django.db import models

from apps.organizations.tenancy import TenantModel

ZERO = Decimal("0.00")


class ForecastSnapshot(TenantModel):
    """One week bucket for an organization forecast run."""

    week_start = models.DateField(db_index=True)
    week_index = models.PositiveSmallIntegerField(default=0)
    currency = models.CharField(max_length=3, default="TRY")
    nominal_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    expected_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    optimistic_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    pessimistic_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    calculation_details = models.JSONField(default=dict, blank=True)
    calculated_at = models.DateTimeField(auto_now_add=True)
    run_id = models.CharField(max_length=36, db_index=True, blank=True, default="")

    class Meta:
        ordering = ("week_start", "id")
        verbose_name = "forecast snapshot"
        verbose_name_plural = "forecast snapshots"
        indexes = [
            models.Index(fields=["organization", "run_id", "week_start"]),
        ]

    def __str__(self) -> str:
        return f"Forecast {self.week_start}: exp={self.expected_amount}"
