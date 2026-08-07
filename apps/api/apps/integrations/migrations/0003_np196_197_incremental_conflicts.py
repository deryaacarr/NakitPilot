# NP-196 / NP-197 — incremental sync state + conflicts

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0002_np192_last_error"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SyncEntityState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("entity_type", models.CharField(db_index=True, max_length=32)),
                ("last_cursor", models.CharField(blank=True, default="", max_length=512)),
                ("last_remote_update_at", models.DateTimeField(blank=True, null=True)),
                ("last_sync_at", models.DateTimeField(blank=True, null=True)),
                ("last_successful_sync_at", models.DateTimeField(blank=True, null=True)),
                ("checksums_json", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "connection",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sync_states",
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
                "verbose_name": "sync entity state",
                "verbose_name_plural": "sync entity states",
            },
        ),
        migrations.CreateModel(
            name="SyncConflict",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("entity_type", models.CharField(db_index=True, max_length=32)),
                (
                    "conflict_type",
                    models.CharField(
                        choices=[
                            ("duplicate_manual_api", "Duplicate manual + API"),
                            ("local_edited", "Locally edited"),
                            ("payment_amount_changed", "Payment amount changed"),
                            ("customer_merged_or_deleted", "Customer merged or deleted"),
                        ],
                        max_length=64,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("open", "Open"), ("resolved", "Resolved")],
                        db_index=True,
                        default="open",
                        max_length=16,
                    ),
                ),
                ("external_id", models.CharField(blank=True, default="", max_length=128)),
                ("internal_model", models.CharField(blank=True, default="", max_length=128)),
                ("internal_id", models.CharField(blank=True, default="", max_length=64)),
                ("message", models.TextField(blank=True, default="")),
                ("source_payload", models.JSONField(blank=True, default=dict)),
                ("local_snapshot", models.JSONField(blank=True, default=dict)),
                (
                    "resolution",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("use_source", "Use source"),
                            ("keep_local", "Keep local"),
                            ("merge", "Merge"),
                            ("skip_field_forever", "Skip field forever"),
                        ],
                        default="",
                        max_length=32,
                    ),
                ),
                ("resolution_detail", models.JSONField(blank=True, default=dict)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "connection",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="conflicts",
                        to="integrations.integrationconnection",
                    ),
                ),
                (
                    "job",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="conflicts",
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
                    "resolved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="resolved_sync_conflicts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "sync conflict",
                "verbose_name_plural": "sync conflicts",
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddConstraint(
            model_name="syncentitystate",
            constraint=models.UniqueConstraint(
                fields=("connection", "entity_type"),
                name="uniq_sync_state_per_connection_entity",
            ),
        ),
        migrations.AddIndex(
            model_name="syncconflict",
            index=models.Index(
                fields=["connection", "status", "entity_type"],
                name="integ_conflict_conn_status_idx",
            ),
        ),
    ]
