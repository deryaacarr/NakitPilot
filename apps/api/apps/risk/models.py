"""Risk snapshot, prediction dataset, and model registry (NP-073, NP-221–223)."""

from __future__ import annotations

from django.db import models

from apps.customers.models import RiskStatus
from apps.organizations.tenancy import TenantModel
from apps.risk.enums import RiskAlgorithm, RiskModelStatus


class RiskSnapshot(TenantModel):
    """Point-in-time rule-based risk score for a customer."""

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="risk_snapshots",
    )
    score = models.PositiveSmallIntegerField(default=0)
    risk_level = models.CharField(
        max_length=16,
        choices=RiskStatus.choices,
        default=RiskStatus.LOW,
    )
    score_details = models.JSONField(default=dict, blank=True)
    calculated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-calculated_at",)
        verbose_name = "risk snapshot"
        verbose_name_plural = "risk snapshots"

    def __str__(self) -> str:
        return f"Risk {self.customer_id}: {self.score} ({self.risk_level})"


class RiskModelVersion(TenantModel):
    """
    Model registry entry (NP-222 / NP-223).

    Core fields: version, algorithm, trained_at, training_data_range,
    metrics_json, feature_list_json, status.
    """

    name = models.CharField(max_length=128)
    version = models.CharField(max_length=64)
    algorithm = models.CharField(
        max_length=32,
        choices=RiskAlgorithm.choices,
    )
    target_label = models.CharField(max_length=64)
    training_data_range = models.JSONField(
        default=dict,
        blank=True,
        help_text='e.g. {"from": "2025-01-01", "to": "2026-01-01", "n_rows": 120}',
    )
    metrics_json = models.JSONField(default=dict, blank=True)
    feature_list_json = models.JSONField(default=list, blank=True)
    comparison = models.JSONField(default=dict, blank=True)
    artifact = models.FileField(
        upload_to="risk_models/%Y/%m/",
        blank=True,
        null=True,
    )
    status = models.CharField(
        max_length=16,
        choices=RiskModelStatus.choices,
        default=RiskModelStatus.TRAINING,
        db_index=True,
    )
    notes = models.TextField(blank=True, default="")
    trained_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "risk model version"
        verbose_name_plural = "risk model versions"
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "version"),
                name="risk_model_version_org_version_uniq",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} {self.version} ({self.algorithm})"

    # Back-compat aliases used by older call sites
    @property
    def metrics(self):
        return self.metrics_json

    @property
    def feature_names(self):
        return self.feature_list_json


class RiskPrediction(TenantModel):
    """
    One risk calculation row for the supervised dataset (NP-221).

    Stores features + scores at prediction time; actual_outcome is filled
    later once outcome horizons elapse.
    """

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="risk_predictions",
    )
    snapshot = models.ForeignKey(
        RiskSnapshot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="predictions",
    )
    feature_values = models.JSONField(default=dict, blank=True)
    rule_score = models.PositiveSmallIntegerField(default=0)
    model_score = models.FloatField(null=True, blank=True)
    final_score = models.PositiveSmallIntegerField(default=0)
    prediction_date = models.DateField(db_index=True)
    outcome_date = models.DateField(
        null=True,
        blank=True,
        help_text="Earliest date when all outcome labels can be evaluated.",
    )
    actual_outcome = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            "Resolved labels: paid_within_30d, paid_within_60d, invoice_90plus_overdue."
        ),
    )
    model_version = models.ForeignKey(
        RiskModelVersion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="predictions",
    )
    outcomes_resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-prediction_date", "-id")
        verbose_name = "risk prediction"
        verbose_name_plural = "risk predictions"
        indexes = [
            models.Index(
                fields=("organization", "prediction_date"),
                name="risk_pred_org_pred_date_idx",
            ),
            models.Index(
                fields=("organization", "outcomes_resolved_at"),
                name="risk_pred_org_resolved_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"Prediction {self.customer_id} @ {self.prediction_date}: {self.final_score}"
