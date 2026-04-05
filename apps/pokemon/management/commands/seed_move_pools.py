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
        "standard": [22, 75],     # Vine Whip, Razor Leaf
        "chase":    [20, 40],     # Bind, Poison Sting
        "special":  [76, 80],     # Solar Beam, Petal Dance
        "support":  [77, 78, 79], # Poison Powder, Stun Spore, Sleep Powder
        "passive":  [73],         # Leech Seed
    }),
    2: ("control", {  # Ivysaur
        "standard": [22, 75],
        "chase":    [20, 72],     # Bind, Mega Drain
        "special":  [76, 34],     # Solar Beam, Body Slam
        "support":  [77, 78, 79],
        "passive":  [73],
    }),
    3: ("control", {  # Venusaur
        "standard": [75, 22],
        "chase":    [20, 72],
        "special":  [76, 80],
        "support":  [77, 79, 78],
        "passive":  [73],
    }),
    # --- Fire line — DPS ---
    4: ("dps", {      # Charmander
        "standard": [52, 10],     # Ember, Scratch
        "chase":    [83, 7],      # Fire Spin, Fire Punch
        "special":  [53],         # Flamethrower
        "support":  [45],         # Growl
        "passive":  [71],         # Absorb
    }),
    5: ("dps", {      # Charmeleon
        "standard": [52, 1],
        "chase":    [7, 83],
        "special":  [53, 34],     # Flamethrower, Body Slam
        "support":  [14, 45],     # Swords Dance, Growl
        "passive":  [71],
    }),
    6: ("dps", {      # Charizard
        "standard": [52, 17],     # Ember, Wing Attack
        "chase":    [7, 83],
        "special":  [53, 19, 38], # Flamethrower, Fly, Double-Edge
        "support":  [14, 43],     # Swords Dance, Leer
        "passive":  [71],
    }),
    # --- Water line — TANK ---
    7: ("tank", {     # Squirtle
        "standard": [55, 33],     # Water Gun, Tackle
        "chase":    [61, 35],     # Bubble Beam, Wrap
        "special":  [57],         # Surf
        "support":  [54, 39],     # Mist, Tail Whip
        "passive":  [68],         # Counter
    }),
    8: ("tank", {     # Wartortle
        "standard": [55, 23],
        "chase":    [61, 35],
        "special":  [57, 56],     # Surf, Hydro Pump
        "support":  [54, 28],     # Mist, Sand Attack
        "passive":  [68],
    }),
    9: ("tank", {     # Blastoise
        "standard": [55, 23],
        "chase":    [61, 9],      # Bubble Beam, Thunder Punch
        "special":  [56, 57],
        "support":  [54, 39, 28],
        "passive":  [68],
    }),
    # --- Electric — ASSASSIN ---
    10: ("assassin", {  # Pikachu
        "standard": [84, 15],     # Thunder Shock, Cut
        "chase":    [9, 3],       # Thunder Punch, Double Slap
        "special":  [34],         # Body Slam
        "support":  [14, 43],     # Swords Dance, Leer
        "passive":  [81],         # String Shot
    }),
    11: ("dps", {       # Raichu
        "standard": [84],
        "chase":    [9, 3],
        "special":  [34, 25],     # Body Slam, Mega Kick
        "support":  [14, 45],
        "passive":  [81],
    }),
    # --- Ghost/Poison — ASSASSIN / CONTROL ---
    12: ("assassin", {  # Gengar
        "standard": [33, 40],     # Tackle, Poison Sting
        "chase":    [44, 49],     # Bite, Sonic Boom
        "special":  [37, 12],     # Thrash, Guillotine
        "support":  [47, 48, 50], # Sing, Supersonic, Disable
        "passive":  [73],
    }),
    13: ("control", {   # Haunter
        "standard": [33],
        "chase":    [44, 49],
        "special":  [37],
        "support":  [47, 48, 50],
        "passive":  [73],
    }),
    # --- Electric Eeveelutions ---
    14: ("assassin", {  # Jolteon
        "standard": [84, 15],
        "chase":    [9, 17],      # Thunder Punch, Wing Attack
        "special":  [34, 38],     # Body Slam, Double-Edge
        "support":  [14, 43],
        "passive":  [81],
    }),
    15: ("bruiser", {   # Flareon
        "standard": [52, 7],      # Ember, Fire Punch
        "chase":    [83, 31],     # Fire Spin, Fury Attack
        "special":  [53, 25],     # Flamethrower, Mega Kick
        "support":  [45, 43],
        "passive":  [71],
    }),
    16: ("support", {   # Vaporeon
        "standard": [55, 23],
        "chase":    [61, 72],     # Bubble Beam, Mega Drain
        "special":  [57, 56],
        "support":  [54, 74, 47], # Mist, Growth, Sing
        "passive":  [73],
    }),
    # --- Ice/Water — TANK ---
    17: ("tank", {      # Lapras
        "standard": [55, 23],
        "chase":    [62, 8],      # Aurora Beam, Ice Punch
        "special":  [57, 58, 59], # Surf, Ice Beam, Blizzard
        "support":  [46, 47],     # Roar, Sing
        "passive":  [68],
    }),
    # --- Legendaries ---
    18: ("tank", {      # Articuno
        "standard": [16, 64],     # Gust, Peck
        "chase":    [62, 8],
        "special":  [58, 59, 19], # Ice Beam, Blizzard, Fly
        "support":  [46, 50],     # Roar, Disable
        "passive":  [68],
    }),
    19: ("dps", {       # Zapdos
        "standard": [84, 16],
        "chase":    [9, 17],      # Thunder Punch, Wing Attack
        "special":  [34, 36],     # Body Slam, Take Down
        "support":  [14, 28],
        "passive":  [81],
    }),
    20: ("dps", {       # Moltres
        "standard": [52, 17],
        "chase":    [7, 83],
        "special":  [53, 19, 38],
        "support":  [45, 14],
        "passive":  [71],
    }),
    # --- Psychic — ASSASSIN / CONTROL ---
    21: ("assassin", {  # Alakazam
        "standard": [33, 1],
        "chase":    [60, 49],     # Psybeam, Sonic Boom
        "special":  [36, 63],     # Take Down, Hyper Beam
        "support":  [48, 43],     # Supersonic, Leer
        "passive":  [73],
    }),
    22: ("control", {   # Hypno
        "standard": [33],
        "chase":    [60, 44],
        "special":  [36],
        "support":  [47, 48, 50],
        "passive":  [73],
    }),
    # --- Poison — CONTROL / TANK ---
    23: ("control", {   # Arbok
        "standard": [40, 30],     # Poison Sting, Horn Attack
        "chase":    [20, 35],     # Bind, Wrap
        "special":  [34, 21],     # Body Slam, Slam
        "support":  [77, 28],     # Poison Powder, Sand Attack
        "passive":  [73],
    }),
    24: ("tank", {      # Weezing
        "standard": [40, 51],     # Poison Sting, Acid
        "chase":    [20, 44],     # Bind, Bite
        "special":  [34, 21],
        "support":  [77, 50, 28], # Poison Powder, Disable, Sand Attack
        "passive":  [73],
    }),
    # --- Fighting — BRUISER ---
    25: ("bruiser", {   # Machamp
        "standard": [2, 1],       # Karate Chop, Pound
        "chase":    [24, 27, 67], # Double Kick, Rolling Kick, Low Kick
        "special":  [26, 66, 25], # Jump Kick, Submission, Mega Kick
        "support":  [14, 45, 43],
        "passive":  [68],
    }),
    # --- Water/Psychic — ASSASSIN ---
    26: ("assassin", {  # Starmie
        "standard": [55, 15],
        "chase":    [61, 60],     # Bubble Beam, Psybeam
        "special":  [57, 56],
        "support":  [28, 48],
        "passive":  [73],
    }),
    # --- Dragon — BRUISER ---
    27: ("bruiser", {   # Dragonite
        "standard": [17, 29],     # Wing Attack, Headbutt
        "chase":    [9, 7],       # Thunder Punch, Fire Punch
        "special":  [38, 19, 63], # Double-Edge, Fly, Hyper Beam
        "support":  [14, 43],
        "passive":  [71],
    }),
    # --- Mewtwo/Mew — DPS / SUPPORT ---
    28: ("dps", {       # Mewtwo
        "standard": [33, 23],
        "chase":    [60, 44],
        "special":  [63, 36, 37], # Hyper Beam, Take Down, Thrash
        "support":  [48, 50, 46],
        "passive":  [73],
    }),
    29: ("support", {   # Mew
        "standard": [1, 33],
        "chase":    [60, 72],
        "special":  [34, 76],
        "support":  [47, 74, 79, 78],
        "passive":  [73],
    }),
    # --- Dark — TANK ---
    30: ("tank", {      # Umbreon
        "standard": [33, 44],     # Tackle, Bite
        "chase":    [35, 49],     # Wrap, Sonic Boom
        "special":  [34, 38],     # Body Slam, Double-Edge
        "support":  [39, 46, 50], # Tail Whip, Roar, Disable
        "passive":  [68],
    }),
}

# Fallback pools keyed by primary type name.
TYPE_POOLS: dict[str, dict[str, list[int]]] = {
    "Normal":   {"standard": [33, 1, 15],  "chase": [3, 31, 4],   "special": [5, 25, 34, 38],  "support": [39, 43, 45, 18], "passive": [68]},
    "Fire":     {"standard": [52],          "chase": [7, 83],      "special": [53],              "support": [45, 14],          "passive": [71]},
    "Water":    {"standard": [55, 23],      "chase": [61, 35],     "special": [57, 56],          "support": [54, 28, 39],      "passive": [68]},
    "Electric": {"standard": [84, 15],      "chase": [9, 3],       "special": [34],              "support": [14, 43],          "passive": [81]},
    "Grass":    {"standard": [22, 75],      "chase": [20, 72],     "special": [76, 80],          "support": [77, 78, 79, 74],  "passive": [73]},
    "Ice":      {"standard": [16, 64],      "chase": [62, 8],      "special": [58, 59],          "support": [46, 47],          "passive": [68]},
    "Fighting": {"standard": [2, 15],       "chase": [24, 27, 67], "special": [26, 66, 25],      "support": [43, 45, 14],      "passive": [68]},
    "Poison":   {"standard": [40, 51],      "chase": [20, 35],     "special": [34, 21],          "support": [77, 28, 50],      "passive": [73]},
    "Ground":   {"standard": [23, 29],      "chase": [20, 35],     "special": [34, 21, 70],      "support": [28, 43, 39],      "passive": [68]},
    "Flying":   {"standard": [16, 64],      "chase": [17, 31],     "special": [19, 65, 25],      "support": [18, 43, 45],      "passive": [81]},
    "Psychic":  {"standard": [33, 1],       "chase": [60, 49],     "special": [36, 63],          "support": [47, 48, 50],      "passive": [73]},
    "Bug":      {"standard": [64, 33],      "chase": [41, 42, 20], "special": [34, 21],          "support": [81, 28, 45],      "passive": [73]},
    "Rock":     {"standard": [29, 23],      "chase": [31, 20],     "special": [34, 36, 70],      "support": [28, 43],          "passive": [68]},
    "Ghost":    {"standard": [33, 44],      "chase": [49, 44],     "special": [37, 12],          "support": [47, 48, 50],      "passive": [73]},
    "Dragon":   {"standard": [29, 17],      "chase": [9, 7],       "special": [38, 63],          "support": [14, 43],          "passive": [71]},
    "Dark":     {"standard": [33, 44],      "chase": [35, 49],     "special": [34, 38],          "support": [39, 46, 50],      "passive": [68]},
    "Steel":    {"standard": [23, 29],      "chase": [20, 9],      "special": [34, 70],          "support": [43, 28],          "passive": [68]},
    "Fairy":    {"standard": [1, 33],       "chase": [3, 60],      "special": [34, 21],          "support": [47, 45, 74],      "passive": [73]},
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def infer_slot_type(move: Any) -> str:
    """Determine the appropriate MoveSlotType value for a move using heuristics."""
    if move.is_charge_move:
        return "special"
    if move.power == 0 and move.accuracy <= 30:
        return "special"  # OHKO moves
    if move.power == 0 and move.pk in PASSIVE_MOVE_PKS:
        return "passive"
    if move.power > 0 and move.pk in PASSIVE_MOVE_PKS:
        return "passive"
    if move.power == 0:
        return "support"
    if move.always_first or move.priority > 0:
        return "chase"
    if move.power >= 80:
        return "special"
    if move.power <= 25:
        return "chase"
    if move.power >= 60:
        return "chase"
    return "standard"


def determine_role(species: Any) -> str:
    """Assign a TacticalRole value based on base stats."""
    speed = species.base_speed
    atk = species.base_attack
    spa = species.base_sp_attack
    total_def = species.base_hp + species.base_defense + species.base_sp_defense
    total_off = atk + spa

    if speed >= 110 and total_off >= 150:
        return "assassin"
    if total_off >= 220:
        return "bruiser" if atk >= spa else "dps"
    if total_def >= 260 and total_off < 200:
        return "tank"
    if total_off < 170:
        return "support" if species.base_hp >= 90 else "control"
    return "dps"


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
