"""
Status effect enumerations and configuration constants.

Three categories:
  PERSISTENT — survive switching, mutually exclusive with each other
  VOLATILE   — cleared on switch or battle end, can coexist
  NARUTO     — Naruto Online inspired effects, some volatile, some persistent
"""
from django.db import models


class StatusCategory(models.TextChoices):
    PERSISTENT = "persistent", "Persistent"
    VOLATILE = "volatile", "Volatile"
    NARUTO = "naruto", "Naruto Inspired"
    PHYSICAL = "physical", "Physical State"
    UTILITY = "utility", "Utility"
    ADVANCED = "advanced", "Advanced"


class StatusName(models.TextChoices):
    # ------------------------------------------------------------------
    # PERSISTENT effects (only one at a time; survive switch-out)
    # ------------------------------------------------------------------
    BURNED = "burned", "Burned"
    POISONED = "poisoned", "Poisoned"
    BADLY_POISONED = "badly_poisoned", "Badly Poisoned"
    PARALYZED = "paralyzed", "Paralyzed"
    FROZEN = "frozen", "Frozen"
    ASLEEP = "asleep", "Asleep"

    # ------------------------------------------------------------------
    # VOLATILE effects (cleared on switch; multiple can coexist)
    # ------------------------------------------------------------------
    CONFUSED = "confused", "Confused"
    INFATUATED = "infatuated", "Infatuated"
    FLINCHED = "flinched", "Flinched"
    BOUND = "bound", "Bound"
    SEEDED = "seeded", "Seeded"
    CURSED = "cursed", "Cursed"
    NIGHTMARE = "nightmare", "Nightmare"
    TAUNTED = "taunted", "Taunted"
    ENCORED = "encored", "Encored"
    TORMENTED = "tormented", "Tormented"
    HEAL_BLOCKED = "heal_blocked", "Heal Blocked"
    PERISH_SONG = "perish_song", "Perish Song"
    YAWNING = "yawning", "Yawning"

    # ------------------------------------------------------------------
    # NARUTO-INSPIRED effects (unique combo chain mechanics)
    # ------------------------------------------------------------------
    IGNITED = "ignited", "Ignited"           # DOT + healing disabled
    IMMOBILE = "immobile", "Immobile"         # Full turn loss, 1 round
    CHAOS = "chaos", "Chaos"                  # Attacks random ally instead of enemy
    BLINDED = "blinded", "Blinded"            # Cannot use standard attacks
    ACUPUNCTURED = "acupunctured", "Acupunctured"  # Cannot use special/mystery moves
    IMPRISONED = "imprisoned", "Imprisoned"   # Takes damage when using special moves
    TAGGED = "tagged", "Tagged"               # Defense/resistance -30%, special combos trigger
    ENFEEBLED = "enfeebled", "Enfeebled"      # Attack and Sp. Attack reduced
    WEAKENED = "weakened", "Weakened"         # All damage output reduced
    CORRODED = "corroded", "Corroded"         # Sp. Defense stripped, worsens each turn
    INTERRUPTED = "interrupted", "Interrupted"  # Current move cancelled, turn lost

    # ------------------------------------------------------------------
    # PHYSICAL states (mutually exclusive; track positional/launch state)
    # ------------------------------------------------------------------
    GROUNDED = "grounded", "Grounded"        # Default; no special state
    AIRBORNE = "airborne", "Airborne"        # Knocked up; enables aerial chases
    LAUNCHED = "launched", "Launched"        # Hit while airborne; extended juggle
    KNOCKBACK = "knockback", "Knockback"     # Pushed back; position changes

    # ------------------------------------------------------------------
    # UTILITY states (persistent buffs/protections)
    # ------------------------------------------------------------------
    SHIELDED = "shielded", "Shielded"        # Absorbs one hit
    HIDDEN = "hidden", "Hidden"              # Cannot be targeted
    IMMUNE = "immune", "Immune"              # Immune to status effects

    # ------------------------------------------------------------------
    # ADVANCED states (chain/state meta effects)
    # ------------------------------------------------------------------
    CHAIN_BREAKER = "chain_breaker", "Chain Breaker"  # Stops combo chain on hit
    STATE_LOCKED = "state_locked", "State Locked"      # Physical state cannot change
    CHARGING = "charging", "Charging"                  # 2-round charge; releases next round


# Persistent statuses are mutually exclusive — only one allowed at a time
PERSISTENT_STATUSES: frozenset[str] = frozenset(
    [
        StatusName.BURNED,
        StatusName.POISONED,
        StatusName.BADLY_POISONED,
        StatusName.PARALYZED,
        StatusName.FROZEN,
        StatusName.ASLEEP,
    ]
)

# Volatile statuses cleared when a Pokemon switches out
VOLATILE_STATUSES: frozenset[str] = frozenset(
    [
        StatusName.CONFUSED,
        StatusName.INFATUATED,
        StatusName.FLINCHED,
        StatusName.BOUND,
        StatusName.SEEDED,
        StatusName.CURSED,
        StatusName.NIGHTMARE,
        StatusName.TAUNTED,
        StatusName.ENCORED,
        StatusName.TORMENTED,
        StatusName.HEAL_BLOCKED,
        StatusName.PERISH_SONG,
        StatusName.YAWNING,
    ]
)

NARUTO_STATUSES: frozenset[str] = frozenset(
    [
        StatusName.IGNITED,
        StatusName.IMMOBILE,
        StatusName.CHAOS,
        StatusName.BLINDED,
        StatusName.ACUPUNCTURED,
        StatusName.IMPRISONED,
        StatusName.TAGGED,
        StatusName.ENFEEBLED,
        StatusName.WEAKENED,
        StatusName.CORRODED,
        StatusName.INTERRUPTED,
    ]
)

# Physical states are mutually exclusive — only one at a time.
# GROUNDED is the implicit default; not stored as an ActiveStatusEffect.
PHYSICAL_STATUSES: frozenset[str] = frozenset(
    [
        StatusName.AIRBORNE,
        StatusName.LAUNCHED,
        StatusName.KNOCKBACK,
    ]
)

UTILITY_STATUSES: frozenset[str] = frozenset(
    [
        StatusName.SHIELDED,
        StatusName.HIDDEN,
        StatusName.IMMUNE,
    ]
)

ADVANCED_STATUSES: frozenset[str] = frozenset(
    [
        StatusName.CHAIN_BREAKER,
        StatusName.STATE_LOCKED,
        StatusName.CHARGING,
    ]
)

# Default durations (in rounds). None = indefinite until cured.
DEFAULT_DURATIONS: dict[str, int | None] = {
    # Persistent — no timer
    StatusName.BURNED: None,
    StatusName.POISONED: None,
    StatusName.BADLY_POISONED: None,
    StatusName.PARALYZED: None,
    StatusName.FROZEN: None,
    StatusName.ASLEEP: None,  # 2–5 turns rolled at application time

    # Volatile
    StatusName.CONFUSED: None,    # 1–4 turns rolled at application
    StatusName.INFATUATED: None,
    StatusName.FLINCHED: 1,
    StatusName.BOUND: 4,          # 4–5 turns rolled at application
    StatusName.SEEDED: None,
    StatusName.CURSED: None,
    StatusName.NIGHTMARE: None,
    StatusName.TAUNTED: 3,
    StatusName.ENCORED: 3,
    StatusName.TORMENTED: None,
    StatusName.HEAL_BLOCKED: 5,
    StatusName.PERISH_SONG: 3,
    StatusName.YAWNING: 1,        # Falls asleep next turn

    # Naruto-inspired
    StatusName.IGNITED: None,
    StatusName.IMMOBILE: 1,
    StatusName.CHAOS: 1,
    StatusName.BLINDED: 3,
    StatusName.ACUPUNCTURED: 3,
    StatusName.IMPRISONED: None,
    StatusName.TAGGED: None,
    StatusName.ENFEEBLED: None,
    StatusName.WEAKENED: None,
    StatusName.CORRODED: None,
    StatusName.INTERRUPTED: 1,

    # Physical states
    StatusName.GROUNDED: None,    # implicit default; infinite if explicitly applied
    StatusName.AIRBORNE: None,    # lasts until hit or round end
    StatusName.LAUNCHED: 1,       # 1 round juggle window
    StatusName.KNOCKBACK: 1,      # resolved at round end

    # Utility states
    StatusName.SHIELDED: None,    # lasts until hit absorbs it
    StatusName.HIDDEN: None,      # lasts until damaged or round end
    StatusName.IMMUNE: 2,         # 2-round immunity window

    # Advanced states
    StatusName.CHAIN_BREAKER: None,  # indefinite; explicitly removed
    StatusName.STATE_LOCKED: 2,      # 2-round state lock
    StatusName.CHARGING: 1,          # 1-round charge; released next turn
}

# Stat modifier multipliers applied by statuses
# Key: status name → dict of stat → multiplier
STAT_MODIFIERS: dict[str, dict[str, float]] = {
    StatusName.BURNED: {"attack": 0.5},
    StatusName.PARALYZED: {"speed": 0.5},
    StatusName.ENFEEBLED: {"attack": 0.5, "sp_attack": 0.5},
    StatusName.WEAKENED: {"damage_output": 0.5},
    StatusName.TAGGED: {"defense": 0.7, "sp_defense": 0.7},
}

# Damage per turn as fraction of max HP (numerator; denominator=16)
# badly_poisoned escalates: base_damage * turns_active
DAMAGE_PER_TURN_SIXTEENTHS: dict[str, int] = {
    StatusName.BURNED: 1,        # 1/16 max HP
    StatusName.POISONED: 2,      # 2/16 = 1/8 max HP
    StatusName.BADLY_POISONED: 1,  # escalates each turn: 1/16, 2/16, 3/16…
    StatusName.SEEDED: 1,         # 1/16 (drains to opponent)
    StatusName.CURSED: 4,         # 1/4 max HP
    StatusName.NIGHTMARE: 4,      # 1/4 max HP (only while asleep)
    StatusName.BOUND: 1,          # 1/16 max HP per turn
    StatusName.IGNITED: 1,        # 1/16 + disables healing
    StatusName.IMPRISONED: 2,     # when attempting special move
    StatusName.CORRODED: 1,       # worsens each turn
}

# Which types are immune to which statuses
TYPE_IMMUNITIES: dict[str, list[str]] = {
    StatusName.BURNED: ["Fire"],
    StatusName.PARALYZED: ["Electric"],
    StatusName.FROZEN: ["Ice"],
    StatusName.POISONED: ["Poison", "Steel"],
    StatusName.BADLY_POISONED: ["Poison", "Steel"],
    StatusName.IGNITED: ["Fire", "Water"],
}
