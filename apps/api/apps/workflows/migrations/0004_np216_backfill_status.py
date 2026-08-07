# Generated manually for NP-216 backfill

from django.db import migrations
from django.utils import timezone


def forwards(apps, schema_editor):
    CollectionWorkflow = apps.get_model("workflows", "CollectionWorkflow")
    for wf in CollectionWorkflow.objects.all():
        updates = []
        if wf.is_active:
            wf.status = "published"
            if not wf.published_at:
                wf.published_at = timezone.now()
            updates.extend(["status", "published_at"])
        else:
            wf.status = "draft"
            updates.append("status")
        # Ensure workflow_key is unique-ish string
        if not wf.workflow_key:
            import uuid

            wf.workflow_key = str(uuid.uuid4())
            updates.append("workflow_key")
        if updates:
            wf.save(update_fields=updates)


def backwards(apps, schema_editor):
    CollectionWorkflow = apps.get_model("workflows", "CollectionWorkflow")
    CollectionWorkflow.objects.filter(status="published").update(is_active=True)
    CollectionWorkflow.objects.exclude(status="published").update(is_active=False)


class Migration(migrations.Migration):
    dependencies = [
        ("workflows", "0003_np215_216_versioning"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
