"""
Management command: generate AI sticker images via Pollinations.ai and save
to static/stickers/generated/{dex:03d}_{variant}.jpg

Uses the same Naruto-online / chakra-ninja prompt templates as the
StickerGeneratorView, seeded by Pokédex number so images are deterministic.

Pollinations.ai (updated 2026):
    - Requires a free API key from https://enter.pollinations.ai
    - Endpoint: https://gen.pollinations.ai/image/{prompt}
    - Secret keys (sk_...): no rate limit — best for this command
    - Set your key in the POLLINATIONS_API_KEY environment variable
      or pass it with --api-key

Usage:
    # Dry run — see what would be generated (no downloads)
    python manage.py generate_sticker_images --dry-run

    # Generate chibi only for Gen 1
    python manage.py generate_sticker_images --variants chibi --dex-end 151

    # All 7 variants for all Pokémon
    python manage.py generate_sticker_images

    # Re-download even if file exists
    python manage.py generate_sticker_images --force

    # Pass API key inline instead of env var
    python manage.py generate_sticker_images --api-key sk_yourkey

Estimated times (with secret key, no rate limit, ~3s per image):
    All 7 variants × 152 Pokémon = 1064 images ≈ 53 min
    Chibi only (1 variant)       =  152 images ≈  8 min
"""
import logging
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser

from apps.pokemon.models import Pokemon

logger = logging.getLogger(__name__)

# ── Output directory ────────────────────────────────────────────────────────
STICKER_SUBDIR = Path("stickers") / "generated"

# ── Pollinations.ai endpoint (2026) ────────────────────────────────────────
BASE_URL = "https://gen.pollinations.ai/image/{prompt}?width={size}&height={size}&seed={seed}&model=flux&nologo=true"

IMAGE_SIZE = 512

# ── Prompt templates (Naruto-online / chakra-ninja theme) ───────────────────
PROMPT_TEMPLATES: dict[str, str] = {
    "base": (
        "{name} pokemon, ninja shinobi battle card art, {chakra} chakra aura, "
        "Naruto online game style, clean character illustration, dramatic lighting, "
        "collectible card art, detailed"
    ),
    "shiny": (
        "{name} pokemon shiny variant, glowing {chakra} chakra energy, golden divine aura, "
        "Naruto online legendary card, iridescent colors, bright divine radiance, "
        "premium foil illustration"
    ),
    "battle_scene": (
        "{name} pokemon action battle pose, {chakra} chakra explosion, "
        "Naruto shinobi battle scene, dynamic energy effects, fierce expression, "
        "anime battle background, epic fantasy"
    ),
    "chibi": (
        "cute chibi {name} pokemon, tiny ninja shinobi outfit, {chakra} element symbol, "
        "kawaii sticker art, thick white outline, pastel colors, "
        "simple flat background, adorable"
    ),
    "manga_panel": (
        "{name} pokemon manga panel art, black ink lines, dramatic screentone shading, "
        "Naruto manga style, speed lines, intense expression, {chakra} chakra marks, "
        "white background"
    ),
    "full_illustration": (
        "{name} pokemon full art card illustration, {chakra} chakra landscape background, "
        "Naruto online premium artwork, lush detailed environment, painted style, "
        "wide angle, epic scene"
    ),
    "anime": (
        "{name} pokemon anime screenshot style, Naruto shippuden animation quality, "
        "{chakra} chakra glow, cel shading, clean outlines, vibrant colors, "
        "anime broadcast style"
    ),
}

ALL_VARIANTS = list(PROMPT_TEMPLATES.keys())


def build_url(name: str, chakra: str, variant: str, seed: int, api_key: str = "") -> str:
    prompt = PROMPT_TEMPLATES[variant].format(name=name, chakra=chakra or "natural")
    url = BASE_URL.format(prompt=quote(prompt), size=IMAGE_SIZE, seed=seed)
    if api_key:
        url += f"&key={quote(api_key)}"
    return url


class Command(BaseCommand):
    help = "Download AI-generated sticker images from Pollinations.ai to static/stickers/generated/"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--api-key",
            metavar="KEY",
            default="",
            help=(
                "Pollinations.ai secret key (sk_...). "
                "Falls back to POLLINATIONS_API_KEY env var. "
                "Get yours free at https://enter.pollinations.ai"
            ),
        )
        parser.add_argument(
            "--variants",
            nargs="+",
            choices=ALL_VARIANTS,
            default=ALL_VARIANTS,
            metavar="VARIANT",
            help=f"Variants to generate. Choices: {', '.join(ALL_VARIANTS)}. Default: all.",
        )
        parser.add_argument(
            "--dex-start",
            type=int,
            default=1,
            metavar="N",
            help="First Pokédex number to process (inclusive). Default: 1.",
        )
        parser.add_argument(
            "--dex-end",
            type=int,
            default=9999,
            metavar="N",
            help="Last Pokédex number to process (inclusive). Default: all.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-download images even if the local file already exists.",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=3.0,
            metavar="SECONDS",
            help="Seconds to wait between requests. Default: 3 (with secret key, no limit).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be generated without downloading anything.",
        )

    def handle(self, *args: object, **options: object) -> None:
        variants: list[str] = options["variants"]
        dex_start: int      = options["dex_start"]
        dex_end: int        = options["dex_end"]
        force: bool         = options["force"]
        delay: float        = options["delay"]
        dry_run: bool       = options["dry_run"]

        # ── API key ─────────────────────────────────────────────────────────
        api_key: str = options["api_key"] or os.environ.get("POLLINATIONS_API_KEY", "")
        if not api_key and not dry_run:
            self.stdout.write(self.style.ERROR(
                "\nNo API key provided.\n"
                "  1. Sign up free at https://enter.pollinations.ai\n"
                "  2. Create a Secret key (sk_...)\n"
                "  3. Run with:  --api-key sk_yourkey\n"
                "     or set:   POLLINATIONS_API_KEY=sk_yourkey in your environment\n"
            ))
            return

        # ── Output dir ───────────────────────────────────────────────────────
        out_dir = Path(settings.BASE_DIR) / "static" / STICKER_SUBDIR
        if not dry_run:
            out_dir.mkdir(parents=True, exist_ok=True)

        # ── Pokémon queryset ─────────────────────────────────────────────────
        qs = (
            Pokemon.objects
            .filter(
                pokedex_number__isnull=False,
                pokedex_number__gte=dex_start,
                pokedex_number__lte=dex_end,
            )
            .select_related("primary_type__chakra_element")
            .order_by("pokedex_number")
        )
        pokemon_list = list(qs)

        if not pokemon_list:
            self.stdout.write(self.style.WARNING("No Pokemon found for the given range."))
            return

        total = len(pokemon_list) * len(variants)
        self.stdout.write(
            f"\n{'[DRY RUN] ' if dry_run else ''}"
            f"{len(variants)} variant(s) x {len(pokemon_list)} Pokemon = {total} images\n"
            f"Output : {out_dir}\n"
            f"Delay  : {delay}s between requests\n"
            f"ETA    : ~{total * delay / 60:.0f} min\n"
            f"API key: {'SET' if api_key else 'NOT SET'}\n"
        )

        done = skipped = failed = 0

        for pokemon in pokemon_list:
            dex: int    = pokemon.pokedex_number  # type: ignore[assignment]
            name: str   = pokemon.name
            chakra: str = (
                pokemon.primary_type.chakra_element.get_name_display()
                if pokemon.primary_type and pokemon.primary_type.chakra_element_id
                else pokemon.primary_type.name if pokemon.primary_type else "natural"
            )

            for variant in variants:
                filename   = f"{dex:03d}_{variant}.jpg"
                local_path = out_dir / filename

                if local_path.exists() and not force:
                    self.stdout.write(f"  SKIP  #{dex:03d} {name} [{variant}]")
                    skipped += 1
                    continue

                url = build_url(name, chakra, variant, seed=dex, api_key=api_key)

                if dry_run:
                    self.stdout.write(f"  WOULD #{dex:03d} {name} [{variant}] chakra={chakra}")
                    done += 1
                    continue

                # ── Download (key as query param, UA to avoid Cloudflare block) ─
                req = urllib.request.Request(
                    url, headers={"User-Agent": "Mozilla/5.0 (compatible; StickerBot/1.0)"}
                )
                try:
                    self.stdout.write(
                        f"  GET   #{dex:03d} {name} [{variant}] ...",
                        ending="",
                    )
                    self.stdout.flush()
                    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
                        local_path.write_bytes(resp.read())
                    size_kb = local_path.stat().st_size // 1024
                    self.stdout.write(f"  OK {size_kb} KB")
                    done += 1
                except urllib.error.HTTPError as exc:
                    self.stdout.write(f"  HTTP {exc.code}")
                    logger.warning("HTTP %d for %s [%s]", exc.code, name, variant)
                    failed += 1
                    if exc.code == 402:
                        self.stdout.write(self.style.ERROR(
                            "\n  Insufficient pollen balance. "
                            "Top up at https://enter.pollinations.ai then re-run.\n"
                        ))
                        return
                    if exc.code == 429:
                        self.stdout.write(self.style.WARNING("  Rate limited — sleeping 60s..."))
                        time.sleep(60)
                        continue
                except Exception as exc:
                    self.stdout.write(f"  FAIL  {exc}")
                    logger.warning("Failed %s [%s]: %s", name, variant, exc)
                    failed += 1

                time.sleep(delay)

        self.stdout.write(self.style.SUCCESS(
            f"\nDone.  Generated: {done}  Skipped: {skipped}  Failed: {failed}"
        ))
        if done and not dry_run:
            self.stdout.write(
                f"\nFiles saved to: {out_dir}\n"
                "Use in templates with:\n"
                "  {% load static %}\n"
                "  <img src=\"{% static 'stickers/generated/025_chibi.jpg' %}\">\n"
            )
