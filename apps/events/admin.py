"""Admin registration for SeasonalEvent."""
from django.contrib import admin

from .models import SeasonalEvent


@admin.register(SeasonalEvent)
class SeasonalEventAdmin(admin.ModelAdmin):
    list_display = ["name", "event_type", "bonus_value", "start_at", "end_at", "is_active", "status_label"]
    list_filter = ["event_type", "is_active"]
    search_fields = ["name", "description"]
    readonly_fields = ["status_label"]
