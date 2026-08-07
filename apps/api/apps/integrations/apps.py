from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.integrations"
    label = "integrations"
    verbose_name = "Integrations"

    def ready(self) -> None:
        # Register built-in connectors (KolayBi stub; more providers later).
        from apps.integrations.connectors import kolaybi  # noqa: F401
