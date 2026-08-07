import uuid

from django.db import migrations, models


def fill_public_ids(apps, schema_editor):
    WebhookDelivery = apps.get_model("webhooks", "WebhookDelivery")
    for row in WebhookDelivery.objects.filter(public_id__isnull=True).iterator():
        row.public_id = uuid.uuid4()
        row.save(update_fields=["public_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("webhooks", "0001_np203_webhook_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="webhookdelivery",
            name="public_id",
            field=models.UUIDField(null=True, editable=False),
        ),
        migrations.RunPython(fill_public_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="webhookdelivery",
            name="public_id",
            field=models.UUIDField(
                default=uuid.uuid4, editable=False, unique=True, db_index=True
            ),
        ),
        migrations.AlterField(
            model_name="webhookdelivery",
            name="max_attempts",
            field=models.PositiveIntegerField(default=7),
        ),
    ]
