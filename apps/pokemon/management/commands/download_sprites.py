"""
Management command: download Pokemon official artwork to local media storage.

Fetches official artwork from the PokeAPI GitHub sprites repository and saves
each file to MEDIA_ROOT/pokemon/sprites/<dex_number:03d>.png, then updates
Pokemon.sprite_url so the template will serve the local copy.

Usage:
    python manage.py download_sprites            # all Pokemon with a pokedex_number
    python manage.py download_sprites --force    # re-download even if file exists
    python manage.py download_sprites --start 152 --end 251   # range only
"""
import logging
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.pokemon.models import Pokemon

logger = logging.getLogger(__name__)

SPRITE_CDN = (
    "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{num}.png"
)
SPRITE_SUBDIR = Path("pokemon") / "sprites"


class Command(BaseCommand):
    help = "Download Pokemon official artwork from PokeAPI GitHub to local media storage."

    def add_arguments(self, parser: object) -> None:
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-download sprites even if the local file already exists.",
        )
        parser.add_argument(
            "--start",
            type=int,
            default=None,
            help="Only download sprites for dex numbers >= this value.",
        )
        parser.add_argument(
            "--end",
            type=int,
            default=None,
            help="Only download sprites for dex numbers <= this value.",
        )

    def handle(self, *args: object, **options: object) -> None:
        force: bool = options["force"]
        start: int | None = options["start"]
        end: int | None = options["end"]

        sprite_dir = Path(settings.MEDIA_ROOT) / SPRITE_SUBDIR
        sprite_dir.mkdir(parents=True, exist_ok=True)

        qs = Pokemon.objects.filter(pokedex_number__isnull=False).order_by("pokedex_number")
        if start is not None:
            qs = qs.filter(pokedex_number__gte=start)
        if end is not None:
            qs = qs.filter(pokedex_number__lte=end)
        total = qs.count()

        if total == 0:
            self.stdout.write(self.style.WARNING("No Pokemon with a pokedex_number found."))
            return

        self.stdout.write(f"Downloading sprites for {total} Pokemon…")
        downloaded = 0
        skipped = 0
        failed = 0

        for pokemon in qs:
            num: int = pokemon.pokedex_number  # type: ignore[assignment]
            filename = f"{num:03d}.png"
            local_path = sprite_dir / filename
            # Use forward slashes for the URL regardless of OS path separator
            media_url = f"{settings.MEDIA_URL}pokemon/sprites/{filename}"

            if local_path.exists() and not force:
                if pokemon.sprite_url != media_url:
                    pokemon.sprite_url = media_url
                    pokemon.save(update_fields=["sprite_url"])
                skipped += 1
                continue

            url = SPRITE_CDN.format(num=num)
            try:
                urllib.request.urlretrieve(url, local_path)  # noqa: S310
                pokemon.sprite_url = media_url
                pokemon.save(update_fields=["sprite_url"])
                downloaded += 1
                self.stdout.write(f"  OK #{num:03d} {pokemon.name}")
            except Exception as exc:
                failed += 1
                logger.warning("Failed to download sprite for %s (#%d): %s", pokemon.name, num, exc)
                self.stdout.write(
                    self.style.WARNING(f"  FAIL #{num:03d} {pokemon.name} - {exc}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Downloaded: {downloaded}, Skipped: {skipped}, Failed: {failed}"
            )
        )
