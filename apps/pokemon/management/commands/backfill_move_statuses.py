"""
Management command: backfill_move_statuses

Assigns applies_status, trigger_status, combo_starter, and combo_trigger
to Move records whose fixture entries were created without those fields.

All status PKs reference the effects.StatusEffect fixture:
  1  burned          2  poisoned       3  badly_poisoned
  4  paralyzed       5  frozen         6  asleep
  7  confused        9  flinched      10  bound
 11  seeded         12  cursed        13  nightmare
 14  taunted        15  encored       16  tormented
 17  heal_blocked   18  perish_song   19  yawning

Usage:
    python manage.py backfill_move_statuses
    python manage.py backfill_move_statuses --dry-run
    python manage.py backfill_move_statuses --reset     # clears all then reapplies
"""
from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Status IDs (match effects/fixtures/status_effects.json)
# ---------------------------------------------------------------------------
BURNED = 1
POISONED = 2
BADLY_POISONED = 3
PARALYZED = 4
FROZEN = 5
ASLEEP = 6
CONFUSED = 7
FLINCHED = 9
BOUND = 10
SEEDED = 11
CURSED = 12
NIGHTMARE = 13
TAUNTED = 14
ENCORED = 15
TORMENTED = 16
HEAL_BLOCKED = 17
PERISH_SONG = 18
YAWNING = 19

# ---------------------------------------------------------------------------
# applies_status: move pk → StatusEffect pk
# ---------------------------------------------------------------------------
APPLIES_STATUS: dict[int, int] = {
    # ── BURN ─────────────────────────────────────────────────────────────
    7: BURNED,    # Fire Punch
    52: BURNED,   # Ember
    53: BURNED,   # Flamethrower
    83: BURNED,   # Fire Spin
    126: BURNED,  # Fire Blast
    172: BURNED,  # Flame Wheel
    221: BURNED,  # Sacred Fire
    257: BURNED,  # Heat Wave
    261: BURNED,  # Will-O-Wisp
    299: BURNED,  # Blaze Kick
    394: BURNED,  # Flare Blitz
    424: BURNED,  # Fire Fang
    436: BURNED,  # Lava Plume
    481: BURNED,  # Flame Burst
    488: BURNED,  # Flame Charge
    517: BURNED,  # Inferno
    519: BURNED,  # Fire Pledge
    545: BURNED,  # Searing Shot
    551: BURNED,  # Blue Flare
    552: BURNED,  # Fiery Dance
    558: BURNED,  # Fusion Flare
    595: BURNED,  # Mystical Fire
    680: BURNED,  # Fire Lash
    725: BURNED,  # Sizzly Slide
    752: BURNED,  # Pyro Ball
    779: BURNED,  # Burning Jealousy
    805: BURNED,  # Raging Fury
    834: BURNED,  # Armor Cannon
    835: BURNED,  # Bitter Blade
    840: BURNED,  # Torch Song
    # ── POISONED ─────────────────────────────────────────────────────────
    40: POISONED,   # Poison Sting
    41: POISONED,   # Twineedle
    51: POISONED,   # Acid
    77: POISONED,   # Poison Powder
    123: POISONED,  # Smog
    124: POISONED,  # Sludge
    139: POISONED,  # Poison Gas
    188: POISONED,  # Sludge Bomb
    342: POISONED,  # Poison Tail
    398: POISONED,  # Poison Jab
    440: POISONED,  # Cross Poison
    441: POISONED,  # Gunk Shot
    482: POISONED,  # Sludge Wave
    672: POISONED,  # Toxic Thread
    773: POISONED,  # Shell Side Arm
    799: POISONED,  # Dire Claw
    846: POISONED,  # Barb Barrage
    881: POISONED,  # Barb Barrage 2
    # ── BADLY POISONED ───────────────────────────────────────────────────
    92: BADLY_POISONED,   # Toxic
    305: BADLY_POISONED,  # Poison Fang
    912: BADLY_POISONED,  # Malignant Chain
    # ── PARALYZED ────────────────────────────────────────────────────────
    9: PARALYZED,    # Thunder Punch
    34: PARALYZED,   # Body Slam
    84: PARALYZED,   # Thunder Shock
    85: PARALYZED,   # Thunderbolt
    86: PARALYZED,   # Thunder Wave
    87: PARALYZED,   # Thunder
    122: PARALYZED,  # Lick
    192: PARALYZED,  # Zap Cannon
    209: PARALYZED,  # Spark
    225: PARALYZED,  # Dragon Breath
    340: PARALYZED,  # Bounce
    395: PARALYZED,  # Force Palm
    422: PARALYZED,  # Thunder Fang
    435: PARALYZED,  # Discharge
    527: PARALYZED,  # Electroweb
    550: PARALYZED,  # Bolt Strike
    609: PARALYZED,  # Nuzzle
    707: PARALYZED,  # Zing Zap
    720: PARALYZED,  # Splishy Splash
    724: PARALYZED,  # Puzzy Buzz
    # ── FROZEN ───────────────────────────────────────────────────────────
    8: FROZEN,    # Ice Punch
    58: FROZEN,   # Ice Beam
    59: FROZEN,   # Blizzard
    181: FROZEN,  # Powder Snow
    301: FROZEN,  # Ice Ball
    333: FROZEN,  # Icicle Spear
    419: FROZEN,  # Avalanche
    420: FROZEN,  # Ice Shard
    423: FROZEN,  # Ice Fang
    553: FROZEN,  # Freeze Shock
    556: FROZEN,  # Icicle Crash
    573: FROZEN,  # Freeze-Dry
    665: FROZEN,  # Ice Hammer
    729: FROZEN,  # Freezy Frost
    793: FROZEN,  # Freezing Glare
    796: FROZEN,  # Glacial Lance
    # ── ASLEEP ───────────────────────────────────────────────────────────
    47: ASLEEP,   # Sing
    79: ASLEEP,   # Sleep Powder
    95: ASLEEP,   # Hypnosis
    142: ASLEEP,  # Lovely Kiss
    147: ASLEEP,  # Spore
    320: ASLEEP,  # Grass Whistle
    464: ASLEEP,  # Dark Void
    547: ASLEEP,  # Relic Song
    # ── CONFUSED ─────────────────────────────────────────────────────────
    48: CONFUSED,   # Supersonic
    60: CONFUSED,   # Psybeam
    109: CONFUSED,  # Confuse Ray
    146: CONFUSED,  # Dizzy Punch
    186: CONFUSED,  # Sweet Kiss
    207: CONFUSED,  # Swagger
    223: CONFUSED,  # Dynamic Punch
    260: CONFUSED,  # Flatter
    298: CONFUSED,  # Teeter Dance
    352: CONFUSED,  # Water Pulse
    431: CONFUSED,  # Rock Climb
    448: CONFUSED,  # Chatter
    542: CONFUSED,  # Hurricane
    762: CONFUSED,  # Strange Steam
    # ── FLINCHED ─────────────────────────────────────────────────────────
    23: FLINCHED,   # Stomp
    27: FLINCHED,   # Rolling Kick
    29: FLINCHED,   # Headbutt
    44: FLINCHED,   # Bite
    125: FLINCHED,  # Bone Club
    157: FLINCHED,  # Rock Slide
    158: FLINCHED,  # Hyper Fang
    310: FLINCHED,  # Astonish
    326: FLINCHED,  # Extrasensory
    399: FLINCHED,  # Dark Pulse
    403: FLINCHED,  # Air Slash
    407: FLINCHED,  # Dragon Rush
    422: FLINCHED,  # Thunder Fang — also paralyzed; burn wins, flinch second
    423: FLINCHED,  # Ice Fang — also frozen; flinch as primary here
    424: FLINCHED,  # Fire Fang — also burned; keep burn above, flinch for Ice/Fire Fang
    428: FLINCHED,  # Zen Headbutt
    442: FLINCHED,  # Iron Head
    531: FLINCHED,  # Heart Stamp
    556: FLINCHED,  # Icicle Crash
    721: FLINCHED,  # Floaty Fall
    732: FLINCHED,  # Double Iron Bash
    808: FLINCHED,  # Mountain Gale
    # ── BOUND ────────────────────────────────────────────────────────────
    20: BOUND,    # Bind
    35: BOUND,    # Wrap
    83: BOUND,    # Fire Spin (also burn — bound takes priority as primary game effect)
    128: BOUND,   # Clamp
    250: BOUND,   # Whirlpool
    328: BOUND,   # Sand Tomb
    463: BOUND,   # Magma Storm
    611: BOUND,   # Infestation
    791: BOUND,   # Thunder Cage
    # ── SEEDED ───────────────────────────────────────────────────────────
    73: SEEDED,   # Leech Seed
    728: SEEDED,  # Sappy Seed
    # ── NIGHTMARE ────────────────────────────────────────────────────────
    171: NIGHTMARE,  # Nightmare — also has trigger below
    # ── TAUNTED ──────────────────────────────────────────────────────────
    269: TAUNTED,  # Taunt
    # ── ENCORED ──────────────────────────────────────────────────────────
    227: ENCORED,  # Encore
    # ── TORMENTED ────────────────────────────────────────────────────────
    259: TORMENTED,  # Torment
    # ── HEAL BLOCKED ─────────────────────────────────────────────────────
    377: HEAL_BLOCKED,  # Heal Block
    # ── PERISH SONG ──────────────────────────────────────────────────────
    195: PERISH_SONG,  # Perish Song
    # ── YAWNING ──────────────────────────────────────────────────────────
    281: YAWNING,  # Yawn
}

# Fire Fang & Ice Fang: burn/freeze are more canonical than flinch
# Overwrite with canonical effect.
APPLIES_STATUS[424] = BURNED   # Fire Fang → burned
APPLIES_STATUS[423] = FROZEN   # Ice Fang → frozen
APPLIES_STATUS[422] = PARALYZED  # Thunder Fang → paralyzed
# Fire Spin: bound traps are the key mechanic
APPLIES_STATUS[83] = BOUND

# ---------------------------------------------------------------------------
# trigger_status: move pk → StatusEffect pk
# Moves that fire as a combo follow-up when the enemy has this status.
# ---------------------------------------------------------------------------
TRIGGER_STATUS: dict[int, int] = {
    138: ASLEEP,     # Dream Eater — fires when enemy is asleep
    171: ASLEEP,     # Nightmare — fires when enemy is asleep (also applies nightmare)
    265: PARALYZED,  # Smelling Salts — double damage vs paralyzed
    358: ASLEEP,     # Wake-Up Slap — double damage vs asleep
    474: POISONED,   # Venoshock — double damage vs poisoned
    506: BURNED,     # Hex — double damage vs any status; burned chosen as primary
    599: POISONED,   # Venom Drench — stat-lowers poisoned targets
    844: BURNED,     # Infernal Parade — double damage vs status targets
    846: POISONED,   # Barb Barrage — double damage vs poisoned
}

# ---------------------------------------------------------------------------
# Combo flags: derived automatically from the two dicts above.
# Any move with applies_status is a potential combo starter.
# Any move with trigger_status is a combo trigger (fires automatically).
# ---------------------------------------------------------------------------


class Command(BaseCommand):
    help = (
        "Backfill applies_status, trigger_status, combo_starter, and "
        "combo_trigger fields on Move records from the static mapping table."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without writing to the database.",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Clear all status fields on ALL moves before reapplying.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from apps.effects.models import StatusEffect
        from apps.pokemon.models import Move

        dry_run: bool = options["dry_run"]
        reset: bool = options["reset"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be saved."))

        # Preload StatusEffect instances keyed by pk.
        status_map: dict[int, StatusEffect] = {
            se.pk: se for se in StatusEffect.objects.all()
        }
        missing_statuses = (
            set(APPLIES_STATUS.values())
            | set(TRIGGER_STATUS.values())
        ) - set(status_map.keys())
        if missing_statuses:
            self.stderr.write(
                self.style.ERROR(
                    f"StatusEffect pks not found in DB: {sorted(missing_statuses)}. "
                    "Run: python manage.py loaddata status_effects"
                )
            )
            return

        # Preload all Move instances keyed by pk.
        move_map: dict[int, Move] = {m.pk: m for m in Move.objects.all()}

        # Warn about pks in the mapping that don't exist in the DB.
        all_configured_pks = set(APPLIES_STATUS) | set(TRIGGER_STATUS)
        absent_pks = all_configured_pks - set(move_map)
        if absent_pks:
            self.stdout.write(
                self.style.WARNING(
                    f"Move pks in mapping but not in DB (skipped): "
                    f"{sorted(absent_pks)}"
                )
            )

        with transaction.atomic():
            if reset and not dry_run:
                cleared = Move.objects.update(
                    applies_status=None,
                    trigger_status=None,
                    combo_starter=False,
                    combo_trigger=False,
                )
                self.stdout.write(f"Reset {cleared} moves to NULL status fields.")

            updated_applies = 0
            updated_trigger = 0

            for pk, status_pk in APPLIES_STATUS.items():
                move = move_map.get(pk)
                if move is None:
                    continue
                status = status_map[status_pk]
                if not dry_run:
                    move.applies_status = status
                    move.combo_starter = True
                updated_applies += 1
                logger.debug("applies_status: Move pk=%d ← %s", pk, status.name)

            for pk, status_pk in TRIGGER_STATUS.items():
                move = move_map.get(pk)
                if move is None:
                    continue
                status = status_map[status_pk]
                if not dry_run:
                    move.trigger_status = status
                    move.combo_trigger = True
                updated_trigger += 1
                logger.debug("trigger_status: Move pk=%d ← %s", pk, status.name)

            if not dry_run:
                # Bulk-save only moves that were actually modified.
                modified_pks = all_configured_pks & set(move_map)
                moves_to_save = [move_map[pk] for pk in modified_pks]
                Move.objects.bulk_update(
                    moves_to_save,
                    fields=["applies_status", "trigger_status", "combo_starter", "combo_trigger"],
                )

            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"DRY RUN: would set applies_status on {updated_applies} moves, "
                        f"trigger_status on {updated_trigger} moves."
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Done. applies_status set on {updated_applies} moves, "
                        f"trigger_status set on {updated_trigger} moves."
                    )
                )
