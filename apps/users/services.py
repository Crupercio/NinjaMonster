"""Currency and trainer level services."""
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


TRAINER_DAILY_XP_CAP: int = 500  # max trainer XP earnable per calendar day

# ── Candy shop prices (Ryo) ──────────────────────────────────────────────────
CANDY_COSTS: dict[str, int] = {
    "trail_mix":    80,
    "sweet_berry":  200,
    "golden_apple": 500,
}

# How much each candy boosts the bond rate (additive percentage points)
CANDY_BOOST: dict[str, int] = {
    "trail_mix":    10,
    "sweet_berry":  25,
    "golden_apple": 50,
}

# Max bond rate regardless of candy (never 100%)
BOND_RATE_CAP: int = 90

# Daily purchase limit per candy type
CANDY_DAILY_LIMIT: int = 3


@transaction.atomic
def award_trainer_xp(user: "User", amount: int, source: str = "") -> int:  # type: ignore[name-defined]
    """
    Award trainer XP, respecting the daily cap and triggering level-ups.

    Args:
        user:   The trainer to award XP to.
        amount: Raw XP to award (will be capped by remaining daily allowance).
        source: Human-readable source label for logging (e.g. 'quest', 'sticker').

    Returns:
        Actual XP awarded after applying daily cap (may be 0 if cap reached).
    """
    today = date.today()
    user.refresh_from_db(fields=["trainer_level", "trainer_xp", "trainer_xp_today", "trainer_xp_date"])

    # Reset daily counter on new day
    if user.trainer_xp_date != today:
        user.trainer_xp_today = 0
        user.trainer_xp_date = today

    remaining_today = max(0, TRAINER_DAILY_XP_CAP - user.trainer_xp_today)
    actual = min(amount, remaining_today)

    if actual <= 0:
        logger.debug("Trainer XP cap reached for %s today (source: %s).", user, source)
        return 0

    user.trainer_xp += actual
    user.trainer_xp_today += actual

    # Process level-ups
    leveled_up = False
    while user.trainer_xp >= user.trainer_xp_to_next_level:
        user.trainer_xp -= user.trainer_xp_to_next_level
        user.trainer_level += 1
        leveled_up = True
        logger.info("Trainer %s reached level %d!", user, user.trainer_level)

    User.objects.filter(pk=user.pk).update(
        trainer_level=user.trainer_level,
        trainer_xp=user.trainer_xp,
        trainer_xp_today=user.trainer_xp_today,
        trainer_xp_date=user.trainer_xp_date,
    )

    logger.debug(
        "Awarded %d trainer XP to %s (source: %s, today total: %d/%d)%s",
        actual, user, source or "unknown",
        user.trainer_xp_today, TRAINER_DAILY_XP_CAP,
        " — LEVELED UP!" if leveled_up else "",
    )
    return actual


def get_candy_inventory(user: "User") -> dict[str, dict]:  # type: ignore[name-defined]
    """Return a structured candy inventory for display."""
    return {
        "trail_mix": {
            "count": user.candy_trail_mix,
            "boost": CANDY_BOOST["trail_mix"],
            "cost": CANDY_COSTS["trail_mix"],
            "label": "Trail Mix",
            "description": "+10% bond rate",
        },
        "sweet_berry": {
            "count": user.candy_sweet_berry,
            "boost": CANDY_BOOST["sweet_berry"],
            "cost": CANDY_COSTS["sweet_berry"],
            "label": "Sweet Berry",
            "description": "+25% bond rate",
        },
        "golden_apple": {
            "count": user.candy_golden_apple,
            "boost": CANDY_BOOST["golden_apple"],
            "cost": CANDY_COSTS["golden_apple"],
            "label": "Golden Apple",
            "description": "+50% bond rate",
        },
    }


@transaction.atomic
def buy_candy(user: "User", candy_type: str) -> None:  # type: ignore[name-defined]
    """
    Purchase one candy of the given type, deducting Ryo.

    Raises ValueError if type is invalid, user can't afford it.
    No daily purchase limit enforced here — UI handles that messaging.
    """
    if candy_type not in CANDY_COSTS:
        raise ValueError(f"Unknown candy type: {candy_type!r}")
    cost = CANDY_COSTS[candy_type]
    deduct_ryo(user, cost)  # raises if insufficient
    field = f"candy_{candy_type}"
    User.objects.filter(pk=user.pk).update(**{field: F(field) + 1})
    user.refresh_from_db(fields=[field])
    logger.info("%s bought 1x %s for %d Ryo.", user, candy_type, cost)


@transaction.atomic
def award_candy(user: "User", candy_type: str, qty: int = 1) -> None:  # type: ignore[name-defined]
    """Grant candy to a user (quest reward, expedition drop, etc.)."""
    if candy_type not in CANDY_COSTS:
        raise ValueError(f"Unknown candy type: {candy_type!r}")
    field = f"candy_{candy_type}"
    User.objects.filter(pk=user.pk).update(**{field: F(field) + qty})
    user.refresh_from_db(fields=[field])
    logger.info("Awarded %dx %s to %s.", qty, candy_type, user)


@transaction.atomic
def use_candy(user: "User", candy_type: str) -> int:
    """
    Consume one candy and return the bond boost amount.

    Raises ValueError if the user has none of this candy type.
    """
    if candy_type not in CANDY_COSTS:
        raise ValueError(f"Unknown candy type: {candy_type!r}")
    field = f"candy_{candy_type}"
    user.refresh_from_db(fields=[field])
    if getattr(user, field) < 1:
        raise ValueError(f"You have no {candy_type.replace('_', ' ').title()} left.")
    User.objects.filter(pk=user.pk).update(**{field: F(field) - 1})
    user.refresh_from_db(fields=[field])
    boost = CANDY_BOOST[candy_type]
    logger.debug("%s used 1x %s (+%d%% bond).", user, candy_type, boost)
    return boost


def can_claim_daily(user: "User") -> bool:  # type: ignore[name-defined]
    """Return True if the user has not yet claimed their daily reward today."""
    return user.last_daily_claim != date.today()


WEEKLY_LOGIN_STREAK = 7  # day on which a bundle pack is awarded


@transaction.atomic
def claim_daily_reward(user: "User") -> dict:  # type: ignore[name-defined]
    """Award DAILY_REWARD_RYO to *user* if they haven't claimed today.

    On every 7th consecutive day, also grants a Bundle Sticker Pack.

    Returns a dict: {"ryo": int, "bundle_pack": StickerPack | None}.
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

    # Weekly bonus: grant a Bundle Pack on every 7th consecutive day
    bundle_pack = None
    if new_streak % WEEKLY_LOGIN_STREAK == 0:
        from apps.stickers.models import PackType, StickerPack
        bundle_pack = StickerPack.objects.create(owner=user, pack_type=PackType.BUNDLE)
        logger.info("Weekly login bonus: bundle pack granted to %s (streak=%d)", user, new_streak)

    logger.info("Daily reward claimed by %s (+%d Ryo, streak=%d)", user, DAILY_REWARD_RYO, new_streak)
    return {"ryo": DAILY_REWARD_RYO, "bundle_pack": bundle_pack}
