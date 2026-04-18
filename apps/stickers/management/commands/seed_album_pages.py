"""
Management command: seed AlbumPage rows for every region that has Pokémon in the DB.

Idempotent — safe to re-run. Only creates pages for regions that have Pokémon
with the matching dex range already loaded.

All pages use bg_image_name="" — the album template applies the site's dark card
theme as the background (no CSS gradients).
"""
import logging

from django.core.management.base import BaseCommand

from apps.pokemon.models import Pokemon
from apps.stickers.models import KANTO_PAGES, AlbumPage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Region page definitions
# Format: (page_number, dex_start, dex_end, location_name, bg_image_name)
# bg_image_name="" → uses site dark-card theme fallback (no gradient)
# ---------------------------------------------------------------------------

JOHTO_PAGES: list[tuple[int, int, int, str, str]] = [
    (1,  152, 166, "New Bark Town at Dusk",        ""),
    (2,  167, 181, "Sprout Tower — Violet City",   ""),
    (3,  182, 196, "Ruins of Alph — Ancient Halls",""),
    (4,  197, 211, "Ilex Forest Shadows",          ""),
    (5,  212, 226, "Mt. Mortar Caverns",           ""),
    (6,  227, 241, "Dragon's Den — Blackthorn",    ""),
    (7,  242, 251, "Tin Tower — Ho-Oh's Roost",    ""),
]

HOENN_PAGES: list[tuple[int, int, int, str, str]] = [
    (1,  252, 266, "Littleroot — Route 101",       ""),
    (2,  267, 281, "Petalburg Forest Depths",      ""),
    (3,  282, 296, "Dewford Cave — Dark Waters",   ""),
    (4,  297, 311, "Mt. Chimney Volcanic Peak",    ""),
    (5,  312, 326, "Fortree City — Canopy Walk",   ""),
    (6,  327, 341, "Mossdeep Space Center",        ""),
    (7,  342, 356, "Seafloor Cavern — Abyss",      ""),
    (8,  357, 371, "Sky Pillar — Ancient Summit",  ""),
    (9,  372, 386, "Cave of Origin — Primal Rift", ""),
]

SINNOH_PAGES: list[tuple[int, int, int, str, str]] = [
    (1,  387, 401, "Lake Verity at Dawn",          ""),
    (2,  402, 416, "Eterna Forest — Mist Hour",    ""),
    (3,  417, 431, "Wayward Cave — Lost Paths",    ""),
    (4,  432, 446, "Solaceon Ruins — Glyphs",      ""),
    (5,  447, 461, "Iron Island — Steel Halls",    ""),
    (6,  462, 476, "Snowpoint Temple — Frozen",    ""),
    (7,  477, 491, "Distortion World — Void",      ""),
    (8,  492, 493, "Shaymin's Garden / Arceus",    ""),
]

UNOVA_PAGES: list[tuple[int, int, int, str, str]] = [
    (1,  494, 508, "Nuvema Town — Route 1",        ""),
    (2,  509, 523, "Pinwheel Forest Shadows",      ""),
    (3,  524, 538, "Desert Resort — Relic Castle", ""),
    (4,  539, 553, "Chargestone Cave — Crystal",   ""),
    (5,  554, 568, "Mistralton Cave — Thunder",    ""),
    (6,  569, 583, "Giant Chasm — Frozen Hollow",  ""),
    (7,  584, 598, "Dragonspiral Tower — Storm",   ""),
    (8,  599, 613, "Abyssal Ruins — Depths",       ""),
    (9,  614, 628, "Victory Road — Final Trial",   ""),
    (10, 629, 643, "N's Castle — Truth & Ideals",  ""),
    (11, 644, 649, "Legendary Chamber — Unova",    ""),
]

KALOS_PAGES: list[tuple[int, int, int, str, str]] = [
    (1,  650, 664, "Vaniville Town — Route 2",     ""),
    (2,  665, 679, "Santalune Forest — Dew",       ""),
    (3,  680, 694, "Geosenge Town — Megastones",   ""),
    (4,  695, 709, "Frost Cavern — Ice Mirror",    ""),
    (5,  710, 721, "Sea Spirit's Den — Azure Bay", ""),
]

ALOLA_PAGES: list[tuple[int, int, int, str, str]] = [
    (1,  722, 736, "Iki Town — Melemele Island",   ""),
    (2,  737, 751, "Lush Jungle — Akala Island",   ""),
    (3,  752, 766, "Malie Garden — Ula'ula",       ""),
    (4,  767, 781, "Poni Plains — Ancient Ruins",  ""),
    (5,  782, 796, "Ultra Wormhole — Dimension",   ""),
    (6,  797, 809, "Altar of the Sunne & Moone",   ""),
]

GALAR_PAGES: list[tuple[int, int, int, str, str]] = [
    (1,  810, 824, "Wedgehurst — Wild Area",       ""),
    (2,  825, 839, "Galar Mine — Motostoke",       ""),
    (3,  840, 854, "Glimwood Tangle — Dusk Mist",  ""),
    (4,  855, 869, "Spikemuth — Dark Streets",     ""),
    (5,  870, 884, "Rose Tower — Wyndon City",     ""),
    (6,  885, 897, "Crown Tundra — Frozen Wild",   ""),
    (7,  898, 905, "Legendary Lair — Galar",       ""),
]


# All regions in order
REGION_PAGE_DEFS: list[tuple[str, list[tuple[int, int, int, str, str]]]] = [
    ("kanto",  KANTO_PAGES),
    ("johto",  JOHTO_PAGES),
    ("hoenn",  HOENN_PAGES),
    ("sinnoh", SINNOH_PAGES),
    ("unova",  UNOVA_PAGES),
    ("kalos",  KALOS_PAGES),
    ("alola",  ALOLA_PAGES),
    ("galar",  GALAR_PAGES),
]


class Command(BaseCommand):
    help = "Seed AlbumPage records for all regions that have Pokémon in the database."

    def handle(self, *args, **options) -> None:  # type: ignore[override]
        created_total = 0
        skipped_total = 0

        for region, page_defs in REGION_PAGE_DEFS:
            self.stdout.write(f"\n{region.upper()}")
            for page_num, dex_start, dex_end, location_name, bg_image_name in page_defs:
                has_pokemon = Pokemon.objects.filter(
                    pokedex_number__gte=dex_start,
                    pokedex_number__lte=dex_end,
                ).exists()
                if not has_pokemon:
                    self.stdout.write(
                        f"  Skip p{page_num} ({dex_start}-{dex_end}): no Pokémon yet"
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
                            f"  + p{page_num} — {location_name} (#{dex_start}–#{dex_end})"
                        )
                    )
                    created_total += 1
                else:
                    self.stdout.write(
                        f"  ~ p{page_num} — {location_name} (exists)"
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. Created {created_total} new pages, skipped {skipped_total} (no Pokémon yet)."
            )
        )
