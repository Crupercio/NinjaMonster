"""Admin for the guild system."""
from django.contrib import admin

from .models import Guild, GuildMembership


class GuildMembershipInline(admin.TabularInline):
    model = GuildMembership
    extra = 0
    readonly_fields = ["joined_at"]


@admin.register(Guild)
class GuildAdmin(admin.ModelAdmin):
    list_display = ["name", "tag", "member_count", "is_recruiting", "created_at"]
    list_filter = ["is_recruiting"]
    search_fields = ["name", "tag"]
    inlines = [GuildMembershipInline]


@admin.register(GuildMembership)
class GuildMembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "guild", "role", "joined_at"]
    list_filter = ["role"]
    search_fields = ["user__username", "guild__name"]
