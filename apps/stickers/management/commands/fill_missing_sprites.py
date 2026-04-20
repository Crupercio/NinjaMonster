"""
Management command: fill_missing_sprites

Fills gaps in local sprite folders for variants whose original PokeAPI source
stopped covering higher generations.

  anime        — missing 494–905
    URL: https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{dex}.png

  battle_scene — missing 650–905
    URL: https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/showdown/{dex}.gif

Usage:
    python manage.py fill_missing_sprites                       # fill all gaps
    python manage.py fill_missing_sprites --variants anime      # anime only
    python manage.py fill_missing_sprites --variants battle_scene
    python manage.py fill_missing_sprites --dex-start 494 --dex-end 905
    python manage.py fill_missing_sprites --dry-run             # preview only
    python manage.py fill_missing_sprites --force               # re-download existing
"""
from __future__ import annotations

import logging
import time
import urllib.error
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser

logger = logging.getLogger(__name__)

_RAW = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon"

# variant → (url_template, file_extension)
VARIANT_CONFIG: dict[str, tuple[str, str]] = {
    "anime":        (f"{_RAW}/{{dex}}.png",                       ".png"),
    "battle_scene": (f"{_RAW}/other/showdown/{{dex}}.gif",        ".gif"),
}

ALL_VARIANTS = list(VARIANT_CONFIG.keys())


def _download(url: str, dest: Path, retries: int = 2) -> bool:
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (StickerBot/2.0)"}
    )
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
                dest.write_bytes(resp.read())
            return True
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return False
            if attempt < retries:
                time.sleep(2.0)
            else:
                logger.warning("HTTP %d for %s", exc.code, url)
                return False
        except Exception as exc:
            if attempt < retries:
                time.sleep(2.0)
            else:
                logger.warning("Failed %s: %s", url, exc)
                return False
    return False


class Command(BaseCommand):
    help = "Fill missing anime/battle_scene sprites using alternative PokeAPI sources."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--variants",
            nargs="+",
            choices=ALL_VARIANTS,
            default=ALL_VARIANTS,
            metavar="VARIANT",
            help=f"Variants to fill. Choices: {', '.join(ALL_VARIANTS)}. Default: all.",
        )
        parser.add_argument(
            "--dex-start",
            type=int,
            default=1,
            metavar="N",
            help="First Pokédex number (inclusive). Default: 1.",
        )
        parser.add_argument(
            "--dex-end",
            type=int,
            default=905,
            metavar="N",
            help="Last Pokédex number (inclusive). Default: 905.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-download even if file already exists.",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=0.05,
            metavar="SECONDS",
            help="Seconds between requests. Default: 0.05.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be downloaded without doing anything.",
        )

    def handle(self, *args: object, **options: object) -> None:
        variants: list[str] = options["variants"]
        dex_start: int = options["dex_start"]
        dex_end: int = options["dex_end"]
        force: bool = options["force"]
        delay: float = options["delay"]
        dry_run: bool = options["dry_run"]

        sprites_root = Path(settings.BASE_DIR) / "static" / "sprites"

        dex_range = range(dex_start, dex_end + 1)
        total = len(dex_range) * len(variants)

        self.stdout.write(
            f"\n{'[DRY RUN] ' if dry_run else ''}"
            f"Dex range: #{dex_start}–#{dex_end}  |  "
            f"Variants: {', '.join(variants)}  |  "
            f"Max files: {total}\n"
        )

        done = skipped = failed = 0

        for variant in variants:
            url_template, ext = VARIANT_CONFIG[variant]
            folder = sprites_root / variant

            if not dry_run:
                folder.mkdir(parents=True, exist_ok=True)

            for dex in dex_range:
                dest = folder / f"{dex}{ext}"

                if dest.exists() and not force:
                    skipped += 1
                    continue

                url = url_template.format(dex=dex)

                if dry_run:
                    self.stdout.write(f"  WOULD  #{dex:04d} [{variant}]  {url}")
                    done += 1
                    continue

                if _download(url, dest):
                    done += 1
                    self.stdout.write(f"  OK  #{dex:04d} [{variant}]")
                else:
                    failed += 1
                    self.stdout.write(
                        self.style.WARNING(f"  MISS #{dex:04d} [{variant}] — not found")
                    )

                time.sleep(delay)

        self.stdout.write(self.style.SUCCESS(
            f"\nDone.  Downloaded: {done}  Skipped: {skipped}  Failed: {failed}\n"
            f"Sprites at: {sprites_root}\n"
        ))
