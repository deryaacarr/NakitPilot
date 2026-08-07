# Generated manually for NP-140

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_epic9_dashboard_alerts"),
    ]

    operations = [
        migrations.AddField(
            model_name="dashboardalert",
            name="notification_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("TASK_DUE", "Görev vadesi"),
                    ("TASK_OVERDUE", "Gecikmiş görev"),
                    ("PROMISE_DUE", "Ödeme sözü vadesi"),
                    ("PROMISE_BROKEN", "Bozulan ödeme sözü"),
                    ("HIGH_RISK_CUSTOMER", "Yüksek riskli müşteri"),
                    ("IMPORT_COMPLETED", "İçe aktarma tamamlandı"),
                    ("IMPORT_FAILED", "İçe aktarma başarısız"),
                ],
                db_index=True,
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="dashboardalert",
            name="href",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
