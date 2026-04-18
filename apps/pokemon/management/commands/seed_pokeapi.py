"""
Management command: seed Pokemon species from PokeAPI (Gen 2–8, dex #152–905).

Pulls name, types, base stats, and generation from the public PokeAPI REST API.
Assigns placeholder moves using the same TYPE_MOVES mapping as seed_gen1.
Sets generation_sources M2M and the new generation FK.

Usage:
    python manage.py seed_pokeapi                    # all 152–905
    python manage.py seed_pokeapi --start 152 --end 251   # Johto only
    python manage.py seed_pokeapi --all              # 1–905 (including Gen 1)

Safe to re-run — uses get_or_create so no duplicates are created.
Existing Pokemon keep their moves; only newly created ones get defaults assigned.

Note: Makes ~2 HTTP requests per Pokemon (~1,500 total). Expect ~20–30 minutes.
      Use --start/--end to process in batches if interrupted.
"""
import logging
import time
import urllib.error
import urllib.request
import json

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.pokemon.models import Generation, Move, Pokemon, PokemonType, SpeciesMovePool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PokeAPI endpoints
# ---------------------------------------------------------------------------
POKEAPI_POKEMON = "https://pokeapi.co/api/v2/pokemon/{num}"
POKEAPI_SPECIES = "https://pokeapi.co/api/v2/pokemon-species/{num}"

# ---------------------------------------------------------------------------
# Type → default move PKs (same as seed_gen1 — placeholder until rework)
# ---------------------------------------------------------------------------
TYPE_MOVES: dict[str, list[int]] = {
    "Normal":   [1, 2, 3],
    "Fire":     [6, 4, 41],
    "Water":    [9, 10, 11],
    "Electric": [13, 14, 16],
    "Grass":    [18, 20, 21],
    "Ice":      [23, 26, 27],
    "Fighting": [1, 42, 53],
    "Poison":   [28, 29, 30],
    "Ground":   [1, 44, 2],
    "Flying":   [1, 3, 38],
    "Psychic":  [36, 43, 48],
    "Bug":      [1, 2, 45],
    "Rock":     [1, 2, 3],
    "Ghost":    [32, 33, 35],
    "Dragon":   [38, 23, 3],
    "Dark":     [39, 40, 47],
    "Steel":    [1, 2, 3],
    "Fairy":    [1, 3, 2],
}

# PokeAPI generation name → our Generation number
GENERATION_MAP: dict[str, int] = {
    "generation-i":   1,
    "generation-ii":  2,
    "generation-iii": 3,
    "generation-iv":  4,
    "generation-v":   5,
    "generation-vi":  6,
    "generation-vii": 7,
    "generation-viii": 8,
    "generation-ix":  9,
}

GENERATION_NAMES: dict[int, str] = {
    1: "Generation I",
    2: "Generation II",
    3: "Generation III",
    4: "Generation IV",
    5: "Generation V",
    6: "Generation VI",
    7: "Generation VII",
    8: "Generation VIII",
    9: "Generation IX",
}


def _fetch_json(url: str) -> dict | None:
    """Fetch JSON from a URL. Returns None on failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "NinjaMonsterApp/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return None


def _get_or_create_generation(number: int) -> Generation:
    gen, _ = Generation.objects.get_or_create(
        number=number,
        defaults={"name": GENERATION_NAMES.get(number, f"Generation {number}")},
    )
    return gen


def _assign_placeholder_moves(pokemon: Pokemon, primary_type_name: str) -> None:
    """Assign default type-based placeholder moves to a newly created species."""
    move_pks = TYPE_MOVES.get(primary_type_name, TYPE_MOVES["Normal"])
    existing_moves = set(
        SpeciesMovePool.objects.filter(species=pokemon).values_list("move_id", flat=True)
    )
    slot_types = ["standard", "chase", "special"]
    for slot, pk in zip(slot_types, move_pks):
        if pk not in existing_moves:
            try:
                move = Move.objects.get(pk=pk)
                SpeciesMovePool.objects.get_or_create(
                    species=pokemon,
                    slot_type=slot,
                    defaults={"move": move},
                )
            except Move.DoesNotExist:
                logger.warning("Placeholder move pk=%d not found for %s", pk, pokemon.name)


class Command(BaseCommand):
    help = "Seed Pokemon species (Gen 2–8) from the public PokeAPI REST API."

    def add_arguments(self, parser: object) -> None:
        parser.add_argument(
            "--start",
            type=int,
            default=152,
            help="First dex number to seed (default: 152).",
        )
        parser.add_argument(
            "--end",
            type=int,
            default=905,
            help="Last dex number to seed (default: 905).",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Seed all 1–905 (overrides --start/--end).",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=0.3,
            help="Seconds to wait between API calls (default: 0.3). Reduce to speed up.",
        )

    def handle(self, *args: object, **options: object) -> None:
        start: int = 1 if options["all"] else options["start"]
        end: int = 905 if options["all"] else options["end"]
        delay: float = options["delay"]

        self.stdout.write(f"Seeding Pokemon #{start}–#{end} from PokeAPI…")
        self.stdout.write(f"Estimated time: ~{int((end - start + 1) * delay * 2 / 60)} minutes\n")

        # Pre-cache types and generations to minimise DB hits
        type_cache: dict[str, PokemonType] = {
            t.name: t for t in PokemonType.objects.all()
        }
        gen_cache: dict[int, Generation] = {
            g.number: g for g in Generation.objects.all()
        }

        created_count = 0
        updated_count = 0
        failed_count = 0

        for num in range(start, end + 1):
            # ── Fetch pokemon data ──────────────────────────────────────────
            poke_data = _fetch_json(POKEAPI_POKEMON.format(num=num))
            if poke_data is None:
                self.stdout.write(self.style.WARNING(f"  SKIP #{num:03d} — pokemon data unavailable"))
                failed_count += 1
                time.sleep(delay)
                continue

            time.sleep(delay)

            # ── Fetch species data (for generation) ─────────────────────────
            species_data = _fetch_json(POKEAPI_SPECIES.format(num=num))
            if species_data is None:
                self.stdout.write(self.style.WARNING(f"  SKIP #{num:03d} — species data unavailable"))
                failed_count += 1
                time.sleep(delay)
                continue

            time.sleep(delay)

            # ── Parse fields ────────────────────────────────────────────────
            name: str = poke_data["name"].replace("-", " ").title()
            # Use the official English name if available
            for entry in species_data.get("names", []):
                if entry.get("language", {}).get("name") == "en":
                    name = entry["name"]
                    break

            # Types
            types_raw = sorted(poke_data["types"], key=lambda x: x["slot"])
            primary_type_name: str = types_raw[0]["type"]["name"].title()
            secondary_type_name: str | None = (
                types_raw[1]["type"]["name"].title() if len(types_raw) > 1 else None
            )

            # Stats — PokeAPI stat name → our field
            stat_map = {
                "hp": "base_hp",
                "attack": "base_attack",
                "defense": "base_defense",
                "special-attack": "base_ninjutsu",
                "special-defense": "base_sp_defense",
                "speed": "base_initiative",
            }
            stats: dict[str, int] = {}
            for stat_entry in poke_data["stats"]:
                stat_name = stat_entry["stat"]["name"]
                if stat_name in stat_map:
                    stats[stat_map[stat_name]] = stat_entry["base_stat"]

            # Generation
            gen_api_name: str = species_data.get("generation", {}).get("name", "generation-i")
            gen_number: int = GENERATION_MAP.get(gen_api_name, 1)

            if gen_number not in gen_cache:
                gen_cache[gen_number] = _get_or_create_generation(gen_number)
            generation = gen_cache[gen_number]

            # Types — get or create
            if primary_type_name not in type_cache:
                primary_type, _ = PokemonType.objects.get_or_create(name=primary_type_name)
                type_cache[primary_type_name] = primary_type
            primary_type = type_cache[primary_type_name]

            secondary_type = None
            if secondary_type_name:
                if secondary_type_name not in type_cache:
                    sec_type, _ = PokemonType.objects.get_or_create(name=secondary_type_name)
                    type_cache[secondary_type_name] = sec_type
                secondary_type = type_cache[secondary_type_name]

            # ── Create or update Pokemon ────────────────────────────────────
            with transaction.atomic():
                pokemon, created = Pokemon.objects.get_or_create(
                    pokedex_number=num,
                    defaults={
                        "name": name,
                        "primary_type": primary_type,
                        "secondary_type": secondary_type,
                        "base_hp": stats.get("base_hp", 45),
                        "base_attack": stats.get("base_attack", 45),
                        "base_defense": stats.get("base_defense", 45),
                        "base_ninjutsu": stats.get("base_ninjutsu", 45),
                        "base_sp_defense": stats.get("base_sp_defense", 45),
                        "base_initiative": stats.get("base_initiative", 45),
                        "generation": generation,
                    },
                )

                if created:
                    # Set generation source M2M
                    pokemon.generation_sources.add(generation)
                    # Assign placeholder moves
                    _assign_placeholder_moves(pokemon, primary_type_name)
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  + #{num:03d} {name} ({primary_type_name}"
                            f"{f'/{secondary_type_name}' if secondary_type_name else ''}"
                            f") Gen {gen_number}"
                        )
                    )
                else:
                    # Backfill generation FK if missing
                    needs_save = False
                    if pokemon.generation_id is None:
                        pokemon.generation = generation
                        needs_save = True
                    if pokemon.name != name and not Pokemon.objects.filter(
                        name=name
                    ).exclude(pk=pokemon.pk).exists():
                        pokemon.name = name
                        needs_save = True
                    if needs_save:
                        pokemon.save(update_fields=["generation", "name"])
                    if not pokemon.generation_sources.filter(pk=generation.pk).exists():
                        pokemon.generation_sources.add(generation)
                    updated_count += 1
                    self.stdout.write(f"  ~ #{num:03d} {name} (exists)")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. Created: {created_count} | Updated: {updated_count} | Failed: {failed_count}"
            )
        )
        self.stdout.write("Run 'python manage.py download_sprites' to fetch artwork locally.")
