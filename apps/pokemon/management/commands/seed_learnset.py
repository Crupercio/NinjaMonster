"""
Management command: seed_learnset

Fetches each Pokemon's learnset from PokeAPI and stores it as JSON on
Pokemon.learnset. Caches move details so each unique move is only fetched once.

Usage:
    python manage.py seed_learnset
    python manage.py seed_learnset --start 1 --end 151   # Gen 1 only
    python manage.py seed_learnset --dex 1               # single Pokemon
"""
from __future__ import annotations

import time
import logging
from typing import Any

import requests
from django.core.management.base import BaseCommand

from apps.pokemon.models import Pokemon

logger = logging.getLogger(__name__)

POKEAPI_BASE = "https://pokeapi.co/api/v2"
SESSION = requests.Session()
SESSION.headers["User-Agent"] = "NinjaMonster/1.0"

# Version group to use for learn method filtering.
# We keep ALL methods but filter to a single modern version group so we
# don't show duplicated methods from 20+ games.
TARGET_VERSION_GROUP = "scarlet-violet"

# Fallback chain: if a Pokemon has no entries for the primary, try these.
VERSION_FALLBACKS = [
    "sword-shield",
    "brilliant-diamond-and-shining-pearl",
    "sun-moon",
    "x-y",
    "black-2-white-2",
    "black-white",
    "heartgold-soulsilver",
    "diamond-pearl",
    "firered-leafgreen",
    "ruby-sapphire",
    "crystal",
    "gold-silver",
    "red-blue",
]


def _get(url: str, retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            r = SESSION.get(url, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            if attempt == retries - 1:
                raise
            logger.warning("Retry %d for %s: %s", attempt + 1, url, exc)
            time.sleep(1.5 * (attempt + 1))
    return {}


def _fetch_move_detail(move_url: str, move_cache: dict) -> dict | None:
    if move_url in move_cache:
        return move_cache[move_url]
    try:
        data = _get(move_url)
        type_name = data.get("type", {}).get("name", "normal").title()
        damage_class = data.get("damage_class", {}).get("name", "status")
        power = data.get("power") or 0
        accuracy = data.get("accuracy") or 0
        pp = data.get("pp") or 0

        # Pick English effect entry
        effect = ""
        for e in data.get("effect_entries", []):
            if e.get("language", {}).get("name") == "en":
                effect = e.get("short_effect", "")
                break

        result = {
            "type": type_name,
            "damage_class": damage_class,
            "power": power,
            "accuracy": accuracy,
            "pp": pp,
            "effect": effect,
        }
        move_cache[move_url] = result
        return result
    except Exception as exc:
        logger.error("Failed to fetch move %s: %s", move_url, exc)
        move_cache[move_url] = None
        return None


def _pick_version_group(move_versions: list[dict]) -> str:
    available = {vd["version_group"]["name"] for vd in move_versions}
    if TARGET_VERSION_GROUP in available:
        return TARGET_VERSION_GROUP
    for vg in VERSION_FALLBACKS:
        if vg in available:
            return vg
    # Last resort: just use whatever is available
    return move_versions[0]["version_group"]["name"] if move_versions else ""


def _build_learnset(pokemon_data: dict, move_cache: dict) -> list[dict]:
    moves_raw = pokemon_data.get("moves", [])
    learnset: list[dict] = []

    for entry in moves_raw:
        move_info = entry.get("move", {})
        move_name = move_info.get("name", "").replace("-", " ").title()
        move_url = move_info.get("url", "")
        version_details = entry.get("version_group_details", [])

        if not version_details:
            continue

        # Pick the best version group this Pokemon has entries for
        vg = _pick_version_group(version_details)
        vg_entries = [v for v in version_details if v["version_group"]["name"] == vg]

        learn_methods: list[str] = []
        level = 0
        for vd in vg_entries:
            method = vd.get("move_learn_method", {}).get("name", "")
            if method not in learn_methods:
                learn_methods.append(method)
            if method == "level-up":
                level = max(level, vd.get("level_learned_at", 0))

        if not learn_methods:
            continue

        detail = _fetch_move_detail(move_url, move_cache)
        if detail is None:
            continue

        learnset.append({
            "name": move_name,
            "type": detail["type"],
            "damage_class": detail["damage_class"],
            "power": detail["power"],
            "accuracy": detail["accuracy"],
            "pp": detail["pp"],
            "effect": detail["effect"],
            "learn_methods": learn_methods,
            "level": level,
        })

    # Sort: level-up moves first (by level), then alphabetical for others
    def sort_key(m: dict) -> tuple:
        has_levelup = "level-up" in m["learn_methods"]
        return (0 if has_levelup else 1, m["level"] if has_levelup else 0, m["name"])

    learnset.sort(key=sort_key)
    return learnset


class Command(BaseCommand):
    help = "Seed Pokemon.learnset from PokeAPI"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--start", type=int, default=1)
        parser.add_argument("--end", type=int, default=905)
        parser.add_argument("--dex", type=int, default=None, help="Single dex number")

    def handle(self, *args: Any, **options: Any) -> None:
        if options["dex"]:
            qs = Pokemon.objects.filter(pokedex_number=options["dex"])
        else:
            qs = Pokemon.objects.filter(
                pokedex_number__gte=options["start"],
                pokedex_number__lte=options["end"],
            ).order_by("pokedex_number")

        total = qs.count()
        self.stdout.write(f"Seeding learnsets for {total} Pokemon...")

        move_cache: dict = {}
        done = 0

        for pokemon in qs:
            try:
                url = f"{POKEAPI_BASE}/pokemon/{pokemon.pokedex_number}/"
                data = _get(url)
                learnset = _build_learnset(data, move_cache)
                pokemon.learnset = learnset
                pokemon.save(update_fields=["learnset"])
                done += 1
                self.stdout.write(
                    f"  [{done}/{total}] {pokemon.name}: {len(learnset)} moves "
                    f"(move cache: {len(move_cache)})"
                )
            except Exception as exc:
                self.stderr.write(f"  ERROR {pokemon.name}: {exc}")

        self.stdout.write(self.style.SUCCESS(f"Done. {done}/{total} Pokemon updated."))
