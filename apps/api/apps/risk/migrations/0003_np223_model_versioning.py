# Generated manually for NP-223 model versioning schema

from django.db import migrations, models


def forwards_status(apps, schema_editor):
    RiskModelVersion = apps.get_model("risk", "RiskModelVersion")
    RiskModelVersion.objects.filter(status="ready").update(status="candidate")
    RiskModelVersion.objects.filter(status="published").update(status="active")


class Migration(migrations.Migration):

    dependencies = [
        ("risk", "0002_np221_222_dataset_registry"),
    ]

    operations = [
        migrations.AddField(
            model_name="riskmodelversion",
            name="training_data_range",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='e.g. {"from": "2025-01-01", "to": "2026-01-01", "n_rows": 120}',
            ),
        ),
        migrations.RenameField(
            model_name="riskmodelversion",
            old_name="metrics",
            new_name="metrics_json",
        ),
        migrations.RenameField(
            model_name="riskmodelversion",
            old_name="feature_names",
            new_name="feature_list_json",
        ),
        migrations.AlterField(
            model_name="riskmodelversion",
            name="status",
            field=models.CharField(
                choices=[
                    ("training", "Training"),
                    ("candidate", "Candidate"),
                    ("active", "Active"),
                    ("retired", "Retired"),
                    ("failed", "Failed"),
                ],
                db_index=True,
                default="training",
                max_length=16,
            ),
        ),
        migrations.RunPython(forwards_status, migrations.RunPython.noop),
    ]

