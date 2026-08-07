# NP-193 — customer source / external_id / field ownership

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0002_customer_last_contact_at_customer_risk_score_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="collection_strategy",
            field=models.CharField(
                blank=True,
                default="",
                help_text="NakitPilot-managed tahsilat stratejisi (entegrasyon ezmez).",
                max_length=128,
            ),
        ),
        migrations.AddField(
            model_name="customer",
            name="source",
            field=models.CharField(
                choices=[("MANUAL", "Manual"), ("KOLAYBI", "KolayBi")],
                db_index=True,
                default="MANUAL",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="customer",
            name="external_id",
            field=models.CharField(blank=True, db_index=True, default="", max_length=128),
        ),
        migrations.AddField(
            model_name="customer",
            name="local_field_overrides",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="customer",
            name="last_synced_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="customer",
            constraint=models.UniqueConstraint(
                condition=~models.Q(external_id=""),
                fields=("organization", "source", "external_id"),
                name="uniq_customer_external_per_org_source",
            ),
        ),
    ]
