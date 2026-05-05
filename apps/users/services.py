"""Currency and trainer level services."""
import logging
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.db.models import F

logger = logging.getLogger(__name__)

User = get_user_model()

# ── Reward constants — tune these in one place ──────────────────────────────
DAILY_REWARD_RYO: int = 1000
BATTLE_WIN_RYO: int = 1000
BATTLE_LOSS_RYO: int = 350
BOND_BONUS_UNLOCK_LEVEL: int = 10
BOND_BONUS_LOCKED_MULTIPLIER: float = 0.25
SELL_VALUE_TIERS: tuple[tuple[int, int], ...] = (
    (50, 1500),
    (90, 2500),
    (99, 3000),
    (100, 5000),
)
# ────────────────────────────────────────────────────────────────────────────


def base_sell_value_for_level(level: int) -> int:
    """Return the full sell value for a Pokemon once its Bond Bonus is unlocked."""
    for max_level, value in SELL_VALUE_TIERS:
        if level <= max_level:
            return value
    return SELL_VALUE_TIERS[-1][1]


def sell_value_for_level(level: int) -> int:
    """Return the current Ryo sell value, including Bond Bonus protection before Lv10."""
    full_value = base_sell_value_for_level(level)
    if level >= BOND_BONUS_UNLOCK_LEVEL:
        return full_value
    return max(1, int(full_value * BOND_BONUS_LOCKED_MULTIPLIER))


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
def purchase_training_slot_upgrade(user: "User") -> dict[str, int]:  # type: ignore[name-defined]
    """Buy the next training slot upgrade when the trainer level gate is met."""
    user.refresh_from_db(fields=["ryo", "trainer_level", "training_slot_upgrade_level"])
    next_upgrade = user.next_training_slot_upgrade
    if next_upgrade is None:
        raise ValueError("All training slot upgrades have already been purchased.")

    min_level = int(next_upgrade["min_level"])
    if user.trainer_level < min_level:
        raise ValueError(
            f"Reach Amigo Level {min_level} to unlock the next training slot upgrade."
        )

    cost = int(next_upgrade["cost"])
    deduct_ryo(user, cost)
    user.training_slot_upgrade_level += 1
    user.save(update_fields=["training_slot_upgrade_level"])
    user.refresh_from_db(fields=["training_slot_upgrade_level", "ryo", "trainer_level"])

    logger.info(
        "%s purchased training slot upgrade #%d for %d Ryo (max slots: %d).",
        user,
        user.training_slot_upgrade_level,
        cost,
        user.max_training_slots,
    )
    return {"cost": cost, "max_training_slots": user.max_training_slots}


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


def _blank_arcade_daily_progress(progress_date: date | None = None) -> dict[str, object]:
    """Return a normalized daily arcade progress payload for one calendar day."""
    current_date = progress_date or date.today()
    return {
        "date": current_date.isoformat(),
        "silhouette_runs": 0,
        "silhouette_best_floor": 0,
        "silhouette_cashout_3plus": 0,
        "memory_clears": 0,
        "memory_best_seconds": 0,
        "memory_master_clears": 0,
        "loteria_rounds": 0,
        "loteria_best_marked": 0,
        "loteria_buena_rounds": 0,
        "loteria_room_ids": [],
        "challenge_claimed": False,
    }


def get_arcade_daily_progress(user: "User") -> dict[str, object]:
    """Return today's arcade progress, resetting stale data automatically."""
    today = date.today()
    progress = user.arcade_daily_progress or {}
    if progress.get("date") != today.isoformat():
        progress = _blank_arcade_daily_progress(today)
        User.objects.filter(pk=user.pk).update(arcade_daily_progress=progress)
        user.arcade_daily_progress = progress
        return progress

    normalized = _blank_arcade_daily_progress(today)
    normalized.update(progress)
    normalized["date"] = today.isoformat()
    normalized["loteria_room_ids"] = [int(room_id) for room_id in normalized.get("loteria_room_ids", [])]
    for key in (
        "silhouette_runs",
        "silhouette_best_floor",
        "silhouette_cashout_3plus",
        "memory_clears",
        "memory_best_seconds",
        "memory_master_clears",
        "loteria_rounds",
        "loteria_best_marked",
        "loteria_buena_rounds",
    ):
        normalized[key] = int(normalized.get(key, 0) or 0)
    if normalized != progress:
        User.objects.filter(pk=user.pk).update(arcade_daily_progress=normalized)
        user.arcade_daily_progress = normalized
    return normalized


@transaction.atomic
def record_arcade_daily_progress(
    user: "User",
    *,
    silhouette_run: bool = False,
    silhouette_floor: int | None = None,
    silhouette_cashout_3plus: bool = False,
    memory_clear: bool = False,
    memory_elapsed_seconds: int | None = None,
    memory_master_clear: bool = False,
    loteria_room_id: int | None = None,
    loteria_marked_count: int | None = None,
    loteria_buena: bool = False,
) -> dict[str, object]:
    """Update the user's Fun Hub daily challenge progress."""
    user.refresh_from_db(fields=["arcade_daily_progress"])
    progress = get_arcade_daily_progress(user)

    if silhouette_run:
        progress["silhouette_runs"] = int(progress["silhouette_runs"]) + 1
    if silhouette_floor is not None:
        progress["silhouette_best_floor"] = max(int(progress["silhouette_best_floor"]), int(silhouette_floor))
    if silhouette_cashout_3plus:
        progress["silhouette_cashout_3plus"] = max(int(progress["silhouette_cashout_3plus"]), 1)

    if memory_clear:
        progress["memory_clears"] = int(progress["memory_clears"]) + 1
    if memory_elapsed_seconds is not None and memory_elapsed_seconds > 0:
        best_seconds = int(progress["memory_best_seconds"])
        progress["memory_best_seconds"] = memory_elapsed_seconds if best_seconds == 0 else min(best_seconds, memory_elapsed_seconds)
    if memory_master_clear:
        progress["memory_master_clears"] = int(progress["memory_master_clears"]) + 1

    if loteria_room_id is not None:
        seen_room_ids = {int(room_id) for room_id in progress.get("loteria_room_ids", [])}
        if int(loteria_room_id) not in seen_room_ids:
            seen_room_ids.add(int(loteria_room_id))
            progress["loteria_room_ids"] = sorted(seen_room_ids)
            progress["loteria_rounds"] = int(progress["loteria_rounds"]) + 1
        if loteria_marked_count is not None:
            progress["loteria_best_marked"] = max(int(progress["loteria_best_marked"]), int(loteria_marked_count))
        if loteria_buena:
            progress["loteria_buena_rounds"] = max(int(progress["loteria_buena_rounds"]), 1)

    User.objects.filter(pk=user.pk).update(arcade_daily_progress=progress)
    user.arcade_daily_progress = progress
    return progress


@transaction.atomic
def claim_arcade_daily_challenge(user: "User", reward_ryo: int) -> dict[str, object]:
    """
    Award the arcade daily challenge Ryo bonus if all tasks are complete and
    the reward has not already been claimed today.

    Raises ValueError if already claimed or tasks not complete.
    Returns dict with new ryo balance.
    """
    user.refresh_from_db(fields=["arcade_daily_progress", "ryo"])
    progress = get_arcade_daily_progress(user)

    if progress.get("challenge_claimed"):
        raise ValueError("Already claimed today.")

    progress["challenge_claimed"] = True
    User.objects.filter(pk=user.pk).update(
        arcade_daily_progress=progress,
        ryo=models.F("ryo") + reward_ryo,
    )
    user.refresh_from_db(fields=["ryo"])
    user.arcade_daily_progress = progress
    logger.info("User %s claimed arcade daily challenge: +%s Ryo", user.pk, reward_ryo)
    return {"ryo": user.ryo}


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
