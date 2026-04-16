"""
Business logic for Pokemon leveling, EXP, and training.

All functions that change database state accept an OwnedPokemon instance
and call .save() themselves — callers do not need to save manually.

EXP rules (as designed):
  - Battle EXP:          Lv 1–50 = 5 XP | Lv 51–100 = 10 XP (flat per bracket)
  - Win:                 full battle EXP
  - Lose:                half battle EXP (rounded down)
  - Training tick:       3× battle EXP for that Pokemon's level bracket
  - Training ticks:      one tick per 2 minutes of training duration
  - Duration bonuses:    30 min = ×1.0 | 60 min = ×1.10 | 240 min = ×1.50
  - Level-up threshold:  three-phase exponential curve (see OwnedPokemon.exp_to_next_level)
  - Training Pokemon:    cannot receive battle EXP; must stop/cancel training first
  - Level-up Ryo:        min(level × 50, 5000) Ryo awarded per level-up

Level-up total time estimates (240-min sessions):
  Lv 1–20:   ~0.8 sessions  (3.4h) — hooks the player fast
  Lv 21–85:  ~10.5 sessions (42h)  — steady grind
  Lv 86–100: ~12.9 sessions (52h)  — 60% of total XP, genuinely hard
  Lv 1–100:  ~24 sessions   (97h)  — roughly 25 days at 1 session/day

Valid training durations (minutes): 30, 60, 240
"""
import logging
import random
from datetime import timedelta
from typing import TYPE_CHECKING

from django.utils import timezone

from .models import OwnedPokemon

if TYPE_CHECKING:
    from .models import Pokemon

logger = logging.getLogger(__name__)

MAX_LEVEL = 100
VALID_DURATIONS = (30, 60, 240)
_DURATION_BONUS = {30: 1.0, 60: 1.10, 240: 1.50}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def award_battle_exp(owned: OwnedPokemon, won: bool) -> int:
    """
    Award EXP after a battle and handle any level-ups.

    Args:
        owned: The OwnedPokemon that participated in the battle.
        won:   True if the Pokemon's team won; False if they lost.

    Returns:
        The amount of EXP actually awarded.

    Raises:
        ValueError: If the Pokemon is currently in training (cannot battle).
    """
    if owned.is_training:
        raise ValueError(
            f"{owned.species.name} is in training and cannot battle. "
            "Call stop_training() first."
        )

    base_exp = owned.battle_exp_gain          # 10 / 20 / 30 … from model property
    earned = base_exp if won else base_exp // 2

    _apply_exp(owned, earned)

    logger.info(
        "%s earned %d EXP from battle (%s). Now Lv.%d, %d/%d EXP.",
        owned.species.name,
        earned,
        "win" if won else "loss",
        owned.level,
        owned.experience,
        owned.exp_to_next_level,
    )
    return earned


def award_training_exp(owned: OwnedPokemon) -> int:
    """
    Award a single training tick's worth of EXP (3× the normal battle bracket).

    The Pokemon must already have is_training=True.
    This is a low-level helper primarily used in tests. For the full timed
    training flow, use start_training() + claim_training() instead.

    Args:
        owned: The OwnedPokemon currently in training.

    Returns:
        The amount of EXP awarded.

    Raises:
        ValueError: If the Pokemon is not in training.
    """
    if not owned.is_training:
        raise ValueError(
            f"{owned.species.name} is not in training. "
            "Call start_training() first."
        )

    earned = owned.battle_exp_gain * 3        # 3× the bracket amount

    _apply_exp(owned, earned)

    logger.info(
        "%s earned %d EXP from a training tick. Now Lv.%d, %d/%d EXP.",
        owned.species.name,
        earned,
        owned.level,
        owned.experience,
        owned.exp_to_next_level,
    )
    return earned


def start_training(owned: OwnedPokemon, duration_minutes: int = 30) -> None:
    """
    Put a Pokemon into timed training mode.

    While training, the Pokemon cannot join battles. Training automatically
    finishes after `duration_minutes` have elapsed; call claim_training() to
    collect the XP reward.

    Args:
        owned:            The OwnedPokemon to train.
        duration_minutes: Training length — must be 30, 60, or 240.

    Raises:
        ValueError: If duration_minutes is not a valid option.
    """
    if duration_minutes not in VALID_DURATIONS:
        raise ValueError(
            f"Invalid duration {duration_minutes}. Choose from {VALID_DURATIONS}."
        )

    if owned.is_training:
        return  # already training — nothing to do

    now = timezone.now()
    owned.is_training = True
    owned.training_started_at = now
    owned.training_ends_at = now + timedelta(minutes=duration_minutes)
    owned.training_duration_minutes = duration_minutes
    owned.save(
        update_fields=[
            "is_training",
            "training_started_at",
            "training_ends_at",
            "training_duration_minutes",
        ]
    )
    logger.info(
        "%s started %d-minute training, finishes at %s.",
        owned.species.name,
        duration_minutes,
        owned.training_ends_at.strftime("%H:%M"),
    )


def stop_training(owned: OwnedPokemon) -> None:
    """
    Cancel a Pokemon's training without awarding any XP.

    Use this when the player wants to abort training early. To collect the
    completed training reward instead, call claim_training().

    Args:
        owned: The OwnedPokemon to remove from training.
    """
    if not owned.is_training:
        return  # not training — nothing to do

    owned.is_training = False
    owned.training_started_at = None
    owned.training_ends_at = None
    owned.training_duration_minutes = None
    owned.save(
        update_fields=[
            "is_training",
            "training_started_at",
            "training_ends_at",
            "training_duration_minutes",
        ]
    )
    logger.info("%s training cancelled (no XP awarded).", owned.species.name)


def claim_training(owned: OwnedPokemon) -> int:
    """
    Claim the XP reward for a completed training session.

    Calculates total XP as:
      ticks = duration_minutes // 2
      xp_per_tick = battle_exp_gain × 3
      total = ticks × xp_per_tick × duration_bonus

    Duration bonuses: 30 min → ×1.0 | 60 min → ×1.10 | 240 min → ×1.50

    Clears all training fields and removes the lock after awarding XP.

    Args:
        owned: The OwnedPokemon whose training has finished.

    Returns:
        Total EXP awarded.

    Raises:
        ValueError: If the Pokemon is not in training, or training isn't done yet.
    """
    if not owned.is_training:
        raise ValueError(f"{owned.species.name} is not currently in training.")

    if owned.training_ends_at is None or timezone.now() < owned.training_ends_at:
        raise ValueError(
            f"{owned.species.name}'s training is not finished yet."
        )

    duration = owned.training_duration_minutes or 30
    ticks = duration // 2                          # one tick per 2 minutes
    xp_per_tick = owned.battle_exp_gain * 3        # 3× bracket XP per tick
    bonus = _DURATION_BONUS.get(duration, 1.0)
    total_xp = int(ticks * xp_per_tick * bonus)

    # Award XP (may trigger level-ups)
    _apply_exp(owned, total_xp)

    # Clear training lock
    owned.is_training = False
    owned.training_started_at = None
    owned.training_ends_at = None
    owned.training_duration_minutes = None
    owned.save(
        update_fields=[
            "is_training",
            "training_started_at",
            "training_ends_at",
            "training_duration_minutes",
        ]
    )

    logger.info(
        "%s completed %d-minute training (×%.2f bonus), earned %d XP. Now Lv.%d.",
        owned.species.name,
        duration,
        bonus,
        total_xp,
        owned.level,
    )
    return total_xp


def create_owned_pokemon(
    owner: object,
    species: "Pokemon",
    level: int = 1,
) -> OwnedPokemon:
    """
    Canonical factory for all Pokémon acquisition paths.

    Creates an OwnedPokemon and assigns a full random moveset via
    assign_random_moveset().  Use this for signup starters, wild catches,
    and any other flow that grants a user a new Pokémon — never construct
    OwnedPokemon inline and call assign_random_moveset separately.

    Args:
        owner:   The User who will own this Pokémon.
        species: The Pokémon species (Pokemon model instance).
        level:   Starting level (default 1).

    Returns:
        The newly created and move-equipped OwnedPokemon instance.
    """
    owned = OwnedPokemon.objects.create(
        owner=owner,
        species=species,
        level=level,
        experience=0,
    )
    assign_random_moveset(owned)
    return owned


def assign_random_moveset(owned: OwnedPokemon) -> None:
    """
    Populate empty move slots on an OwnedPokemon from its species' SpeciesMovePool.

    Only fills slots that are currently None — existing moves are never overwritten.
    Logs an ERROR for any slot whose pool is missing, so gaps are never silent.

    Args:
        owned: The OwnedPokemon instance to equip. Must already be saved (has a PK).
    """
    from .models import MoveSlotType, SpeciesMovePool  # local import avoids circular

    slot_field_map: dict[str, str] = {
        MoveSlotType.STANDARD: "move_standard",
        MoveSlotType.CHASE: "move_chase",
        MoveSlotType.MYSTERY: "move_special",
        MoveSlotType.PASSIVE_1: "move_support",
        MoveSlotType.PASSIVE_2: "move_passive",
    }

    # Only target slots that are actually empty.
    empty_slots = {
        slot_type: field_name
        for slot_type, field_name in slot_field_map.items()
        if getattr(owned, f"{field_name}_id") is None
    }

    if not empty_slots:
        logger.info(
            "%s (pk=%s) already has a complete moveset — skipping.",
            owned.species.name,
            owned.pk,
        )
        return

    pool_entries = list(
        SpeciesMovePool.objects.filter(species=owned.species).select_related("move")
    )

    if not pool_entries:
        logger.error(
            "No SpeciesMovePool entries for %s (pk=%s) — %d slot(s) left empty: %s.",
            owned.species.name,
            owned.pk,
            len(empty_slots),
            ", ".join(empty_slots.values()),
        )
        return

    grouped: dict[str, list] = {}
    for entry in pool_entries:
        grouped.setdefault(entry.slot_type, []).append(entry.move)

    update_fields: list[str] = []
    missing_slots: list[str] = []

    for slot_type, field_name in empty_slots.items():
        candidates = grouped.get(slot_type, [])
        if candidates:
            setattr(owned, field_name, random.choice(candidates))
            update_fields.append(field_name)
        else:
            missing_slots.append(f"{field_name} ({slot_type})")

    if missing_slots:
        logger.error(
            "%s (pk=%s) has no pool entries for slot(s): %s — those slots remain empty.",
            owned.species.name,
            owned.pk,
            ", ".join(missing_slots),
        )

    if update_fields:
        owned.save(update_fields=update_fields)
        logger.info(
            "Assigned moveset to %s (pk=%s): %s.",
            owned.species.name,
            owned.pk,
            ", ".join(f"{f}={getattr(owned, f + '_id')}" for f in update_fields),
        )


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _apply_exp(owned: OwnedPokemon, earned: int) -> int:
    """
    Add `earned` EXP to the Pokemon, triggering level-ups as needed.

    On each level-up, awards Ryo to the owner (min(level × 50, 5000)).
    Saves only changed fields to avoid overwriting concurrent updates.

    Returns:
        Total Ryo awarded from level-ups (0 if no level-up occurred).
    """
    from apps.users.services import award_ryo

    owned.experience += earned
    total_ryo = 0

    while owned.level < MAX_LEVEL and owned.experience >= owned.exp_to_next_level:
        owned.experience -= owned.exp_to_next_level
        owned.level += 1
        ryo = owned.level_up_ryo
        total_ryo += ryo
        logger.info(
            "%s leveled up to Lv.%d! (+%d Ryo)",
            owned.species.name, owned.level, ryo,
        )

    owned.save(update_fields=["experience", "level"])

    if total_ryo:
        award_ryo(owned.owner, total_ryo)
        logger.info(
            "%s owner earned %d Ryo total from level-ups (now Lv.%d).",
            owned.species.name, total_ryo, owned.level,
        )

    return total_ryo
