# Generated for EPIC 16

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("organizations", "0003_invitation"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ExportJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "report_type",
                    models.CharField(
                        choices=[
                            ("OVERDUE_RECEIVABLES", "Gecikmiş alacak"),
                            ("COLLECTION_ACTIVITY", "Tahsilat aktivite"),
                            ("CUSTOMER_RISK", "Müşteri risk"),
                        ],
                        max_length=64,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PREPARING", "Hazırlanıyor"),
                            ("READY", "Hazır"),
                            ("FAILED", "Başarısız"),
                            ("EXPIRED", "Süresi doldu"),
                        ],
                        db_index=True,
                        default="PREPARING",
                        max_length=16,
                    ),
                ),
                ("filters", models.JSONField(blank=True, default=dict)),
                ("original_filename", models.CharField(blank=True, max_length=255)),
                ("stored_path", models.CharField(blank=True, max_length=512)),
                ("file_size", models.PositiveIntegerField(default=0)),
                ("row_count", models.PositiveIntegerField(default=0)),
                ("celery_task_id", models.CharField(blank=True, max_length=255)),
                ("error_message", models.TextField(blank=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(app_label)s_%(class)s_set",
                        to="organizations.organization",
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="report_export_jobs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "export job",
                "verbose_name_plural": "export jobs",
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddIndex(
            model_name="exportjob",
            index=models.Index(fields=["organization", "status", "created_at"], name="reports_exp_organiz_idx"),
        ),
        migrations.AddIndex(
            model_name="exportjob",
            index=models.Index(fields=["organization", "report_type"], name="reports_exp_organiz_type_idx"),
        ),
    ]
