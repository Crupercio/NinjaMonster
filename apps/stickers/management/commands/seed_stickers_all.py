"""
Management command: verify sticker system coverage across all seeded Pokemon.

Stickers are player-earned records (not pre-created). This command reports
how many Pokemon exist per generation and confirms the album can display them.

Usage:
    python manage.py seed_stickers_all
"""
import logging

from django.core.management.base import BaseCommand

from apps.pokemon.models import Generation, Pokemon

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Report sticker system coverage — how many Pokemon are seeded per generation."

    def handle(self, *args: object, **options: object) -> None:
        total = Pokemon.objects.count()
        self.stdout.write(f"Total Pokemon in database: {total}\n")

        generations = Generation.objects.order_by("number")
        if not generations.exists():
            self.stdout.write(self.style.WARNING("No generations seeded yet."))
            return

        for gen in generations:
            count = Pokemon.objects.filter(generation=gen).count()
            no_gen_count = Pokemon.objects.filter(
                pokedex_number__isnull=False, generation__isnull=True
            ).count()
            self.stdout.write(
                self.style.SUCCESS(f"  Gen {gen.number} ({gen.name}): {count} Pokémon")
            )

        if no_gen_count := Pokemon.objects.filter(
            pokedex_number__isnull=False, generation__isnull=True
        ).count():
            self.stdout.write(
                self.style.WARNING(
                    f"\n  {no_gen_count} Pokémon missing generation FK "
                    f"— run seed_pokeapi to fix."
                )
            )

        self.stdout.write(
            "\nNote: Stickers are earned through gameplay (catch, training, battles, packs)."
            "\nThe album will automatically display all seeded Pokémon as unlockable slots."
        )
