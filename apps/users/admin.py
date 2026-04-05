"""Admin registration for the custom User model."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin configuration for the custom User model."""

    list_display = ("username", "email", "display_name", "ryo", "battles_won", "battles_played", "is_staff")
    list_filter = ("is_staff", "is_superuser", "is_active")
    search_fields = ("username", "email", "display_name")
    ordering = ("-date_joined",)

    fieldsets = BaseUserAdmin.fieldsets + (  # type: ignore[operator]
        (
            "Game Profile",
            {
                "fields": (
                    "display_name",
                    "avatar_url",
                    "sticker_dust",
                    "ryo",
                    "last_daily_claim",
                    "battles_won",
                    "battles_played",
                    "longest_combo_chain",
                )
            },
        ),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (  # type: ignore[operator]
        (
            "Game Profile",
            {"fields": ("email", "display_name")},
        ),
    )
