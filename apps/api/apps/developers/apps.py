from django.apps import AppConfig


class DevelopersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.developers"
    label = "developers"
    verbose_name = "Developer Portal"
