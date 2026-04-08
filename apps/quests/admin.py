from django.contrib import admin

from .models import QuestTemplate, UserQuest


@admin.register(QuestTemplate)
class QuestTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "quest_type", "condition", "condition_value", "reward_summary", "is_active", "order"]
    list_filter = ["quest_type", "condition", "is_active"]
    search_fields = ["name"]
    ordering = ["quest_type", "order"]


@admin.register(UserQuest)
class UserQuestAdmin(admin.ModelAdmin):
    list_display = ["user", "template", "period_key", "progress", "completed", "rewarded", "assigned_at"]
    list_filter = ["completed", "rewarded", "template__quest_type"]
    search_fields = ["user__username", "template__name"]
    raw_id_fields = ["user", "template"]
