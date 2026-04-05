"""
Management command: check_move_pools

Reports which species are missing SpeciesMovePool coverage for any slot type.
Exits with code 1 if any incomplete species are found, so it can be used in CI.

Usage:
    python manage.py check_move_pools
    python manage.py check_move_pools --quiet   # only print failures
"""
from __future__ import annotations

import sys
from typing import Any

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Verify that every Pokemon species has at least one SpeciesMovePool entry "
        "for each slot type (standard, chase, special, support, passive). "
        "Exits with code 1 if any species are incomplete."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--quiet",
            action="store_true",
            default=False,
            help="Suppress output for species that are complete.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from apps.pokemon.models import MoveSlotType, Pokemon, SpeciesMovePool

        quiet: bool = options["quiet"]
        all_slots: frozenset[str] = frozenset(MoveSlotType.values)

        all_species = list(
            Pokemon.objects.prefetch_related("move_pool")
            .order_by("pokedex_number", "name")
        )

        # Build a coverage map: species_pk → set of covered slot types.
        coverage: dict[int, set[str]] = {s.pk: set() for s in all_species}
        for entry in SpeciesMovePool.objects.values("species_id", "slot_type"):
            coverage[entry["species_id"]].add(entry["slot_type"])

        incomplete: list[tuple[Any, frozenset[str]]] = []
        for species in all_species:
            missing = all_slots - coverage[species.pk]
            if missing:
                incomplete.append((species, frozenset(missing)))

        total = len(all_species)

        if not incomplete:
            self.stdout.write(
                self.style.SUCCESS(
                    f"All {total} species are battle-ready "
                    f"(every slot type covered)."
                )
            )
            return

        self.stdout.write(
            self.style.ERROR(
                f"{len(incomplete)}/{total} species are NOT battle-ready:"
            )
        )
        for species, missing in incomplete:
            dex = f"#{species.pokedex_number}" if species.pokedex_number else "no-dex"
            self.stdout.write(
                f"  pk={species.pk} {dex} {species.name} "
                f"— missing slots: {', '.join(sorted(missing))}"
            )

        if not quiet:
            self.stdout.write("")
            self.stdout.write(
                "Run `python manage.py seed_move_pools` to backfill missing entries."
            )

        sys.exit(1)
