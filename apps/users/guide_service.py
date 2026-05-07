"""
Guided onboarding service.

7 steps × 10,000 Ryo + 130,000 completion bonus = 200,000 Ryo total.
One-time only — guide_step is monotonically increasing; it never resets.
"""
import logging
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F

logger = logging.getLogger(__name__)

User = get_user_model()

STEP_RYO: int = 10_000
COMPLETION_BONUS: int = 130_000
TOTAL_RYO: int = 7 * STEP_RYO + COMPLETION_BONUS  # 200,000

GUIDE_STEPS: list[dict[str, Any]] = [
    {
        "step": 1,
        "title": "Claim Your Daily Reward",
        "description": "Visit the Daily Claim page and collect your first Ryo.",
        "url_name": "users:daily_claim",
        "icon": "📅",
        "ryo": STEP_RYO,
    },
    {
        "step": 2,
        "title": "Visit the Sticker Shop",
        "description": "Head to the shop and buy your first sticker pack.",
        "url_name": "stickers:buy_pack",
        "icon": "🛍️",
        "ryo": STEP_RYO,
    },
    {
        "step": 3,
        "title": "Open a Sticker Pack",
        "description": "Open any sticker pack to reveal your first stickers.",
        "url_name": "stickers:my_packs",
        "icon": "✨",
        "ryo": STEP_RYO,
    },
    {
        "step": 4,
        "title": "Place a Sticker in Your Album",
        "description": "Visit your Sticker Album and place one sticker.",
        "url_name": "stickers:album",
        "icon": "📒",
        "ryo": STEP_RYO,
    },
    {
        "step": 5,
        "title": "Play the Silhouette Tower",
        "description": "Start a Rookie run in the Silhouette Tower arcade.",
        "url_name": "game:silhouette_hub",
        "icon": "🗼",
        "ryo": STEP_RYO,
    },
    {
        "step": 6,
        "title": "Play Lotería",
        "description": "Join a Lotería room and play a game.",
        "url_name": "game:loteria_game",
        "icon": "🎴",
        "ryo": STEP_RYO,
    },
    {
        "step": 7,
        "title": "Accept a Quest",
        "description": "Visit the Quests page and take on a challenge.",
        "url_name": "quests:quest_list",
        "icon": "📜",
        "ryo": STEP_RYO,
    },
]

GUIDE_COMPLETE_STEP: int = 8  # sentinel value meaning fully done


def get_current_step(user: User) -> dict[str, Any] | None:
    """Return the current step dict, or None if guide is done/dismissed."""
    step = getattr(user, "guide_step", 0)
    if step == 0:
        # Not started yet — return step 1 info so we can show the intro banner
        return GUIDE_STEPS[0]
    if step >= GUIDE_COMPLETE_STEP:
        return None
    idx = step - 1
    if 0 <= idx < len(GUIDE_STEPS):
        return GUIDE_STEPS[idx]
    return None


def get_guide_context(user: User) -> dict[str, Any]:
    """Build full context dict for the guide panel template tag."""
    if not user.is_authenticated:
        return {"guide_active": False}

    step = getattr(user, "guide_step", 0)
    if step >= GUIDE_COMPLETE_STEP:
        return {"guide_active": False}

    current = get_current_step(user)
    earned_so_far = max(0, (step - 1)) * STEP_RYO if step > 0 else 0

    return {
        "guide_active": True,
        "guide_step": step,
        "guide_started": step > 0,
        "guide_current": current,
        "guide_steps": GUIDE_STEPS,
        "guide_total_steps": len(GUIDE_STEPS),
        "guide_earned": earned_so_far,
        "guide_total_ryo": TOTAL_RYO,
        "guide_step_ryo": STEP_RYO,
        "guide_completion_bonus": COMPLETION_BONUS,
        "guide_progress_pct": round((max(0, step - 1) / len(GUIDE_STEPS)) * 100),
    }


@transaction.atomic
def advance_guide(user: User, to_step: int) -> int:
    """
    Advance the user's guide to `to_step` if it's higher than current.
    Awards 10,000 Ryo for each newly completed step.
    Returns ryo awarded this call (0 if already past this step).
    """
    user = User.objects.select_for_update().get(pk=user.pk)
    current = user.guide_step

    # Only advance forward, never back
    if to_step <= current:
        return 0

    # Ryo awarded for each step completed (moving past it, not entering it).
    # Steps between old position and new position, excluding step 0 (not started).
    completed_steps = to_step - 1 - (current - 1 if current > 0 else 0)
    ryo_awarded = max(0, completed_steps) * STEP_RYO

    if ryo_awarded:
        User.objects.filter(pk=user.pk).update(
            guide_step=to_step,
            ryo=F("ryo") + ryo_awarded,
        )
        logger.info(
            "Guide advance: user=%s step=%d ryo_awarded=%d",
            user, to_step, ryo_awarded,
        )
        return ryo_awarded

    User.objects.filter(pk=user.pk).update(guide_step=to_step)
    return 0


@transaction.atomic
def complete_guide(user: User) -> int:
    """
    Mark guide as fully complete and award the 130,000 completion bonus.
    Returns bonus ryo awarded (0 if already complete).
    """
    user = User.objects.select_for_update().get(pk=user.pk)
    if user.guide_step >= GUIDE_COMPLETE_STEP:
        return 0

    User.objects.filter(pk=user.pk).update(
        guide_step=GUIDE_COMPLETE_STEP,
        ryo=F("ryo") + COMPLETION_BONUS,
    )
    logger.info("Guide complete: user=%s bonus_ryo=%d", user, COMPLETION_BONUS)
    return COMPLETION_BONUS


# Map each step number to the URL names that count as "visiting" that step.
# When the user GETs any of these URLs, the guide auto-advances past that step.
_STEP_URL_TRIGGERS: dict[int, list[str]] = {
    1: ["users:daily_claim"],
    2: ["stickers:buy_pack"],
    3: ["stickers:my_packs", "stickers:pack_open"],
    4: ["stickers:album"],
    5: ["game:silhouette_hub"],
    6: ["game:loteria_game"],
    7: ["quests:quest_list"],
}

# Reverse map: url_name → step it unlocks
_URL_TO_STEP: dict[str, int] = {
    url: step
    for step, urls in _STEP_URL_TRIGGERS.items()
    for url in urls
}


def maybe_advance_from_url(user: User, url_name: str) -> int:
    """
    Called from view GET handlers. If `url_name` matches the current guide step,
    advance to the next step and return ryo awarded (0 if not applicable).
    """
    if not user.is_authenticated:
        return 0
    step = getattr(user, "guide_step", 0)
    if step == 0 or step >= GUIDE_COMPLETE_STEP:
        return 0

    expected_step = _URL_TO_STEP.get(url_name)
    if expected_step is None or expected_step != step:
        return 0

    next_step = step + 1
    ryo = advance_guide(user, next_step)

    # If that was the last step, award the completion bonus directly.
    # complete_guide() would bail because advance_guide already set guide_step=8.
    if next_step > len(GUIDE_STEPS):
        User.objects.filter(pk=user.pk).update(ryo=F("ryo") + COMPLETION_BONUS)
        ryo += COMPLETION_BONUS
        logger.info("Guide complete: user=%s bonus_ryo=%d", user, COMPLETION_BONUS)

    return ryo


@transaction.atomic
def dismiss_guide(user: User) -> None:
    """Permanently dismiss the guide without awarding remaining rewards."""
    User.objects.filter(pk=user.pk).update(guide_step=GUIDE_COMPLETE_STEP)
    logger.info("Guide dismissed: user=%s", user)
