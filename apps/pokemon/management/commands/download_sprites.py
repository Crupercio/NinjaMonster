"""
Management command: download Gen 1 Pokemon sprites to local media storage.

Fetches official artwork from the Pokemon.com CDN and saves each file to
MEDIA_ROOT/pokemon/sprites/<dex_number>.png, then updates Pokemon.sprite_url
so the template will serve the local copy instead of the CDN.

Usage:
    python manage.py download_sprites            # all Pokemon with a pokedex_number
    python manage.py download_sprites --force    # re-download even if file exists
"""
import logging
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.pokemon.models import Pokemon

logger = logging.getLogger(__name__)

SPRITE_CDN = (
    "https://www.pokemon.com/static-assets/content-assets/cms2/img/pokedex/full/{num:03d}.png"
)
SPRITE_SUBDIR = Path("pokemon") / "sprites"


class Command(BaseCommand):
    help = "Download Pokemon sprites from CDN to local media storage."

    def add_arguments(self, parser: object) -> None:
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-download sprites even if the local file already exists.",
        )

    def handle(self, *args: object, **options: object) -> None:
        force: bool = options["force"]

        sprite_dir = Path(settings.MEDIA_ROOT) / SPRITE_SUBDIR
        sprite_dir.mkdir(parents=True, exist_ok=True)

        qs = Pokemon.objects.filter(pokedex_number__isnull=False).order_by("pokedex_number")
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
