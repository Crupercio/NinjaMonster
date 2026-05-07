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
def advance_guide(user: User, to_step: int) -> None:
    """
    Advance guide_step to `to_step` if higher than current. No ryo awarded here —
    ryo is claimed manually via claim_guide_step() on the profile page.
    """
    updated = User.objects.filter(pk=user.pk, guide_step__lt=to_step).update(guide_step=to_step)
    if updated:
        user.guide_step = to_step  # update in-memory so context processor sees new value
        logger.info("Guide advance: user=%s step=%d", user, to_step)


@transaction.atomic
def claim_guide_step(user: User) -> dict[str, int]:
    """
    Claim ryo for the next unclaimed guide step. Called from profile page.
    Returns {"ryo": N, "bonus": N, "claimed_step": N, "all_done": bool}.
    """
    user_db = User.objects.select_for_update().get(pk=user.pk)
    visited = user_db.guide_step
    claimed = user_db.guide_claimed_step

    if claimed >= visited or visited == 0:
        return {"ryo": 0, "bonus": 0, "claimed_step": claimed, "all_done": False}

    # Claim the next unclaimed step
    next_claimed = claimed + 1
    ryo = STEP_RYO

    bonus = 0
    all_done = False

    # If claiming step 7 AND all pages visited, also grant completion bonus
    if next_claimed == len(GUIDE_STEPS) and visited >= GUIDE_COMPLETE_STEP:
        bonus = COMPLETION_BONUS
        all_done = True

    User.objects.filter(pk=user.pk).update(
        guide_claimed_step=next_claimed,
        ryo=F("ryo") + ryo + bonus,
    )
    logger.info(
        "Guide claim: user=%s claimed_step=%d ryo=%d bonus=%d",
        user, next_claimed, ryo, bonus,
    )
    return {"ryo": ryo, "bonus": bonus, "claimed_step": next_claimed, "all_done": all_done}


@transaction.atomic
def dismiss_guide(user: User) -> None:
    """Permanently dismiss the guide without awarding remaining rewards."""
    User.objects.filter(pk=user.pk).update(guide_step=GUIDE_COMPLETE_STEP)
    user.guide_step = GUIDE_COMPLETE_STEP
    logger.info("Guide dismissed: user=%s", user)


# Map each step number to the URL names that count as "visiting" that step.
_STEP_URL_TRIGGERS: dict[int, list[str]] = {
    1: ["users:daily_claim"],
    2: ["stickers:buy_pack"],
    3: ["stickers:my_packs", "stickers:pack_open"],
    4: ["stickers:album"],
    5: ["game:silhouette_hub"],
    6: ["game:loteria_game"],
    7: ["quests:quest_list"],
}

_URL_TO_STEP: dict[str, int] = {
    url: step
    for step, urls in _STEP_URL_TRIGGERS.items()
    for url in urls
}


def maybe_advance_from_url(user: User, url_name: str) -> None:
    """
    Called from view GET/POST handlers. Marks the page as visited and advances
    guide_step. No ryo is awarded — user claims it manually on the profile page.
    """
    if not user.is_authenticated:
        return
    step = getattr(user, "guide_step", 0)
    if step == 0 or step >= GUIDE_COMPLETE_STEP:
        return

    expected_step = _URL_TO_STEP.get(url_name)
    if expected_step is None or expected_step != step:
        return

    next_step = step + 1
    advance_guide(user, next_step)


def get_guide_profile_context(user: User) -> dict:
    """
    Build the profile-page tutorial rewards section context.
    Shows each step with visited/claimed state and a claim button.
    """
    if not user.is_authenticated:
        return {"guide_profile_active": False}

    visited = getattr(user, "guide_step", 0)
    claimed = getattr(user, "guide_claimed_step", 0)

    if visited == 0:
        return {"guide_profile_active": False}

    steps_display = []
    for s in GUIDE_STEPS:
        n = s["step"]
        is_visited = visited >= n + 1 or visited >= GUIDE_COMPLETE_STEP
        is_claimed = claimed >= n
        steps_display.append({
            **s,
            "visited": is_visited,
            "claimed": is_claimed,
            "claimable": is_visited and not is_claimed and claimed == n - 1,
        })

    # Bonus: claimable when all 7 steps claimed and all pages visited
    bonus_visited = visited >= GUIDE_COMPLETE_STEP
    bonus_claimed = claimed >= GUIDE_COMPLETE_STEP
    bonus_claimable = bonus_visited and not bonus_claimed and claimed == len(GUIDE_STEPS)

    total_earned = claimed * STEP_RYO + (COMPLETION_BONUS if bonus_claimed else 0)

    return {
        "guide_profile_active": True,
        "guide_profile_steps": steps_display,
        "guide_profile_bonus_visited": bonus_visited,
        "guide_profile_bonus_claimed": bonus_claimed,
        "guide_profile_bonus_claimable": bonus_claimable,
        "guide_profile_total_earned": total_earned,
        "guide_profile_total_ryo": TOTAL_RYO,
        "guide_profile_visited": visited,
        "guide_profile_claimed": claimed,
    }


