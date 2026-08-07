# NP-192 — connection last_error for status panel

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0001_np190_integrations"),
    ]

    operations = [
        migrations.AddField(
            model_name="integrationconnection",
            name="last_error",
            field=models.TextField(blank=True, default=""),
        ),
    ]
