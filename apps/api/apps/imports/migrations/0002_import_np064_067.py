# Generated manually for NP-064–067

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("imports", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="importjob",
            name="duplicate_policy",
            field=models.CharField(
                choices=[
                    ("SKIP", "Skip row"),
                    ("UPDATE", "Update existing"),
                    ("CREATE", "Create as new"),
                ],
                default="SKIP",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="importjob",
            name="result_summary",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="importjob",
            name="successful_rows",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="importjob",
            name="failed_rows",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="importjob",
            name="skipped_duplicates",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="importjob",
            name="celery_task_id",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="importerror",
            name="kind",
            field=models.CharField(
                choices=[
                    ("VALIDATION", "Validation"),
                    ("DUPLICATE", "Duplicate"),
                    ("SKIPPED", "Skipped"),
                    ("SYSTEM", "System"),
                ],
                default="VALIDATION",
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name="importjob",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("VALIDATING", "Validating"),
                    ("READY", "Ready"),
                    ("PROCESSING", "Processing"),
                    ("COMPLETED", "Completed"),
                    ("FAILED", "Failed"),
                    ("CANCELLED", "Cancelled"),
                ],
                default="PENDING",
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="importjob",
            name="column_mapping",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
