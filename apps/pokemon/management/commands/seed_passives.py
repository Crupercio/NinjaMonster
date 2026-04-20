"""
Management command: seed_passives

Creates:
  - 18 Synergy Moves (passive_1 slot, one per type)
  - 20 HeldEffect objects (item passive system)
  - 20 Display Moves for passive_2 slot (one per held effect)

Safe to re-run: uses get_or_create throughout.

Usage:
    python manage.py seed_passives
    python manage.py seed_passives --dry-run
"""
from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 18 Synergy Moves — passive_1 slot, one per type
# ---------------------------------------------------------------------------
SYNERGY_MOVES: list[tuple[str, str, str]] = [
    # (name, type_name, description)
    ("Burning Will",     "Fire",     "If 2+ Fire allies on team: Fire moves deal +15% damage. Each additional Fire type stacks +5%."),
    ("Tidal Flow",       "Water",    "If 2+ Water allies on team: Restore 3% HP at round start. +1% per extra Water ally."),
    ("Root Network",     "Grass",    "If 2+ Grass allies on team: CC durations on allies reduced by 1 round."),
    ("Discharge Field",  "Electric", "If 2+ Electric allies on team: Paralyzed enemies lose an additional action per round."),
    ("Psi Resonance",    "Psychic",  "If 2+ Psychic allies on team: Confused enemies deal +10% self-damage."),
    ("Permafrost Pact",  "Ice",      "If 2+ Ice allies on team: Frozen status lasts 2 extra rounds."),
    ("Iron Fist Accord", "Fighting", "If 2+ Fighting allies on team: Flinched enemies are also paralyzed."),
    ("Toxic Network",    "Poison",   "If 2+ Poison allies on team: Poison damage ticks deal +3% extra HP per round."),
    ("Tectonic Bond",    "Ground",   "If 2+ Ground allies on team: Immobile enemies cannot use mystery moves."),
    ("Stone Wall Pact",  "Rock",     "If 2+ Rock allies on team: All allies gain +10% Defense."),
    ("Spirit Link",      "Ghost",    "If 2+ Ghost allies on team: Confused enemies also receive Nightmare."),
    ("Dragon's Pride",   "Dragon",   "If 2+ Dragon allies on team: Dragon-type moves deal +20% damage."),
    ("Shadow Pact",      "Dark",     "If 2+ Dark allies on team: Taunted enemies deal -15% damage."),
    ("Swarm Mind",       "Bug",      "If 2+ Bug allies on team: Blinded enemies have +20% miss chance."),
    ("Versatile Core",   "Normal",   "If 3+ Normal allies on team: All Normal-type allies gain +5% speed."),
    ("Wind Riders",      "Flying",   "If 2+ Flying allies on team: All moves gain +5% accuracy."),
    ("Fortified Line",   "Steel",    "If 2+ Steel allies on team: Weakened enemies take +15% damage."),
    ("Enchanted Circle", "Fairy",    "If 2+ Fairy allies on team: Infatuated enemies cannot use chase moves."),
]

# ---------------------------------------------------------------------------
# 20 HeldEffect objects
# ---------------------------------------------------------------------------
HELD_EFFECTS: list[tuple[str, str, str, dict, float, int]] = [
    # (name, description, trigger_condition, effect_data, activation_chance, max_activations)
    ("Oran Berry",        "Heals 10% max HP when HP drops below 40%.",                          "on_hit",    {"heal_fraction": 0.10, "hp_threshold": 0.40}, 1.0, 1),
    ("Sitrus Berry",      "Heals 25% max HP when HP drops below 50%.",                          "on_hit",    {"heal_fraction": 0.25, "hp_threshold": 0.50}, 1.0, 1),
    ("Leftovers",         "Restores 3% HP at the start of each round.",                         "passive",   {"heal_fraction": 0.03}, 1.0, 0),
    ("Shell Bell",        "Heals 15% of damage dealt after each attack.",                       "on_hit",    {"heal_on_damage_fraction": 0.15}, 1.0, 0),
    ("Rocky Helmet",      "Reflects 15% of damage taken back to the attacker.",                 "on_hit",    {"damage_reflect": 0.15}, 1.0, 0),
    ("Focus Sash",        "Survive a KO hit with 1 HP remaining. Activates once per battle.",   "on_hit",    {"focus_sash": True}, 1.0, 1),
    ("Life Orb",          "+30% damage dealt. Lose 10% HP after each attack.",                  "on_hit",    {"damage_boost": 0.30, "recoil_fraction": 0.10}, 1.0, 0),
    ("Scope Lens",        "Chase moves that crit deal +15% bonus damage.",                      "on_hit",    {"crit_chase_boost": 0.15}, 1.0, 0),
    ("Weakness Policy",   "When hit by a super-effective move: +50% offense for 2 rounds.",     "on_hit",    {"weakness_policy": True, "boost_duration": 2}, 1.0, 1),
    ("Eviolite",          "If not final evolution: +50% Defense and Sp. Defense.",               "passive",   {"eviolite": True}, 1.0, 0),
    ("Assault Vest",      "+50% Special Defense. Cannot use passive/support moves.",             "passive",   {"sp_def_boost": 0.50}, 1.0, 0),
    ("Choice Band",       "+50% damage on standard attacks. Locked to one move per round.",     "passive",   {"std_damage_boost": 0.50}, 1.0, 0),
    ("Sage Mode Scroll",  "While HP > 70%: all damage dealt +25%.",                             "passive",   {"sage_mode": True, "boost": 0.25, "hp_threshold": 0.70}, 1.0, 0),
    ("Bijuu Cloak",       "When HP drops below 40%: +40% attack, immune to CC for 2 rounds.",  "on_hit",    {"bijuu_cloak": True, "duration": 2}, 1.0, 1),
    ("Susanoo Shard",     "Reduces all incoming damage by 15%.",                                "passive",   {"damage_reduction": 0.15}, 1.0, 0),
    ("Chakra Pill",       "When afflicted by CC: cleanse all status and heal 20% HP. Once.",   "on_status", {"status_cleanse": True, "heal_fraction": 0.20}, 1.0, 1),
    ("Shadow Clone Tag",  "On faint: revive with 20% HP. Once per battle.",                    "on_faint",  {"revive_hp_fraction": 0.20}, 1.0, 1),
    ("Cursed Seal",       "50% chance to reflect any applied status back to the attacker.",     "on_status", {"status_reflect": True}, 0.50, 0),
    ("Eight Gates Seal",  "+20% attack each round. Lose 5% HP per round. No cap.",              "passive",   {"atk_boost_per_round": 0.20, "hp_cost_fraction": 0.05}, 1.0, 0),
    ("Tailed Beast Chakra", "On faint: all surviving allies heal 15% HP.",                      "on_faint",  {"team_heal_fraction": 0.15}, 1.0, 1),
]


class Command(BaseCommand):
    help = (
        "Seed synergy moves (passive_1), held effects, and passive_2 display "
        "moves into the database. Safe to re-run."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Show what would be created without writing to the database.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from apps.pokemon.models import HeldEffect, Move, PokemonType

        dry_run: bool = options["dry_run"]

        self.stdout.write(self.style.MIGRATE_HEADING("=== seed_passives ==="))
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be written."))

        with transaction.atomic():
            synergy_created = 0
            synergy_updated = 0
            held_created = 0
            held_updated = 0
            passive2_created = 0
            passive2_updated = 0

            # ------------------------------------------------------------------
            # Step 1 — Synergy Moves (passive_1 slot)
            # ------------------------------------------------------------------
            self.stdout.write(self.style.MIGRATE_LABEL("Step 1: Synergy Moves (passive_1) …"))

            for move_name, type_name, description in SYNERGY_MOVES:
                try:
                    ptype = PokemonType.objects.get(name=type_name)
                except PokemonType.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  Type '{type_name}' not found — skipping {move_name}."
                        )
                    )
                    continue

                if not dry_run:
                    obj, created = Move.objects.get_or_create(
                        name=move_name,
                        defaults={
                            "move_type": ptype,
                            "slot_type": "passive_1",
                            "power": 0,
                            "accuracy": 100,
                            "description": description,
                            "support_flag": True,
                        },
                    )
                    if not created:
                        obj.description = description
                        obj.save(update_fields=["description"])
                        synergy_updated += 1
                    else:
                        synergy_created += 1
                else:
                    exists = Move.objects.filter(name=move_name).exists()
                    self.stdout.write(
                        f"  [dry-run] {'Would update' if exists else 'Would create'}: {move_name} ({type_name})"
                    )
                    if not exists:
                        synergy_created += 1
                    else:
                        synergy_updated += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"  Synergy moves: {synergy_created} created, {synergy_updated} updated."
                )
            )

            # ------------------------------------------------------------------
            # Step 2 — HeldEffect objects
            # ------------------------------------------------------------------
            self.stdout.write(self.style.MIGRATE_LABEL("Step 2: HeldEffect objects …"))

            for (
                name, description, trigger_condition, effect_data,
                activation_chance, max_activations,
            ) in HELD_EFFECTS:
                if not dry_run:
                    obj, created = HeldEffect.objects.get_or_create(
                        name=name,
                        defaults={
                            "description": description,
                            "trigger_condition": trigger_condition,
                            "effect_data": effect_data,
                            "activation_chance": activation_chance,
                            "max_activations": max_activations,
                        },
                    )
                    if not created:
                        obj.description = description
                        obj.trigger_condition = trigger_condition
                        obj.effect_data = effect_data
                        obj.activation_chance = activation_chance
                        obj.max_activations = max_activations
                        obj.save(update_fields=[
                            "description", "trigger_condition", "effect_data",
                            "activation_chance", "max_activations",
                        ])
                        held_updated += 1
                    else:
                        held_created += 1
                else:
                    exists = HeldEffect.objects.filter(name=name).exists()
                    self.stdout.write(
                        f"  [dry-run] {'Would update' if exists else 'Would create'}: {name}"
                    )
                    if not exists:
                        held_created += 1
                    else:
                        held_updated += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"  HeldEffects: {held_created} created, {held_updated} updated."
                )
            )

            # ------------------------------------------------------------------
            # Step 3 — passive_2 display Moves (one per held effect)
            # ------------------------------------------------------------------
            self.stdout.write(self.style.MIGRATE_LABEL("Step 3: passive_2 display Moves …"))

            # Use Normal type as the generic type for passive_2 display moves
            try:
                normal_type = PokemonType.objects.get(name="Normal")
            except PokemonType.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        "  Normal type not found — cannot create passive_2 display moves."
                    )
                )
                if dry_run:
                    transaction.set_rollback(True)
                return

            for (
                name, description, trigger_condition, effect_data,
                activation_chance, max_activations,
            ) in HELD_EFFECTS:
                if not dry_run:
                    obj, created = Move.objects.get_or_create(
                        name=name,
                        slot_type="passive_2",
                        defaults={
                            "move_type": normal_type,
                            "power": 0,
                            "accuracy": 100,
                            "description": description,
                            "support_flag": True,
                        },
                    )
                    if not created:
                        obj.description = description
                        obj.save(update_fields=["description"])
                        passive2_updated += 1
                    else:
                        passive2_created += 1
                else:
                    exists = Move.objects.filter(name=name, slot_type="passive_2").exists()
                    self.stdout.write(
                        f"  [dry-run] {'Would update' if exists else 'Would create'} passive_2: {name}"
                    )
                    if not exists:
                        passive2_created += 1
                    else:
                        passive2_updated += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"  passive_2 moves: {passive2_created} created, {passive2_updated} updated."
                )
            )

            # ------------------------------------------------------------------
            # Summary
            # ------------------------------------------------------------------
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("=== Summary ==="))
            self.stdout.write(f"  Synergy moves (passive_1) : {synergy_created} created, {synergy_updated} updated")
            self.stdout.write(f"  HeldEffects               : {held_created} created, {held_updated} updated")
            self.stdout.write(f"  Display moves (passive_2) : {passive2_created} created, {passive2_updated} updated")

            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("Dry run complete — database unchanged."))
