from django.contrib import admin

from apps.onboarding.models import FeatureAnnouncement, OnboardingState, ProductAnalyticsEvent


@admin.register(OnboardingState)
class OnboardingStateAdmin(admin.ModelAdmin):
    list_display = ("organization", "current_step", "wizard_completed", "sample_data_enabled")


@admin.register(FeatureAnnouncement)
class FeatureAnnouncementAdmin(admin.ModelAdmin):
    list_display = ("key", "title", "is_active", "created_at")
    list_filter = ("is_active",)


@admin.register(ProductAnalyticsEvent)
class ProductAnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ("event_name", "organization", "occurred_at")
    list_filter = ("event_name",)
