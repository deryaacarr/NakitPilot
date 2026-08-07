from django.db import migrations


def forwards(apps, schema_editor):
    Dispute = apps.get_model("collections", "Dispute")
    Dispute.objects.filter(status="IN_REVIEW").update(status="UNDER_REVIEW")


def backwards(apps, schema_editor):
    Dispute = apps.get_model("collections", "Dispute")
    Dispute.objects.filter(status="UNDER_REVIEW").update(status="IN_REVIEW")


class Migration(migrations.Migration):
    dependencies = [
        ("collections", "0004_np251_270_disputes_segments_payables"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
