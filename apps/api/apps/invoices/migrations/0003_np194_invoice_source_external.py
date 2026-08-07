# NP-194 — invoice source / external_id unique

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("invoices", "0002_invoice_payment_completion_date_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="source",
            field=models.CharField(
                choices=[("MANUAL", "Manual"), ("KOLAYBI", "KolayBi")],
                db_index=True,
                default="MANUAL",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="invoice",
            name="external_id",
            field=models.CharField(blank=True, db_index=True, default="", max_length=128),
        ),
        migrations.AddField(
            model_name="invoice",
            name="last_synced_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="invoice",
            constraint=models.UniqueConstraint(
                condition=~models.Q(external_id=""),
                fields=("organization", "source", "external_id"),
                name="unique_external_invoice",
            ),
        ),
    ]
