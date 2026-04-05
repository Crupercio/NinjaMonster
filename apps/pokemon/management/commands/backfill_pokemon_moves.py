"""
Management command: backfill_pokemon_moves

Fills empty move slots on OwnedPokemon instances that were created before
the SpeciesMovePool system was fully populated. Already-assigned slots are
left untouched unless --force is passed.

Usage:
    python manage.py backfill_pokemon_moves
    python manage.py backfill_pokemon_moves --force   # overwrite all slots
    python manage.py backfill_pokemon_moves --dry-run # preview only
"""
from __future__ import annotations

import logging
import random
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

logger = logging.getLogger(__name__)

SLOT_FIELD_MAP: dict[str, str] = {
    "standard": "move_standard",
    "chase": "move_chase",
    "special": "move_special",
    "support": "move_support",
    "passive": "move_passive",
}


class Command(BaseCommand):
    help = (
        "Backfill missing move slots on OwnedPokemon from each species' SpeciesMovePool. "
        "Only fills None slots by default; use --force to overwrite existing assignments."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Re-assign ALL move slots, even those already filled.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Report what would change without writing to the database.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        force: bool = options["force"]
        dry_run: bool = options["dry_run"]

        from apps.pokemon.models import OwnedPokemon, SpeciesMovePool  # local import

        if force:
            queryset = OwnedPokemon.objects.select_related("species").all()
        else:
            missing_any = Q(move_standard__isnull=True) | Q(move_chase__isnull=True) | \
                          Q(move_special__isnull=True) | Q(move_support__isnull=True) | \
                          Q(move_passive__isnull=True)
            queryset = OwnedPokemon.objects.select_related("species").filter(missing_any)

        total_candidates = queryset.count()
        self.stdout.write(
            f"Found {total_candidates} OwnedPokemon to inspect"
            f"{' (force mode — all slots)' if force else ' (missing slots only)'}."
        )

        if total_candidates == 0:
            self.stdout.write(self.style.SUCCESS("Nothing to do."))
            return

        # Pre-fetch all SpeciesMovePool entries in one query, grouped by species.
        pool_qs = SpeciesMovePool.objects.select_related("move").all()
        species_pool: dict[int, dict[str, list]] = {}
        for entry in pool_qs:
            slot_group = species_pool.setdefault(entry.species_id, {})
            slot_group.setdefault(entry.slot_type, []).append(entry.move)

        updated_count = 0
        skipped_no_pool = 0
        slot_fill_counts: dict[str, int] = {slot: 0 for slot in SLOT_FIELD_MAP}

        for owned in queryset.iterator():
            pool = species_pool.get(owned.species_id, {})

            if not pool:
                logger.warning(
                    "No SpeciesMovePool for %s (OwnedPokemon pk=%s) — skipping.",
                    owned.species.name,
                    owned.pk,
                )
                skipped_no_pool += 1
                continue

            fields_to_save: list[str] = []
            for slot_type, field_name in SLOT_FIELD_MAP.items():
                current_value = getattr(owned, field_name + "_id")
                if current_value is not None and not force:
                    continue  # slot already filled, leave it alone

                candidates = pool.get(slot_type, [])
                if not candidates:
                    logger.debug(
                        "No %s candidates in pool for %s — slot left empty.",
                        slot_type,
                        owned.species.name,
                    )
                    continue

                chosen = random.choice(candidates)
                if not dry_run:
                    setattr(owned, field_name, chosen)
                fields_to_save.append(field_name)
                slot_fill_counts[slot_type] += 1

            if fields_to_save:
                if not dry_run:
                    with transaction.atomic():
                        owned.save(update_fields=fields_to_save)
                updated_count += 1
                logger.info(
                    "%s pk=%s: filled %s.",
                    owned.species.name,
                    owned.pk,
                    ", ".join(fields_to_save),
                )

        # --- Summary ---
        prefix = "[DRY RUN] " if dry_run else ""
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"{prefix}Done."))
        self.stdout.write(f"  Inspected : {total_candidates}")
        self.stdout.write(f"  Updated   : {updated_count}")
        self.stdout.write(f"  No pool   : {skipped_no_pool} (species has no SpeciesMovePool entries)")
        self.stdout.write("  Slots filled per type:")
        for slot_type, count in slot_fill_counts.items():
            self.stdout.write(f"    {slot_type:<10} {count}")
