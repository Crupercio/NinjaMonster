"""Template context helpers for user-aware navigation."""
from __future__ import annotations


def ach_pending(request) -> dict:
    """Inject unclaimed achievement count for the sidebar badge."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"ach_pending_count": 0}

    from apps.users.achievement_service import AchievementService
    return {"ach_pending_count": AchievementService().pending_count(user)}


def guide_context(request) -> dict:
    """Inject onboarding guide state for the floating guide panel."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"guide_active": False}

    from apps.users.guide_service import get_guide_context
    return get_guide_context(user)
