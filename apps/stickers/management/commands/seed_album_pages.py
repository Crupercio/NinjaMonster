"""
Management command: seed AlbumPage rows for every region that has Pokémon in the DB.

Idempotent — safe to re-run. Only creates pages for regions that have Pokémon
with the matching dex range already loaded. Kanto pages are always seeded from
the KANTO_PAGES constant; future regions can be added here as their Pokémon
are loaded.
"""
import logging

from django.core.management.base import BaseCommand

from apps.pokemon.models import Pokemon
from apps.stickers.models import KANTO_PAGES, AlbumPage

logger = logging.getLogger(__name__)


# Future regions: add entries here when Pokémon for those gens are loaded.
# Format: (region, [(page_number, dex_start, dex_end, location_name, bg_image_name), ...])
REGION_PAGE_DEFS: list[tuple[str, list[tuple[int, int, int, str, str]]]] = [
    ("kanto", KANTO_PAGES),
    # ("johto", JOHTO_PAGES),   ← add when gen 2 Pokémon are loaded
    # ("hoenn", HOENN_PAGES),
]


class Command(BaseCommand):
    help = "Seed AlbumPage records for all regions that have Pokémon in the database."

    def handle(self, *args, **options) -> None:  # type: ignore[override]
        created_total = 0
        skipped_total = 0

        for region, page_defs in REGION_PAGE_DEFS:
            for page_num, dex_start, dex_end, location_name, bg_image_name in page_defs:
                # Only create if at least one Pokémon exists in this dex range
                has_pokemon = Pokemon.objects.filter(
                    pokedex_number__gte=dex_start,
                    pokedex_number__lte=dex_end,
                ).exists()
                if not has_pokemon:
                    self.stdout.write(
                        f"  Skipping {region} p{page_num} ({dex_start}-{dex_end}): "
                        f"no Pokémon in DB yet"
                    )
                    skipped_total += 1
                    continue

                page, created = AlbumPage.objects.update_or_create(
                    region=region,
                    page_number=page_num,
                    defaults={
                        "dex_start": dex_start,
                        "dex_end": dex_end,
                        "location_name": location_name,
                        "bg_image_name": bg_image_name,
                    },
                )
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  Created: {region} p{page_num} — {location_name} "
                            f"(#{dex_start}–#{dex_end})"
                        )
                    )
                    created_total += 1
                else:
                    self.stdout.write(f"  Exists:  {region} p{page_num} — {location_name}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. Created {created_total} new pages, skipped {skipped_total}."
            )
        )
