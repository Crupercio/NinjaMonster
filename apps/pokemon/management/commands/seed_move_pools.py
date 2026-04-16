"""
Management command: seed_move_pools

Populates SpeciesMovePool entries for all Pokemon species with tactically
curated move sets. Also:
  - Updates Move.slot_type using heuristic rules
  - Assigns Pokemon.primary_role based on base stats
  - Tags SpeciesMovePool.role_tag with the species' role

Usage:
    python manage.py seed_move_pools
    python manage.py seed_move_pools --dry-run
    python manage.py seed_move_pools --clear   # delete existing entries first
"""
from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PASSIVE_MOVE_PKS: frozenset[int] = frozenset({
    68,   # Counter — reactive, fires back
    71,   # Absorb — drain
    72,   # Mega Drain — drain
    73,   # Leech Seed — persistent drain
    81,   # String Shot — persistent slow
})

# Curated pools for 30 featured Pokemon.
# Format: {pokemon_pk: (role, {slot_type: [move_pk, ...]})}
SPECIES_POOLS: dict[int, tuple[str, dict[str, list[int]]]] = {
    # --- Grass/Poison line — CONTROL ---
    1: ("control", {  # Bulbasaur
        "standard":  [22, 75],     # Vine Whip, Razor Leaf
        "chase":     [20, 40],     # Bind, Poison Sting
        "mystery":   [76, 80],     # Solar Beam, Petal Dance
        "passive_1": [77, 78, 79], # Poison Powder, Stun Spore, Sleep Powder
        "passive_2": [73],         # Leech Seed
    }),
    2: ("control", {  # Ivysaur
        "standard":  [22, 75],
        "chase":     [20, 72],     # Bind, Mega Drain
        "mystery":   [76, 34],     # Solar Beam, Body Slam
        "passive_1": [77, 78, 79],
        "passive_2": [73],
    }),
    3: ("control", {  # Venusaur
        "standard":  [75, 22],
        "chase":     [20, 72],
        "mystery":   [76, 80],
        "passive_1": [77, 79, 78],
        "passive_2": [73],
    }),
    # --- Fire line — BURST ---
    4: ("burst", {      # Charmander
        "standard":  [52, 10],    # Ember, Scratch
        "chase":     [83, 7],     # Fire Spin, Fire Punch
        "mystery":   [53],        # Flamethrower
        "passive_1": [45],        # Growl
        "passive_2": [71],        # Absorb
    }),
    5: ("burst", {      # Charmeleon
        "standard":  [52, 1],
        "chase":     [7, 83],
        "mystery":   [53, 34],    # Flamethrower, Body Slam
        "passive_1": [14, 45],    # Swords Dance, Growl
        "passive_2": [71],
    }),
    6: ("burst", {      # Charizard
        "standard":  [52, 17],    # Ember, Wing Attack
        "chase":     [7, 83],
        "mystery":   [53, 19, 38], # Flamethrower, Fly, Double-Edge
        "passive_1": [14, 43],    # Swords Dance, Leer
        "passive_2": [71],
    }),
    # --- Water line — TANK ---
    7: ("tank", {     # Squirtle
        "standard":  [55, 33],    # Water Gun, Tackle
        "chase":     [61, 35],    # Bubble Beam, Wrap
        "mystery":   [57],        # Surf
        "passive_1": [54, 39],    # Mist, Tail Whip
        "passive_2": [68],        # Counter
    }),
    8: ("tank", {     # Wartortle
        "standard":  [55, 23],
        "chase":     [61, 35],
        "mystery":   [57, 56],    # Surf, Hydro Pump
        "passive_1": [54, 28],    # Mist, Sand Attack
        "passive_2": [68],
    }),
    9: ("tank", {     # Blastoise
        "standard":  [55, 23],
        "chase":     [61, 9],     # Bubble Beam, Thunder Punch
        "mystery":   [56, 57],
        "passive_1": [54, 39, 28],
        "passive_2": [68],
    }),
    # --- Electric — COMBO ---
    10: ("combo", {  # Pikachu
        "standard":  [84, 15],    # Thunder Shock, Cut
        "chase":     [9, 3],      # Thunder Punch, Double Slap
        "mystery":   [34],        # Body Slam
        "passive_1": [14, 43],    # Swords Dance, Leer
        "passive_2": [81],        # String Shot
    }),
    11: ("burst", {       # Raichu
        "standard":  [84],
        "chase":     [9, 3],
        "mystery":   [34, 25],    # Body Slam, Mega Kick
        "passive_1": [14, 45],
        "passive_2": [81],
    }),
    # --- Ghost/Poison — COMBO / CONTROL ---
    12: ("combo", {  # Gengar
        "standard":  [33, 40],    # Tackle, Poison Sting
        "chase":     [44, 49],    # Bite, Sonic Boom
        "mystery":   [37, 12],    # Thrash, Guillotine
        "passive_1": [47, 48, 50], # Sing, Supersonic, Disable
        "passive_2": [73],
    }),
    13: ("control", {   # Haunter
        "standard":  [33],
        "chase":     [44, 49],
        "mystery":   [37],
        "passive_1": [47, 48, 50],
        "passive_2": [73],
    }),
    # --- Electric Eeveelutions ---
    14: ("combo", {  # Jolteon
        "standard":  [84, 15],
        "chase":     [9, 17],     # Thunder Punch, Wing Attack
        "mystery":   [34, 38],    # Body Slam, Double-Edge
        "passive_1": [14, 43],
        "passive_2": [81],
    }),
    15: ("tank", {   # Flareon
        "standard":  [52, 7],     # Ember, Fire Punch
        "chase":     [83, 31],    # Fire Spin, Fury Attack
        "mystery":   [53, 25],    # Flamethrower, Mega Kick
        "passive_1": [45, 43],
        "passive_2": [71],
    }),
    16: ("support", {   # Vaporeon
        "standard":  [55, 23],
        "chase":     [61, 72],    # Bubble Beam, Mega Drain
        "mystery":   [57, 56],
        "passive_1": [54, 74, 47], # Mist, Growth, Sing
        "passive_2": [73],
    }),
    # --- Ice/Water — TANK ---
    17: ("tank", {      # Lapras
        "standard":  [55, 23],
        "chase":     [62, 8],     # Aurora Beam, Ice Punch
        "mystery":   [57, 58, 59], # Surf, Ice Beam, Blizzard
        "passive_1": [46, 47],    # Roar, Sing
        "passive_2": [68],
    }),
    # --- Legendaries ---
    18: ("tank", {      # Articuno
        "standard":  [16, 64],    # Gust, Peck
        "chase":     [62, 8],
        "mystery":   [58, 59, 19], # Ice Beam, Blizzard, Fly
        "passive_1": [46, 50],    # Roar, Disable
        "passive_2": [68],
    }),
    19: ("burst", {       # Zapdos
        "standard":  [84, 16],
        "chase":     [9, 17],     # Thunder Punch, Wing Attack
        "mystery":   [34, 36],    # Body Slam, Take Down
        "passive_1": [14, 28],
        "passive_2": [81],
    }),
    20: ("burst", {       # Moltres
        "standard":  [52, 17],
        "chase":     [7, 83],
        "mystery":   [53, 19, 38],
        "passive_1": [45, 14],
        "passive_2": [71],
    }),
    # --- Psychic — COMBO / CONTROL ---
    21: ("combo", {  # Alakazam
        "standard":  [33, 1],
        "chase":     [60, 49],    # Psybeam, Sonic Boom
        "mystery":   [36, 63],    # Take Down, Hyper Beam
        "passive_1": [48, 43],    # Supersonic, Leer
        "passive_2": [73],
    }),
    22: ("control", {   # Hypno
        "standard":  [33],
        "chase":     [60, 44],
        "mystery":   [36],
        "passive_1": [47, 48, 50],
        "passive_2": [73],
    }),
    # --- Poison — CONTROL / TANK ---
    23: ("control", {   # Arbok
        "standard":  [40, 30],    # Poison Sting, Horn Attack
        "chase":     [20, 35],    # Bind, Wrap
        "mystery":   [34, 21],    # Body Slam, Slam
        "passive_1": [77, 28],    # Poison Powder, Sand Attack
        "passive_2": [73],
    }),
    24: ("tank", {      # Weezing
        "standard":  [40, 51],    # Poison Sting, Acid
        "chase":     [20, 44],    # Bind, Bite
        "mystery":   [34, 21],
        "passive_1": [77, 50, 28], # Poison Powder, Disable, Sand Attack
        "passive_2": [73],
    }),
    # --- Fighting — TANK ---
    25: ("tank", {   # Machamp
        "standard":  [2, 1],      # Karate Chop, Pound
        "chase":     [24, 27, 67], # Double Kick, Rolling Kick, Low Kick
        "mystery":   [26, 66, 25], # Jump Kick, Submission, Mega Kick
        "passive_1": [14, 45, 43],
        "passive_2": [68],
    }),
    # --- Water/Psychic — COMBO ---
    26: ("combo", {  # Starmie
        "standard":  [55, 15],
        "chase":     [61, 60],    # Bubble Beam, Psybeam
        "mystery":   [57, 56],
        "passive_1": [28, 48],
        "passive_2": [73],
    }),
    # --- Dragon — TANK ---
    27: ("tank", {   # Dragonite
        "standard":  [17, 29],    # Wing Attack, Headbutt
        "chase":     [9, 7],      # Thunder Punch, Fire Punch
        "mystery":   [38, 19, 63], # Double-Edge, Fly, Hyper Beam
        "passive_1": [14, 43],
        "passive_2": [71],
    }),
    # --- Mewtwo/Mew — BURST / SUPPORT ---
    28: ("burst", {       # Mewtwo
        "standard":  [33, 23],
        "chase":     [60, 44],
        "mystery":   [63, 36, 37], # Hyper Beam, Take Down, Thrash
        "passive_1": [48, 50, 46],
        "passive_2": [73],
    }),
    29: ("support", {   # Mew
        "standard":  [1, 33],
        "chase":     [60, 72],
        "mystery":   [34, 76],
        "passive_1": [47, 74, 79, 78],
        "passive_2": [73],
    }),
    # --- Dark — TANK ---
    30: ("tank", {      # Umbreon
        "standard":  [33, 44],    # Tackle, Bite
        "chase":     [35, 49],    # Wrap, Sonic Boom
        "mystery":   [34, 38],    # Body Slam, Double-Edge
        "passive_1": [39, 46, 50], # Tail Whip, Roar, Disable
        "passive_2": [68],
    }),
}

# Fallback pools keyed by primary type name.
TYPE_POOLS: dict[str, dict[str, list[int]]] = {
    "Normal":   {"standard": [33, 1, 15],  "chase": [3, 31, 4],   "mystery": [5, 25, 34, 38],  "passive_1": [39, 43, 45, 18], "passive_2": [68]},
    "Fire":     {"standard": [52],          "chase": [7, 83],      "mystery": [53],              "passive_1": [45, 14],          "passive_2": [71]},
    "Water":    {"standard": [55, 23],      "chase": [61, 35],     "mystery": [57, 56],          "passive_1": [54, 28, 39],      "passive_2": [68]},
    "Electric": {"standard": [84, 15],      "chase": [9, 3],       "mystery": [34],              "passive_1": [14, 43],          "passive_2": [81]},
    "Grass":    {"standard": [22, 75],      "chase": [20, 72],     "mystery": [76, 80],          "passive_1": [77, 78, 79, 74],  "passive_2": [73]},
    "Ice":      {"standard": [16, 64],      "chase": [62, 8],      "mystery": [58, 59],          "passive_1": [46, 47],          "passive_2": [68]},
    "Fighting": {"standard": [2, 15],       "chase": [24, 27, 67], "mystery": [26, 66, 25],      "passive_1": [43, 45, 14],      "passive_2": [68]},
    "Poison":   {"standard": [40, 51],      "chase": [20, 35],     "mystery": [34, 21],          "passive_1": [77, 28, 50],      "passive_2": [73]},
    "Ground":   {"standard": [23, 29],      "chase": [20, 35],     "mystery": [34, 21, 70],      "passive_1": [28, 43, 39],      "passive_2": [68]},
    "Flying":   {"standard": [16, 64],      "chase": [17, 31],     "mystery": [19, 65, 25],      "passive_1": [18, 43, 45],      "passive_2": [81]},
    "Psychic":  {"standard": [33, 1],       "chase": [60, 49],     "mystery": [36, 63],          "passive_1": [47, 48, 50],      "passive_2": [73]},
    "Bug":      {"standard": [64, 33],      "chase": [41, 42, 20], "mystery": [34, 21],          "passive_1": [81, 28, 45],      "passive_2": [73]},
    "Rock":     {"standard": [29, 23],      "chase": [31, 20],     "mystery": [34, 36, 70],      "passive_1": [28, 43],          "passive_2": [68]},
    "Ghost":    {"standard": [33, 44],      "chase": [49, 44],     "mystery": [37, 12],          "passive_1": [47, 48, 50],      "passive_2": [73]},
    "Dragon":   {"standard": [29, 17],      "chase": [9, 7],       "mystery": [38, 63],          "passive_1": [14, 43],          "passive_2": [71]},
    "Dark":     {"standard": [33, 44],      "chase": [35, 49],     "mystery": [34, 38],          "passive_1": [39, 46, 50],      "passive_2": [68]},
    "Steel":    {"standard": [23, 29],      "chase": [20, 9],      "mystery": [34, 70],          "passive_1": [43, 28],          "passive_2": [68]},
    "Fairy":    {"standard": [1, 33],       "chase": [3, 60],      "mystery": [34, 21],          "passive_1": [47, 45, 74],      "passive_2": [73]},
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def infer_slot_type(move: Any) -> str:
    """Determine the appropriate MoveSlotType value for a move using heuristics."""
    if move.is_charge_move:
        return "mystery"
    if move.power == 0 and move.accuracy <= 30:
        return "mystery"  # OHKO moves
    if move.power == 0 and move.pk in PASSIVE_MOVE_PKS:
        return "passive_2"
    if move.power > 0 and move.pk in PASSIVE_MOVE_PKS:
        return "passive_2"
    if move.power == 0:
        return "passive_1"
    if move.always_first or move.priority > 0:
        return "chase"
    if move.power >= 80:
        return "mystery"
    if move.power <= 25:
        return "chase"
    if move.power >= 60:
        return "chase"
    return "standard"


def determine_role(species: Any) -> str:
    """Assign a TacticalRole value based on base stats."""
    speed = species.base_initiative
    atk = species.base_attack
    spa = species.base_ninjutsu
    total_def = species.base_hp + species.base_defense + species.base_sp_defense
    total_off = atk + spa

    if speed >= 110 and total_off >= 150:
        return "combo"
    if total_off >= 220:
        return "tank" if atk >= spa else "burst"
    if total_def >= 260 and total_off < 200:
        return "tank"
    if total_off < 170:
        return "support" if species.base_hp >= 90 else "control"
    return "burst"


# ---------------------------------------------------------------------------
# Management command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = (
        "Seed SpeciesMovePool entries for all Pokemon species. "
        "Also infers Move.slot_type and assigns Pokemon.primary_role."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Show what would be done without writing to the database.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            default=False,
            help="Delete all existing SpeciesMovePool entries before seeding.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        # Lazy import to avoid app-registry issues at module load time.
        from apps.pokemon.models import Move, MoveSlotType, Pokemon, SpeciesMovePool

        dry_run: bool = options["dry_run"]
        clear: bool = options["clear"]

        self.stdout.write(self.style.MIGRATE_HEADING("=== seed_move_pools ==="))
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be written."))

        with transaction.atomic():
            # ------------------------------------------------------------------
            # Optional clear
            # ------------------------------------------------------------------
            if clear and not dry_run:
                deleted_count, _ = SpeciesMovePool.objects.all().delete()
                self.stdout.write(f"Cleared {deleted_count} existing SpeciesMovePool entries.")
            elif clear and dry_run:
                existing = SpeciesMovePool.objects.count()
                self.stdout.write(f"[dry-run] Would delete {existing} existing SpeciesMovePool entries.")

            # ------------------------------------------------------------------
            # Step 1 — Update Move.slot_type
            # ------------------------------------------------------------------
            self.stdout.write(self.style.MIGRATE_LABEL("Step 1: Inferring Move.slot_type …"))
            moves = list(Move.objects.all())
            moves_to_update: list[Any] = []
            for move in moves:
                new_slot = infer_slot_type(move)
                if move.slot_type != new_slot:
                    move.slot_type = new_slot
                    moves_to_update.append(move)

            if not dry_run:
                batch_size = 200
                for i in range(0, len(moves_to_update), batch_size):
                    Move.objects.bulk_update(
                        moves_to_update[i : i + batch_size],
                        ["slot_type"],
                    )
                self.stdout.write(
                    self.style.SUCCESS(f"  Updated slot_type on {len(moves_to_update)} moves.")
                )
            else:
                self.stdout.write(
                    f"  [dry-run] Would update slot_type on {len(moves_to_update)} moves."
                )

            # ------------------------------------------------------------------
            # Step 2 — Assign Pokemon.primary_role
            # ------------------------------------------------------------------
            self.stdout.write(self.style.MIGRATE_LABEL("Step 2: Assigning Pokemon.primary_role …"))
            all_species = list(Pokemon.objects.all())
            species_to_update: list[Any] = []
            for species in all_species:
                if species.pk in SPECIES_POOLS:
                    new_role = SPECIES_POOLS[species.pk][0]
                else:
                    new_role = determine_role(species)
                if species.primary_role != new_role:
                    species.primary_role = new_role
                    species_to_update.append(species)

            if not dry_run:
                Pokemon.objects.bulk_update(species_to_update, ["primary_role"])
                self.stdout.write(
                    self.style.SUCCESS(f"  Assigned primary_role to {len(species_to_update)} species.")
                )
            else:
                self.stdout.write(
                    f"  [dry-run] Would update primary_role on {len(species_to_update)} species."
                )

            # ------------------------------------------------------------------
            # Step 3 — Create SpeciesMovePool entries
            # ------------------------------------------------------------------
            self.stdout.write(self.style.MIGRATE_LABEL("Step 3: Creating SpeciesMovePool entries …"))

            # Build a lookup of all move PKs that actually exist.
            existing_move_pks: frozenset[int] = frozenset(
                Move.objects.values_list("pk", flat=True)
            )

            # Reload species with primary_type name (needed for TYPE_POOLS lookup).
            all_species_with_type = list(
                Pokemon.objects.select_related("primary_type").all()
            )

            created_count = 0
            skipped_count = 0
            missing_move_count = 0

            # Build a set of (species_pk, move_pk) already present so we can
            # avoid redundant DB round-trips when clear was not used.
            if not clear:
                existing_pairs: set[tuple[int, int]] = set(
                    SpeciesMovePool.objects.values_list("species_id", "move_id")
                )
            else:
                existing_pairs = set()

            entries_to_create: list[SpeciesMovePool] = []

            for species in all_species_with_type:
                if species.pk in SPECIES_POOLS:
                    role, pool_def = SPECIES_POOLS[species.pk]
                else:
                    type_name = species.primary_type.name
                    pool_def = TYPE_POOLS.get(type_name, {})
                    role = species.primary_role  # already updated in step 2

                for slot_type, move_pk_list in pool_def.items():
                    for move_pk in move_pk_list:
                        if move_pk not in existing_move_pks:
                            logger.warning(
                                "Move pk=%s not found in database — skipping for species %s.",
                                move_pk,
                                species.name,
                            )
                            missing_move_count += 1
                            continue
                        if (species.pk, move_pk) in existing_pairs:
                            skipped_count += 1
                            continue
                        entries_to_create.append(
                            SpeciesMovePool(
                                species_id=species.pk,
                                move_id=move_pk,
                                slot_type=slot_type,
                                role_tag=role,
                            )
                        )
                        existing_pairs.add((species.pk, move_pk))
                        created_count += 1

            if not dry_run:
                SpeciesMovePool.objects.bulk_create(entries_to_create, batch_size=500)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Created {created_count} new SpeciesMovePool entries "
                        f"({skipped_count} already existed, {missing_move_count} missing moves skipped)."
                    )
                )
            else:
                self.stdout.write(
                    f"  [dry-run] Would create {created_count} new SpeciesMovePool entries "
                    f"({skipped_count} already exist, {missing_move_count} missing moves would be skipped)."
                )

            if dry_run:
                # Roll back everything so no writes persist.
                transaction.set_rollback(True)

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run complete — database unchanged."))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"seed_move_pools complete: "
                    f"{len(moves_to_update)} moves updated, "
                    f"{len(species_to_update)} species roles assigned, "
                    f"{created_count} pool entries created."
                )
            )
