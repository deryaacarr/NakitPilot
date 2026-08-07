# Generated manually for NP-190

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("organizations", "0003_invitation"),
    ]

    operations = [
        migrations.CreateModel(
            name="IntegrationConnection",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "provider",
                    models.CharField(
                        choices=[("kolaybi", "KolayBi")],
                        db_index=True,
                        max_length=64,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("connected", "Connected"),
                            ("error", "Error"),
                            ("disabled", "Disabled"),
                        ],
                        db_index=True,
                        default="draft",
                        max_length=32,
                    ),
                ),
                (
                    "external_company_id",
                    models.CharField(blank=True, default="", max_length=128),
                ),
                (
                    "external_company_name",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("settings_json", models.JSONField(blank=True, default=dict)),
                ("last_sync_at", models.DateTimeField(blank=True, null=True)),
                ("last_successful_sync_at", models.DateTimeField(blank=True, null=True)),
                ("next_sync_at", models.DateTimeField(blank=True, null=True)),
                (
                    "sync_frequency",
                    models.CharField(
                        choices=[
                            ("manual", "Manual"),
                            ("hourly", "Hourly"),
                            ("daily", "Daily"),
                        ],
                        default="manual",
                        max_length=32,
                    ),
                ),
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
                "verbose_name": "integration connection",
                "verbose_name_plural": "integration connections",
                "ordering": ("-created_at",),
            },
        ),
        migrations.CreateModel(
            name="IntegrationCredential",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("encrypted_payload", models.TextField()),
                ("key_hint", models.CharField(blank=True, default="", max_length=16)),
                ("rotated_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "connection",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="credential",
                        to="integrations.integrationconnection",
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
            ],
            options={
                "verbose_name": "integration credential",
                "verbose_name_plural": "integration credentials",
            },
        ),
        migrations.CreateModel(
            name="SyncJob",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("job_type", models.CharField(default="full", max_length=64)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("running", "Running"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                            ("cancelled", "Cancelled"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=32,
                    ),
                ),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("stats_json", models.JSONField(blank=True, default=dict)),
                (
                    "celery_task_id",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("error_message", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "connection",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sync_jobs",
                        to="integrations.integrationconnection",
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
            ],
            options={
                "verbose_name": "sync job",
                "verbose_name_plural": "sync jobs",
                "ordering": ("-created_at",),
            },
        ),
        migrations.CreateModel(
            name="SyncRecord",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("entity_type", models.CharField(db_index=True, max_length=64)),
                (
                    "external_id",
                    models.CharField(blank=True, default="", max_length=128),
                ),
                (
                    "internal_id",
                    models.CharField(blank=True, default="", max_length=64),
                ),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("created", "Created"),
                            ("updated", "Updated"),
                            ("skipped", "Skipped"),
                            ("failed", "Failed"),
                        ],
                        max_length=32,
                    ),
                ),
                ("payload_summary", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "job",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="records",
                        to="integrations.syncjob",
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
            ],
            options={
                "verbose_name": "sync record",
                "verbose_name_plural": "sync records",
                "ordering": ("id",),
            },
        ),
        migrations.CreateModel(
            name="SyncError",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("code", models.CharField(blank=True, default="", max_length=64)),
                ("message", models.TextField()),
                ("raw_detail", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "job",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="errors",
                        to="integrations.syncjob",
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
                    "record",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="errors",
                        to="integrations.syncrecord",
                    ),
                ),
            ],
            options={
                "verbose_name": "sync error",
                "verbose_name_plural": "sync errors",
                "ordering": ("id",),
            },
        ),
        migrations.CreateModel(
            name="ExternalObjectMapping",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("entity_type", models.CharField(db_index=True, max_length=64)),
                ("external_id", models.CharField(max_length=128)),
                ("internal_model", models.CharField(max_length=128)),
                ("internal_id", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "connection",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="object_mappings",
                        to="integrations.integrationconnection",
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
            ],
            options={
                "verbose_name": "external object mapping",
                "verbose_name_plural": "external object mappings",
            },
        ),
        migrations.AddConstraint(
            model_name="integrationconnection",
            constraint=models.UniqueConstraint(
                fields=("organization", "provider", "external_company_id"),
                name="uniq_integration_provider_company_per_org",
            ),
        ),
        migrations.AddIndex(
            model_name="integrationconnection",
            index=models.Index(
                fields=["organization", "provider"],
                name="integ_conn_org_provider_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="externalobjectmapping",
            constraint=models.UniqueConstraint(
                fields=("connection", "entity_type", "external_id"),
                name="uniq_external_object_per_connection",
            ),
        ),
        migrations.AddIndex(
            model_name="externalobjectmapping",
            index=models.Index(
                fields=["organization", "internal_model", "internal_id"],
                name="integ_map_internal_idx",
            ),
        ),
    ]
