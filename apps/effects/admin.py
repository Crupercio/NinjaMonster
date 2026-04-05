"""Admin registrations for the effects app."""
from django.contrib import admin

from .models import ActiveStatusEffect, StatusEffect


@admin.register(StatusEffect)
class StatusEffectAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "damage_per_turn", "prevents_action", "disables_healing")
    list_filter = ("category", "prevents_action", "disables_healing")
    search_fields = ("name", "description")


@admin.register(ActiveStatusEffect)
class ActiveStatusEffectAdmin(admin.ModelAdmin):
    list_display = ("slot", "status", "remaining_turns", "turns_active", "applied_at_round")
    list_filter = ("status__category",)
    raw_id_fields = ("slot", "status")
