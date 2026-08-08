from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("organizations", "0006_np340_354_pwa_legal"),
    ]

    operations = [
        migrations.CreateModel(
            name="SavedTableView",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("resource", models.CharField(db_index=True, max_length=64)),
                ("name", models.CharField(max_length=120)),
                ("filters", models.JSONField(blank=True, default=dict)),
                ("hidden_columns", models.JSONField(blank=True, default=list)),
                ("sort", models.JSONField(blank=True, default=dict)),
                ("is_default", models.BooleanField(default=False)),
                ("is_shared", models.BooleanField(default=False)),
                ("share_token", models.CharField(blank=True, db_index=True, max_length=48)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="saved_table_views",
                        to=settings.AUTH_USER_MODEL,
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
                "verbose_name": "saved table view",
                "verbose_name_plural": "saved table views",
                "ordering": ("name", "id"),
            },
        ),
        migrations.AddIndex(
            model_name="savedtableview",
            index=models.Index(
                fields=["organization", "resource"], name="savedview_org_resource_idx"
            ),
        ),
    ]
