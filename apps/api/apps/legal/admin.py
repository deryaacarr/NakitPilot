from django.contrib import admin

from apps.legal.models import (
    LegalCase,
    LegalCaseActivity,
    LegalCaseDocument,
    LegalCaseInvoice,
    LegalCaseStatusHistory,
)

admin.site.register(LegalCase)
admin.site.register(LegalCaseInvoice)
admin.site.register(LegalCaseActivity)
admin.site.register(LegalCaseDocument)
admin.site.register(LegalCaseStatusHistory)
