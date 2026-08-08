from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0004_np340_354_pwa_legal"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("organizations", "0003_invitation"),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationPreference",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("muted_types", models.JSONField(blank=True, default=list)),
                ("mute_info", models.BooleanField(default=False)),
                ("mute_system", models.BooleanField(default=False)),
                ("group_by_customer", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(app_label)s_%(class)s_set",
                        to="organizations.organization",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notification_preferences",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "notification preference",
                "verbose_name_plural": "notification preferences",
                "ordering": ("-updated_at",),
            },
        ),
        migrations.AddConstraint(
            model_name="notificationpreference",
            constraint=models.UniqueConstraint(
                fields=("organization", "user"),
                name="notifications_pref_org_user_uniq",
            ),
        ),
    ]
