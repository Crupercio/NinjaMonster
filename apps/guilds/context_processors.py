"""Template context helpers for guild-aware navigation."""

from __future__ import annotations

from .models import GuildMembership


def nav_guild(request):
    """Provide the current user's guild membership for nav rendering."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"nav_guild_membership": None}

    membership = (
        GuildMembership.objects.select_related("guild")
        .filter(user=user)
        .first()
    )
    return {"nav_guild_membership": membership}
