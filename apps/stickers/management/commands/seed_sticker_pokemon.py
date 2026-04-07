"""
Management command: seed_sticker_pokemon

Verifies that the first 30 Pokémon (by pokedex_number, falling back to pk)
are present in the database — a prerequisite for the sticker system.

Usage:
    python manage.py seed_sticker_pokemon            # dry-run report
    python manage.py seed_sticker_pokemon --load     # load the fixture if missing
"""
import logging
from argparse import ArgumentParser
from typing import Any

from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.pokemon.models import Pokemon

logger = logging.getLogger(__name__)

# First-generation starter pool — the 30 Pokémon seeded for the sticker album.
SEED_POKEMON_NAMES: list[str] = [
    "Bulbasaur", "Ivysaur", "Venusaur",
    "Charmander", "Charmeleon", "Charizard",
    "Squirtle", "Wartortle", "Blastoise",
    "Pikachu", "Raichu",
    "Gengar", "Haunter",
    "Jolteon", "Flareon", "Vaporeon",
    "Lapras",
    "Articuno", "Zapdos", "Moltres",
    "Alakazam", "Hypno",
    "Arbok", "Weezing",
    "Machamp", "Starmie", "Dragonite",
    "Mewtwo", "Mew",
    "Umbreon",
]


class Command(BaseCommand):
    help = (
        "Check that the first 30 Pokémon required by the sticker system exist. "
        "Pass --load to auto-load the pokemon fixture if any are missing."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--load",
            action="store_true",
            default=False,
            help="Load apps/pokemon/fixtures/pokemon.json if Pokémon are missing.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        present = set(
            Pokemon.objects.filter(name__in=SEED_POKEMON_NAMES)
            .values_list("name", flat=True)
        )
        missing = [n for n in SEED_POKEMON_NAMES if n not in present]

        self.stdout.write(
            f"Sticker seed check: {len(present)}/30 Pokémon present, "
            f"{len(missing)} missing."
        )

        if not missing:
            self.stdout.write(self.style.SUCCESS("All 30 seed Pokémon are present."))
            return

        self.stdout.write(f"Missing: {', '.join(missing)}")

        if options["load"]:
            self.stdout.write("Loading pokemon fixture …")
            call_command(
                "loaddata",
                "apps/pokemon/fixtures/types.json",
                verbosity=1,
            )
            call_command(
                "loaddata",
                "apps/pokemon/fixtures/pokemon.json",
                verbosity=1,
            )
            # Re-check
            still_missing = [
                n for n in SEED_POKEMON_NAMES
                if not Pokemon.objects.filter(name=n).exists()
            ]
            if still_missing:
                self.stderr.write(
                    self.style.ERROR(
                        f"Still missing after fixture load: {', '.join(still_missing)}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS("Fixture loaded — all 30 seed Pokémon present.")
                )
        else:
            self.stdout.write(
                "Run with --load to load the pokemon fixture automatically."
            )
