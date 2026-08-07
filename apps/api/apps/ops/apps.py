from django.apps import AppConfig


class OpsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ops"
    label = "ops"
    verbose_name = "Ops & Observability"

    def ready(self):
        # Register structured logging context defaults
        from apps.ops import logging_context  # noqa: F401
