# Generated manually for NP-221 / NP-222

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0004_np211_214_workflow_engine"),
        ("organizations", "0003_invitation"),
        ("risk", "0001_epic7_payments"),
    ]

    operations = [
        migrations.CreateModel(
            name="RiskModelVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=128)),
                ("version", models.CharField(max_length=64)),
                (
                    "algorithm",
                    models.CharField(
                        choices=[
                            ("logistic_regression", "Logistic Regression"),
                            ("gradient_boosting", "Gradient Boosting"),
                            ("random_forest", "Random Forest"),
                        ],
                        max_length=32,
                    ),
                ),
                ("target_label", models.CharField(max_length=64)),
                ("feature_names", models.JSONField(blank=True, default=list)),
                ("metrics", models.JSONField(blank=True, default=dict)),
                ("comparison", models.JSONField(blank=True, default=dict)),
                ("artifact", models.FileField(blank=True, null=True, upload_to="risk_models/%Y/%m/")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("training", "Training"),
                            ("ready", "Ready"),
                            ("published", "Published"),
                            ("retired", "Retired"),
                        ],
                        db_index=True,
                        default="training",
                        max_length=16,
                    ),
                ),
                ("notes", models.TextField(blank=True, default="")),
                ("trained_at", models.DateTimeField(blank=True, null=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(app_label)s_%(class)s_set",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={
                "verbose_name": "risk model version",
                "verbose_name_plural": "risk model versions",
                "ordering": ("-created_at",),
            },
        ),
        migrations.CreateModel(
            name="RiskPrediction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("feature_values", models.JSONField(blank=True, default=dict)),
                ("rule_score", models.PositiveSmallIntegerField(default=0)),
                ("model_score", models.FloatField(blank=True, null=True)),
                ("final_score", models.PositiveSmallIntegerField(default=0)),
                ("prediction_date", models.DateField(db_index=True)),
                (
                    "outcome_date",
                    models.DateField(
                        blank=True,
                        help_text="Earliest date when all outcome labels can be evaluated.",
                        null=True,
                    ),
                ),
                (
                    "actual_outcome",
                    models.JSONField(
                        blank=True,
                        help_text="Resolved labels: paid_within_30d, paid_within_60d, invoice_90plus_overdue.",
                        null=True,
                    ),
                ),
                ("outcomes_resolved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="risk_predictions",
                        to="customers.customer",
                    ),
                ),
                (
                    "model_version",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="predictions",
                        to="risk.riskmodelversion",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(app_label)s_%(class)s_set",
                        to="organizations.organization",
                    ),
                ),
                (
                    "snapshot",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="predictions",
                        to="risk.risksnapshot",
                    ),
                ),
            ],
            options={
                "verbose_name": "risk prediction",
                "verbose_name_plural": "risk predictions",
                "ordering": ("-prediction_date", "-id"),
            },
        ),
        migrations.AddConstraint(
            model_name="riskmodelversion",
            constraint=models.UniqueConstraint(
                fields=("organization", "version"),
                name="risk_model_version_org_version_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="riskprediction",
            index=models.Index(
                fields=["organization", "prediction_date"],
                name="risk_pred_org_pred_date_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="riskprediction",
            index=models.Index(
                fields=["organization", "outcomes_resolved_at"],
                name="risk_pred_org_resolved_idx",
            ),
        ),
    ]
