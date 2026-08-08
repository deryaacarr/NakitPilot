from django.contrib import admin

from apps.platform.models import (
    FeatureFlag,
    ImpersonationSession,
    MaintenanceWindow,
    PlatformAuditLog,
    SupportTicket,
)

admin.site.register(FeatureFlag)
admin.site.register(MaintenanceWindow)
admin.site.register(ImpersonationSession)
admin.site.register(SupportTicket)
admin.site.register(PlatformAuditLog)
