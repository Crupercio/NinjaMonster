"""
Management command: apply_universal_roles

Assigns TacticalRole to every Pokemon not already covered by apply_gen1_roles
and generates role-aware SpeciesMovePool entries for them.

Design
------
Roles are inferred from three signals, in priority order:

  1. Manual overrides  — ROLE_OVERRIDES dict (pokedex_number -> role).
     Add high-profile Pokemon here when the auto-rule gets them wrong.

  2. Type + evolution position rules
     - Evolution position (solo / first / mid / final) shapes the role.
     - Type pairings bias toward known archetypes.

  3. Base stats fallback
     - High offense + speed  -> combo
     - High offense          -> burst
     - High total defense    -> tank
     - High HP + low offense -> support
     - Otherwise             -> control

Run AFTER seed_pokeapi so all Gen 2-8 Pokemon exist in the DB.

Usage:
    python manage.py apply_universal_roles
    python manage.py apply_universal_roles --gen 2          # Johto only
    python manage.py apply_universal_roles --gen 2 --gen 3  # multi-gen
    python manage.py apply_universal_roles --dry-run
    python manage.py apply_universal_roles --clear          # wipe pools first
    python manage.py apply_universal_roles --roles-only
    python manage.py apply_universal_roles --pools-only
"""
from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Generation dex ranges
# ---------------------------------------------------------------------------
GEN_RANGES: dict[int, tuple[int, int]] = {
    1: (1, 151),
    2: (152, 251),
    3: (252, 386),
    4: (387, 493),
    5: (494, 649),
    6: (650, 721),
    7: (722, 809),
    8: (810, 905),
    9: (906, 1010),
}

# ---------------------------------------------------------------------------
# Manual role overrides  (pokedex_number -> role slug)
# Add entries here for any Pokemon the auto-rule assigns incorrectly.
# ---------------------------------------------------------------------------
ROLE_OVERRIDES: dict[int, str] = {
    # Gen 2 notable overrides
    196: "combo",    # Espeon    — Psychic glass-cannon combo
    197: "tank",     # Umbreon   — Dark wall tank
    212: "burst",    # Scizor    — Bullet Punch burst striker
    248: "tank",     # Tyranitar — Rock/Dark fortress
    249: "support",  # Lugia     — Aero Blast legendary support
    250: "burst",    # Ho-Oh     — Sacred Fire apex burst
    # Gen 3
    282: "combo",    # Gardevoir — Psychic/Fairy combo
    330: "burst",    # Flygon    — Dragon/Ground striker
    350: "support",  # Milotic   — Water defensive support
    373: "burst",    # Salamence — Dragon/Flying apex burst
    376: "tank",     # Metagross — Steel/Psychic fortress
    377: "tank",     # Regirock  — Rock wall
    378: "tank",     # Regice    — Ice wall
    379: "tank",     # Registeel — Steel wall
    380: "support",  # Latias    — Dragon support
    381: "burst",    # Latios    — Dragon burst
    382: "tank",     # Kyogre    — Water legendary tank
    383: "burst",    # Groudon   — Ground legendary burst
    384: "burst",    # Rayquaza  — Dragon apex burst
    # Gen 4
    448: "combo",    # Lucario   — Fighting/Steel combo
    445: "burst",    # Garchomp  — Dragon/Ground burst
    487: "control",  # Giratina  — Ghost/Dragon control
    488: "support",  # Cresselia — Psychic support
    # Gen 5
    609: "combo",    # Chandelure — Ghost/Fire combo
    635: "burst",    # Hydreigon — Dark/Dragon burst
    643: "burst",    # Reshiram  — Dragon/Fire burst
    644: "burst",    # Zekrom    — Dragon/Electric burst
    646: "tank",     # Kyurem    — Dragon/Ice tank
    # Gen 6
    681: "combo",    # Aegislash — Steel/Ghost combo
    700: "support",  # Sylveon   — Fairy support
    716: "support",  # Xerneas   — Fairy legendary support
    717: "control",  # Yveltal   — Dark/Flying control
    # Gen 7
    745: "control",  # Lycanroc  — Rock control
    748: "burst",    # Toxapex wait — actually defensive... 748 is Toxapex
    785: "burst",    # Tapu Koko — Electric/Fairy burst
    786: "support",  # Tapu Lele — Psychic/Fairy support
    787: "tank",     # Tapu Bulu — Grass/Fairy tank
    788: "support",  # Tapu Fini — Water/Fairy support
    800: "combo",    # Necrozma  — Psychic combo
    # Gen 8
    888: "burst",    # Zacian    — Fairy burst
    889: "tank",     # Zamazenta — Fighting tank
    890: "burst",    # Eternatus — Poison/Dragon burst
}

# ---------------------------------------------------------------------------
# Type -> role bias per evolution position
# Evolution positions: "solo" (no evolutions), "first", "mid", "final"
# ---------------------------------------------------------------------------
_TYPE_ROLE_BIAS: dict[str, dict[str, str]] = {
    "Fire":     {"solo": "burst",   "first": "burst",   "mid": "combo",   "final": "burst"},
    "Water":    {"solo": "tank",    "first": "control", "mid": "support", "final": "tank"},
    "Grass":    {"solo": "control", "first": "burst",   "mid": "control", "final": "tank"},
    "Electric": {"solo": "burst",   "first": "combo",   "mid": "combo",   "final": "burst"},
    "Ice":      {"solo": "control", "first": "control", "mid": "tank",    "final": "tank"},
    "Fighting": {"solo": "burst",   "first": "burst",   "mid": "burst",   "final": "tank"},
    "Poison":   {"solo": "control", "first": "control", "mid": "control", "final": "tank"},
    "Ground":   {"solo": "burst",   "first": "burst",   "mid": "burst",   "final": "tank"},
    "Rock":     {"solo": "tank",    "first": "burst",   "mid": "burst",   "final": "tank"},
    "Ghost":    {"solo": "combo",   "first": "control", "mid": "combo",   "final": "combo"},
    "Psychic":  {"solo": "combo",   "first": "control", "mid": "control", "final": "combo"},
    "Bug":      {"solo": "control", "first": "control", "mid": "burst",   "final": "burst"},
    "Dragon":   {"solo": "burst",   "first": "control", "mid": "combo",   "final": "burst"},
    "Dark":     {"solo": "combo",   "first": "control", "mid": "combo",   "final": "combo"},
    "Normal":   {"solo": "combo",   "first": "control", "mid": "burst",   "final": "burst"},
    "Flying":   {"solo": "burst",   "first": "control", "mid": "combo",   "final": "burst"},
    "Steel":    {"solo": "tank",    "first": "tank",    "mid": "tank",    "final": "tank"},
    "Fairy":    {"solo": "support", "first": "control", "mid": "support", "final": "support"},
}

# Secondary type adjustments — if primary gives one role but secondary strongly
# suggests another, blend toward the secondary's archetype.
_SECONDARY_TYPE_OVERRIDE: dict[str, dict[str, str]] = {
    # Steel secondary always pulls toward tank (Steel is the ultimate armor type)
    "Steel":  {"burst": "tank", "combo": "tank", "control": "tank"},
    # Fairy secondary pulls support/solo roles toward support
    "Fairy":  {"control": "support", "burst": "combo"},
    # Ghost secondary makes controllers into combos
    "Ghost":  {"control": "combo"},
    # Psychic secondary softens pure burst into combo
    "Psychic": {"burst": "combo"},
}


def _infer_evo_position(species: Any, all_dex: set[int]) -> str:
    """
    Estimate evolution position without needing the PokeAPI evolution chain.
    Uses pokedex_number proximity heuristic:
    - No adjacent neighbours in ±3 range with same primary type -> solo
    - Lowest in a contiguous type cluster                        -> first
    - Highest in a contiguous type cluster                       -> final
    - Otherwise                                                  -> mid
    """
    if not species.pokedex_number:
        return "solo"

    dex = species.pokedex_number
    type_id = species.primary_type_id

    # Look at ±3 neighbours for same primary type
    nearby = [
        n for n in range(max(1, dex - 3), dex + 4)
        if n != dex and n in all_dex
    ]
    # We need the type_id of neighbours — use a pre-built map passed in
    # For now use the simpler heuristic: position within consecutive run
    has_prev = (dex - 1) in all_dex or (dex - 2) in all_dex
    has_next = (dex + 1) in all_dex or (dex + 2) in all_dex

    if not has_prev and not has_next:
        return "solo"
    if not has_prev:
        return "first"
    if not has_next:
        return "final"
    return "mid"


def _stat_role(species: Any) -> str:
    """Fallback role based on base stats."""
    spd = species.base_initiative
    atk = species.base_attack
    spa = species.base_ninjutsu
    hp  = species.base_hp
    df  = species.base_defense
    spd_def = species.base_sp_defense
    total_off = atk + spa
    total_def = hp + df + spd_def

    if spd >= 100 and total_off >= 150:
        return "combo"
    if total_off >= 220:
        return "burst"
    if total_def >= 270 and total_off < 190:
        return "tank"
    if hp >= 100 and total_off < 160:
        return "support"
    if total_off < 160:
        return "control"
    return "burst"


def infer_role(species: Any, all_dex: set[int]) -> str:
    """
    Full role inference pipeline:
      1. Manual override
      2. Type + evo-position rule
      3. Secondary type adjustment
      4. Stat fallback
    """
    dex = species.pokedex_number

    # 1 — Manual override
    if dex in ROLE_OVERRIDES:
        return ROLE_OVERRIDES[dex]

    # 2 — Type + evo-position
    evo_pos = _infer_evo_position(species, all_dex)
    primary_name = species.primary_type.name if species.primary_type else "Normal"
    role = _TYPE_ROLE_BIAS.get(primary_name, {}).get(evo_pos, _stat_role(species))

    # 3 — Secondary type adjustment
    if species.secondary_type:
        sec_name = species.secondary_type.name
        overrides = _SECONDARY_TYPE_OVERRIDE.get(sec_name, {})
        role = overrides.get(role, role)

    return role


# ---------------------------------------------------------------------------
# Move scoring — same as apply_gen1_roles
# ---------------------------------------------------------------------------
_CC_STATUSES: frozenset[str] = frozenset({
    "paralyzed", "asleep", "confused", "frozen", "bound",
    "flinched", "yawning", "taunted", "tormented",
})
_BURST_STATUSES: frozenset[str] = frozenset({
    "burned", "poisoned", "badly_poisoned", "flinched", "seeded",
})


def _score_move(move: Any, role: str, slot: str) -> int:
    import re
    score = 0
    if re.search(r" \d+$", move.name):
        score -= 20  # deprioritise Z-move / variant duplicates

    status: str | None = (
        move.applies_status.name if move.applies_status_id else None
    )

    if role == "burst":
        if slot == "standard" and status in _BURST_STATUSES:
            score += 10
        if slot in ("mystery", "chase") and move.power >= 100:
            score += 12
        elif slot in ("mystery", "chase") and move.power >= 75:
            score += 6
        score += move.power // 10

    elif role == "control":
        if status in _CC_STATUSES:
            score += 12
        if slot == "standard" and status in _CC_STATUSES:
            score += 8
        if slot == "chase" and status in _CC_STATUSES:
            score += 5
        score += move.power // 20

    elif role == "tank":
        if move.support_flag:
            score += 15
        if slot == "passive_1" and move.power == 0:
            score += 8
        if slot in ("standard", "mystery") and move.power >= 60:
            score += 5
        if status and status not in _CC_STATUSES:
            score += 3
        score += move.power // 20

    elif role == "support":
        if move.support_flag:
            score += 20
        if slot == "passive_1" and move.power == 0:
            score += 8
        if status and status not in _CC_STATUSES and status not in _BURST_STATUSES:
            score += 8
        score -= move.power // 15

    elif role == "combo":
        if move.always_first or move.priority > 0:
            score += 8
        if move.combo_starter:
            score += 10
        if move.combo_trigger:
            score += 10
        if move.combo_role:
            score += 5
        score += move.power // 12

    return score


def _pick_moves(
    slot: str,
    role: str,
    primary_type_id: int,
    secondary_type_id: int | None,
    normal_type_id: int,
    moves_by_slot: dict[str, list[Any]],
    count: int = 2,
    exclude_pks: set[int] | None = None,
) -> list[int]:
    exclude = exclude_pks or set()
    candidates = [m for m in moves_by_slot.get(slot, []) if m.pk not in exclude]

    def _top(pool: list[Any], n: int) -> list[int]:
        ranked = sorted(
            pool, key=lambda m: _score_move(m, role, slot), reverse=True
        )
        return [m.pk for m in ranked[:n]]

    result = _top(
        [m for m in candidates if m.move_type_id == primary_type_id],
        count,
    )
    if len(result) < count and secondary_type_id:
        extra = _top(
            [m for m in candidates
             if m.move_type_id == secondary_type_id and m.pk not in result],
            count - len(result),
        )
        result.extend(extra)
    if len(result) < count:
        extra = _top(
            [m for m in candidates
             if m.move_type_id == normal_type_id and m.pk not in result],
            count - len(result),
        )
        result.extend(extra)
    if len(result) < count:
        extra = _top(
            [m for m in candidates if m.pk not in result],
            count - len(result),
        )
        result.extend(extra)
    return result[:count]


# ---------------------------------------------------------------------------
# Management command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = (
        "Assign TacticalRole and generate SpeciesMovePool entries for all "
        "Pokemon not covered by apply_gen1_roles. Run after seed_pokeapi."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--gen",
            type=int,
            action="append",
            dest="gens",
            help="Generation(s) to process (default: all above Gen 1). Repeatable.",
        )
        parser.add_argument("--dry-run", action="store_true", default=False)
        parser.add_argument("--roles-only", action="store_true", default=False)
        parser.add_argument("--pools-only", action="store_true", default=False)
        parser.add_argument(
            "--clear",
            action="store_true",
            default=False,
            help="Wipe existing SpeciesMovePool entries for targeted species first.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from apps.pokemon.models import Move, Pokemon, SpeciesMovePool

        dry_run: bool = options["dry_run"]
        roles_only: bool = options["roles_only"]
        pools_only: bool = options["pools_only"]
        clear: bool = options["clear"]
        target_gens: list[int] = options["gens"] or list(range(2, 10))

        self.stdout.write(self.style.MIGRATE_HEADING("=== apply_universal_roles ==="))
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be written."))

        # Build dex range filter from target generations
        dex_filter: list[tuple[int, int]] = [
            GEN_RANGES[g] for g in target_gens if g in GEN_RANGES
        ]
        if not dex_filter:
            self.stdout.write(self.style.ERROR("No valid generations specified."))
            return

        from django.db.models import Q
        q = Q()
        for lo, hi in dex_filter:
            q |= Q(pokedex_number__gte=lo, pokedex_number__lte=hi)

        with transaction.atomic():
            species_qs = (
                Pokemon.objects.filter(q)
                .select_related("primary_type", "secondary_type")
                .order_by("pokedex_number")
            )
            all_species = list(species_qs)

            if not all_species:
                self.stdout.write(
                    self.style.WARNING(
                        f"No Pokemon found for generations {target_gens}. "
                        "Run seed_pokeapi first."
                    )
                )
                return

            self.stdout.write(
                f"Processing {len(all_species)} Pokemon "
                f"across generations {target_gens}."
            )

            # Pre-build the set of all pokedex numbers for evo-position detection
            all_dex: set[int] = set(
                Pokemon.objects.exclude(pokedex_number__isnull=True)
                .values_list("pokedex_number", flat=True)
            )

            # ------------------------------------------------------------------
            # Step 1 — Assign primary_role
            # ------------------------------------------------------------------
            if not pools_only:
                self.stdout.write(
                    self.style.MIGRATE_LABEL("Step 1: Assigning primary_role …")
                )
                to_update: list[Pokemon] = []
                for sp in all_species:
                    new_role = infer_role(sp, all_dex)
                    if sp.primary_role != new_role:
                        sp.primary_role = new_role
                        to_update.append(sp)

                if not dry_run:
                    Pokemon.objects.bulk_update(to_update, ["primary_role"])
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  Updated primary_role on {len(to_update)} species."
                        )
                    )
                else:
                    self.stdout.write(
                        f"  [dry-run] Would update {len(to_update)} species."
                    )

            if roles_only:
                if dry_run:
                    transaction.set_rollback(True)
                return

            # ------------------------------------------------------------------
            # Step 2 — Generate SpeciesMovePool entries
            # ------------------------------------------------------------------
            self.stdout.write(
                self.style.MIGRATE_LABEL("Step 2: Generating move pools …")
            )

            if clear and not dry_run:
                pks = [s.pk for s in all_species]
                deleted, _ = SpeciesMovePool.objects.filter(
                    species_id__in=pks
                ).delete()
                self.stdout.write(f"  Cleared {deleted} existing entries.")
            elif clear and dry_run:
                pks = [s.pk for s in all_species]
                n = SpeciesMovePool.objects.filter(species_id__in=pks).count()
                self.stdout.write(f"  [dry-run] Would clear {n} existing entries.")

            all_moves = list(
                Move.objects.select_related(
                    "move_type", "applies_status"
                ).all()
            )
            moves_by_slot: dict[str, list[Any]] = {}
            for move in all_moves:
                moves_by_slot.setdefault(move.slot_type, []).append(move)

            normal_type_id: int = next(
                m.move_type_id for m in all_moves if m.move_type.name == "Normal"
            )

            pks = [s.pk for s in all_species]
            existing_pairs: set[tuple[int, int]] = set(
                SpeciesMovePool.objects.filter(species_id__in=pks)
                .values_list("species_id", "move_id")
            ) if not clear else set()

            TYPE_SYNERGY_MOVE: dict[str, str] = {
                "Fire": "Burning Will", "Water": "Tidal Flow", "Grass": "Root Network",
                "Electric": "Discharge Field", "Psychic": "Psi Resonance", "Ice": "Permafrost Pact",
                "Fighting": "Iron Fist Accord", "Poison": "Toxic Network", "Ground": "Tectonic Bond",
                "Rock": "Stone Wall Pact", "Ghost": "Spirit Link", "Dragon": "Dragon's Pride",
                "Dark": "Shadow Pact", "Bug": "Swarm Mind", "Normal": "Versatile Core",
                "Flying": "Wind Riders", "Steel": "Fortified Line", "Fairy": "Enchanted Circle",
            }
            ROLE_ITEM_PASSIVE: dict[str, str] = {
                "burst":   "Life Orb",
                "combo":   "Scope Lens",
                "tank":    "Rocky Helmet",
                "support": "Shell Bell",
                "control": "Susanoo Shard",
            }

            synergy_pk_by_name: dict[str, int] = {
                m.name: m.pk
                for m in Move.objects.filter(
                    slot_type="passive_1",
                    name__in=list(TYPE_SYNERGY_MOVE.values()),
                )
            }
            passive2_pk_by_name: dict[str, int] = {
                m.name: m.pk
                for m in Move.objects.filter(
                    slot_type="passive_2",
                    name__in=list(ROLE_ITEM_PASSIVE.values()),
                )
            }

            entries_to_create: list[SpeciesMovePool] = []
            created = 0
            skipped = 0
            slots_config = [
                ("standard", 2),
                ("chase", 2),
                ("mystery", 2),
            ]

            for sp in all_species:
                role = infer_role(sp, all_dex) if pools_only else sp.primary_role
                used_pks: set[int] = set()

                for slot, count in slots_config:
                    chosen = _pick_moves(
                        slot=slot,
                        role=role,
                        primary_type_id=sp.primary_type_id,
                        secondary_type_id=sp.secondary_type_id,
                        normal_type_id=normal_type_id,
                        moves_by_slot=moves_by_slot,
                        count=count,
                        exclude_pks=used_pks,
                    )
                    for pk in chosen:
                        if (sp.pk, pk) in existing_pairs:
                            skipped += 1
                            continue
                        entries_to_create.append(
                            SpeciesMovePool(
                                species_id=sp.pk,
                                move_id=pk,
                                slot_type=slot,
                                role_tag=role,
                            )
                        )
                        existing_pairs.add((sp.pk, pk))
                        used_pks.add(pk)
                        created += 1

                # Step 3a — passive_1 synergy move (type-matched)
                primary_type_name = sp.primary_type.name if sp.primary_type else ""
                synergy_move_name = TYPE_SYNERGY_MOVE.get(primary_type_name)
                if synergy_move_name:
                    synergy_pk = synergy_pk_by_name.get(synergy_move_name)
                    if synergy_pk and (sp.pk, synergy_pk) not in existing_pairs:
                        entries_to_create.append(
                            SpeciesMovePool(
                                species_id=sp.pk,
                                move_id=synergy_pk,
                                slot_type="passive_1",
                                role_tag=role,
                            )
                        )
                        existing_pairs.add((sp.pk, synergy_pk))
                        used_pks.add(synergy_pk)
                        created += 1

                # Step 3b — passive_2 display move (role-matched item)
                item_move_name = ROLE_ITEM_PASSIVE.get(role)
                if item_move_name:
                    item_pk = passive2_pk_by_name.get(item_move_name)
                    if item_pk and (sp.pk, item_pk) not in existing_pairs:
                        entries_to_create.append(
                            SpeciesMovePool(
                                species_id=sp.pk,
                                move_id=item_pk,
                                slot_type="passive_2",
                                role_tag=role,
                            )
                        )
                        existing_pairs.add((sp.pk, item_pk))
                        used_pks.add(item_pk)
                        created += 1

            if not dry_run:
                SpeciesMovePool.objects.bulk_create(
                    entries_to_create, batch_size=500
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Created {created} pool entries "
                        f"({skipped} already existed)."
                    )
                )
            else:
                self.stdout.write(
                    f"  [dry-run] Would create {created} entries "
                    f"({skipped} already exist)."
                )

            if dry_run:
                transaction.set_rollback(True)

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS("apply_universal_roles complete.")
            )
        else:
            self.stdout.write(self.style.WARNING("Dry run complete."))
