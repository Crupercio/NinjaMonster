"""Currency services for the Ryo wallet system."""
import logging
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F

logger = logging.getLogger(__name__)

User = get_user_model()

# ── Reward constants — tune these in one place ──────────────────────────────
DAILY_REWARD_RYO: int = 1000
BATTLE_WIN_RYO: int = 200
BATTLE_LOSS_RYO: int = 50
SELL_RYO_PER_LEVEL: int = 50   # sell value = max(100, level * SELL_RYO_PER_LEVEL)
SELL_RYO_MINIMUM: int = 100
# ────────────────────────────────────────────────────────────────────────────


def sell_value_for_level(level: int) -> int:
    """Return the Ryo sell value for a Pokemon of the given level."""
    return max(SELL_RYO_MINIMUM, level * SELL_RYO_PER_LEVEL)


@transaction.atomic
def award_ryo(user: "User", amount: int) -> None:  # type: ignore[name-defined]
    """Add *amount* Ryo to *user*'s wallet atomically."""
    if amount <= 0:
        raise ValueError(f"award_ryo: amount must be positive, got {amount!r}")
    User.objects.filter(pk=user.pk).update(ryo=F("ryo") + amount)
    user.refresh_from_db(fields=["ryo"])
    logger.debug("Awarded %d Ryo to %s (total: %d)", amount, user, user.ryo)


@transaction.atomic
def deduct_ryo(user: "User", amount: int) -> None:  # type: ignore[name-defined]
    """Subtract *amount* Ryo from *user*'s wallet.

    Raises ValueError if the user cannot afford it.
    """
    if amount <= 0:
        raise ValueError(f"deduct_ryo: amount must be positive, got {amount!r}")
    user.refresh_from_db(fields=["ryo"])
    if user.ryo < amount:
        raise ValueError(
            f"Insufficient Ryo: need {amount}, have {user.ryo}"
        )
    User.objects.filter(pk=user.pk).update(ryo=F("ryo") - amount)
    user.refresh_from_db(fields=["ryo"])
    logger.debug("Deducted %d Ryo from %s (total: %d)", amount, user, user.ryo)


def can_claim_daily(user: "User") -> bool:  # type: ignore[name-defined]
    """Return True if the user has not yet claimed their daily reward today."""
    return user.last_daily_claim != date.today()


@transaction.atomic
def claim_daily_reward(user: "User") -> int:  # type: ignore[name-defined]
    """Award DAILY_REWARD_RYO to *user* if they haven't claimed today.

    Returns the amount awarded.
    Raises ValueError if already claimed today.
    """
    user.refresh_from_db(fields=["last_daily_claim", "ryo", "daily_claim_streak", "max_daily_claim_streak"])
    if not can_claim_daily(user):
        raise ValueError("Daily reward already claimed today.")

    # Streak tracking: consecutive = claimed yesterday, else reset to 1
    yesterday = date.today() - timedelta(days=1)
    new_streak = (user.daily_claim_streak + 1) if user.last_daily_claim == yesterday else 1
    new_max = max(user.max_daily_claim_streak, new_streak)

    User.objects.filter(pk=user.pk).update(
        ryo=F("ryo") + DAILY_REWARD_RYO,
        last_daily_claim=date.today(),
        daily_claim_streak=new_streak,
        max_daily_claim_streak=new_max,
    )
    user.refresh_from_db(fields=["ryo", "last_daily_claim", "daily_claim_streak", "max_daily_claim_streak"])
    logger.info("Daily reward claimed by %s (+%d Ryo, streak=%d)", user, DAILY_REWARD_RYO, new_streak)
    return DAILY_REWARD_RYO
