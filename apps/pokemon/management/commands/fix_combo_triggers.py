"""
Management command: fix_combo_triggers

Assigns trigger_status to chase moves so combo chains can actually fire.

Previously, standard moves correctly applied statuses (Ember -> BURNED,
Thunder Shock -> PARALYZED, Acid -> POISONED, etc.) but NO chase move had
trigger_status set, so _find_combo_candidates always returned an empty list
and combos never fired.

This command wires the two halves together:
  Standard move applies STATUS -> enemy has STATUS ->
  Chase move with trigger_status=STATUS fires -> COMBO x2!

Usage:
    python manage.py fix_combo_triggers
    python manage.py fix_combo_triggers --dry-run
"""
from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

logger = logging.getLogger(__name__)

# -- Trigger assignments ------------------------------------------------------
# Maps Move.pk -> StatusEffect.name (trigger_status to assign)
#
# Design rationale:
#   Fire Punch (7)    -> BURNED   : Ember (standard) applies BURNED -> Fire Punch chases
#   Ice Punch (8)     -> FROZEN   : Ice Beam/Blizzard (mystery) applies FROZEN -> Ice Punch chases
#   Thunder Punch (9) -> PARALYZED: Thunder Shock (standard) applies PARALYZED -> Thunder Punch chases
#   Bind (20)         -> POISONED : Acid/Poison Sting (standard) apply POISONED -> Bind chases
#   Wrap (35)         -> BOUND    : Fire Spin (standard) applies BOUND -> Wrap chases
#   Poison Sting (40) -> POISONED : Self-chain on Poison types (two poisoners on team)
#   Bite (44)         -> PARALYZED: Cross-type chain — Thunder Shock stuns, Bite follows up
#   Psybeam (60)      -> CONFUSED : Supersonic/Confuse Ray apply CONFUSED -> Psybeam chases
#   Bubble Beam (61)  -> POISONED : Poison types often support Water allies
#   Aurora Beam (62)  -> FROZEN   : Ice types chain frozen enemies
#   Fire Spin (83)    -> BURNED   : Ember primes, Fire Spin follows on Fire-heavy teams
#   Double Slap (3)   -> PARALYZED: Harass paralyzed targets
#   Low Kick (67)     -> BOUND    : Kick a trapped/bound foe
#   Sonic Boom (49)   -> CONFUSED : Psychic/Ghost follow-up on confused targets
#   Mega Drain (72)   -> POISONED : Drain a poisoned foe for bonus healing synergy

TRIGGER_ASSIGNMENTS: dict[int, str] = {
    3:  "paralyzed",   # Double Slap
    7:  "burned",      # Fire Punch
    8:  "frozen",      # Ice Punch
    9:  "paralyzed",   # Thunder Punch
    20: "poisoned",    # Bind
    35: "bound",       # Wrap
    40: "poisoned",    # Poison Sting
    44: "paralyzed",   # Bite
    49: "confused",    # Sonic Boom
    60: "confused",    # Psybeam
    61: "poisoned",    # Bubble Beam
    62: "frozen",      # Aurora Beam
    67: "bound",       # Low Kick
    72: "poisoned",    # Mega Drain
    83: "burned",      # Fire Spin
}

# Also ensure these standard moves have applies_status set
# (most are already set in the DB, this is a safety net)
STANDARD_STATUS_ASSIGNMENTS: dict[int, str] = {
    52: "burned",      # Ember
    84: "paralyzed",   # Thunder Shock
    40: "poisoned",    # Poison Sting (also chase but some pools use it as standard)
    51: "poisoned",    # Acid
    83: "bound",       # Fire Spin
    29: "flinched",    # Headbutt
    23: "flinched",    # Stomp
    47: "asleep",      # Sing
    77: "poisoned",    # Poison Powder
    78: "paralyzed",   # Stun Spore
    79: "asleep",      # Sleep Powder
    48: "confused",    # Supersonic
}


class Command(BaseCommand):
    help = (
        "Assign trigger_status to chase moves and verify standard moves have "
        "applies_status set, enabling the combo chain system to fire in battle."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Preview changes without writing to the database.",
        )

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        from apps.effects.models import StatusEffect
        from apps.pokemon.models import Move

        dry_run: bool = options["dry_run"]
        prefix = "[DRY RUN] " if dry_run else ""

        # Pre-fetch all StatusEffect objects keyed by name
        status_map: dict[str, StatusEffect] = {
            se.name: se for se in StatusEffect.objects.all()
        }

        self.stdout.write(f"Loaded {len(status_map)} status effects.")
        self.stdout.write("")

        # -- Phase A: assign trigger_status to chase moves -----------------
        self.stdout.write(self.style.MIGRATE_HEADING("== Phase A: trigger_status for chase moves =="))
        trigger_updated = 0
        trigger_skipped = 0

        move_pks = list(TRIGGER_ASSIGNMENTS.keys())
        moves = {m.pk: m for m in Move.objects.filter(pk__in=move_pks).select_related("trigger_status")}

        for move_pk, status_name in TRIGGER_ASSIGNMENTS.items():
            move = moves.get(move_pk)
            if move is None:
                self.stdout.write(self.style.WARNING(f"  Move pk={move_pk} not found — skipped."))
                trigger_skipped += 1
                continue

            se = status_map.get(status_name)
            if se is None:
                self.stdout.write(self.style.WARNING(
                    f"  StatusEffect '{status_name}' not found for Move pk={move_pk} ({move.name}) — skipped."
                ))
                trigger_skipped += 1
                continue

            old = move.trigger_status.name if move.trigger_status else "None"
            if move.trigger_status_id == se.pk:
                self.stdout.write(f"  pk={move_pk:3d} {move.name:30s} trigger_status already={se.name} OK")
                continue

            self.stdout.write(
                f"  {prefix}pk={move_pk:3d} {move.name:30s}  {old} -> {se.name}"
            )
            if not dry_run:
                move.trigger_status = se
                move.save(update_fields=["trigger_status"])
            trigger_updated += 1

        # -- Phase B: verify/fix applies_status on standard moves ---------
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("== Phase B: applies_status for standard moves =="))
        applies_updated = 0

        std_pks = list(STANDARD_STATUS_ASSIGNMENTS.keys())
        std_moves = {
            m.pk: m for m in Move.objects.filter(pk__in=std_pks).select_related("applies_status")
        }

        for move_pk, status_name in STANDARD_STATUS_ASSIGNMENTS.items():
            move = std_moves.get(move_pk)
            if move is None:
                self.stdout.write(self.style.WARNING(f"  Move pk={move_pk} not found — skipped."))
                continue

            se = status_map.get(status_name)
            if se is None:
                self.stdout.write(self.style.WARNING(
                    f"  StatusEffect '{status_name}' not found for Move pk={move_pk} ({move.name}) — skipped."
                ))
                continue

            old = move.applies_status.name if move.applies_status else "None"
            if move.applies_status_id == se.pk:
                self.stdout.write(f"  pk={move_pk:3d} {move.name:30s} applies_status already={se.name} OK")
                continue

            self.stdout.write(
                f"  {prefix}pk={move_pk:3d} {move.name:30s}  {old} -> {se.name}"
            )
            if not dry_run:
                move.applies_status = se
                move.save(update_fields=["applies_status"])
            applies_updated += 1

        # -- Summary -------------------------------------------------------
        self.stdout.write("")
        self.stdout.write("-" * 60)
        self.stdout.write(self.style.SUCCESS(f"{prefix}Done."))
        self.stdout.write(f"  trigger_status assigned : {trigger_updated}")
        self.stdout.write(f"  trigger_status skipped  : {trigger_skipped}")
        self.stdout.write(f"  applies_status fixed    : {applies_updated}")
        self.stdout.write("")
        self.stdout.write("Combo chains now active. Example flows:")
        self.stdout.write("  Ember (BURNED) -> Fire Punch triggers on BURNED -> COMBO x2")
        self.stdout.write("  Thunder Shock (PARALYZED) -> Thunder Punch/Bite trigger -> COMBO x2")
        self.stdout.write("  Acid (POISONED) -> Poison Sting/Bind trigger -> COMBO x2")
        self.stdout.write("  Fire Spin (BOUND) -> Wrap triggers -> COMBO x2")
        self.stdout.write("  Supersonic (CONFUSED) -> Psybeam/Sonic Boom trigger -> COMBO x2")

        if dry_run:
            transaction.set_rollback(True)
