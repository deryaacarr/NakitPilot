from django.apps import AppConfig


class PayablesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.payables"
    label = "payables"
    verbose_name = "Payables & expenses"
