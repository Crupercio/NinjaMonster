"""Sticker collection scoring and leaderboard helpers."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from django.contrib.auth import get_user_model

from apps.pokemon.models import Pokemon

from .models import REGION_RANGES, Sticker, StickerRarity, StickerVariant
from .services import _COMPLETION_RARITIES, _COMPLETION_VARIANTS

User = get_user_model()

RARITY_POINTS: dict[str, int] = {
    StickerRarity.COMMON: 10,
    StickerRarity.UNCOMMON: 20,
    StickerRarity.RARE: 35,
    StickerRarity.EPIC: 55,
    StickerRarity.PRISMATIC: 85,
    StickerRarity.FULL_ART: 125,
    StickerRarity.SECRET_RARE: 180,
}

VARIANT_MULTIPLIERS: dict[str, float] = {
    StickerVariant.BASE: 1.00,
    StickerVariant.SHINY: 1.10,
    StickerVariant.BATTLE_SCENE: 1.15,
    StickerVariant.WATERCOLOR: 1.18,
    StickerVariant.TV_90S: 1.20,
    StickerVariant.CARTOON: 1.20,
    StickerVariant.COLOR_SWAP: 1.25,
    StickerVariant.SKETCH: 1.25,
    StickerVariant.BURN_SCROLL: 1.25,
    StickerVariant.NEON_GLOW: 1.40,
    StickerVariant.GLITTER: 1.40,
    StickerVariant.HOLOGRAPHIC: 1.40,
    StickerVariant.CHROME: 1.40,
    StickerVariant.ANIME: 1.80,
}

ROW_BONUS_RATE = 0.15
COLUMN_BONUS_RATE = 0.20
GENERATION_BONUS_RATE = 0.40
PAGE_SIZE = 15
PAGE_COLUMNS = 5


@dataclass(frozen=True)
class PlacementRecord:
    """Serializable placement metadata used for scoring."""

    pokemon_id: int
    pokedex_number: int
    rarity: str
    variant: str


@dataclass(frozen=True)
class StickerCollectionStats:
    """Computed sticker collection metrics for a user or guild."""

    soul_bound_count: int
    sticker_score: int
    row_completions: int
    row_bonus: int
    column_completions: int
    column_bonus: int
    generation_completions: int
    generation_bonus: int
    total_score: int


def _region_for_dex(pokedex_number: int) -> str | None:
    for region, (low, high) in REGION_RANGES.items():
        if low <= pokedex_number <= high:
            return region
    return None


def _score_slot(rarity: str, variant: str) -> int:
    base = RARITY_POINTS.get(rarity, 0)
    multiplier = VARIANT_MULTIPLIERS.get(variant, 1.0)
    return round(base * multiplier)


def _build_album_layout() -> tuple[
    dict[int, tuple[str, int, int, int]],
    dict[tuple[str, int, int], int],
    dict[tuple[str, int, int], int],
    dict[str, int],
]:
    """
    Return layout metadata for row/column/generation completion checks.

    Maps pokemon_id -> (region, page_number, row_number, column_number).
    """
    pokemon_rows = list(
        Pokemon.objects.exclude(pokedex_number__isnull=True)
        .values("id", "pokedex_number")
        .order_by("pokedex_number")
    )

    by_region: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for row in pokemon_rows:
        dex = int(row["pokedex_number"])
        region = _region_for_dex(dex)
        if region is None:
            continue
        by_region[region].append((int(row["id"]), dex))

    pokemon_positions: dict[int, tuple[str, int, int, int]] = {}
    row_targets: dict[tuple[str, int, int], int] = defaultdict(int)
    column_targets: dict[tuple[str, int, int], int] = defaultdict(int)
    region_slot_totals: dict[str, int] = {}

    for region, entries in by_region.items():
        for index, (pokemon_id, _dex) in enumerate(entries):
            page_number = index // PAGE_SIZE + 1
            slot_index = index % PAGE_SIZE
            row_number = slot_index // PAGE_COLUMNS + 1
            column_number = slot_index % PAGE_COLUMNS + 1
            pokemon_positions[pokemon_id] = (region, page_number, row_number, column_number)
            row_targets[(region, page_number, row_number)] += 1
            column_targets[(region, page_number, column_number)] += 1

        region_slot_totals[region] = (
            len(entries) * len(_COMPLETION_RARITIES) * len(_COMPLETION_VARIANTS)
        )

    return pokemon_positions, row_targets, column_targets, region_slot_totals


def build_collection_stats(records: list[PlacementRecord]) -> StickerCollectionStats:
    """Compute score and completion metrics from a list of soul-bound placements."""
    (
        pokemon_positions,
        row_targets,
        column_targets,
        region_slot_totals,
    ) = _build_album_layout()

    slot_groups_by_row: dict[tuple[str, int, str, str, int], list[int]] = defaultdict(list)
    slot_groups_by_column: dict[tuple[str, int, str, str, int], list[int]] = defaultdict(list)
    region_scores: dict[str, int] = defaultdict(int)
    region_counts: dict[str, int] = defaultdict(int)

    sticker_score = 0
    for record in records:
        position = pokemon_positions.get(record.pokemon_id)
        if position is None:
            continue
        region, page_number, row_number, column_number = position
        points = _score_slot(record.rarity, record.variant)
        sticker_score += points
        region_scores[region] += points
        region_counts[region] += 1
        slot_groups_by_row[(region, page_number, record.rarity, record.variant, row_number)].append(points)
        slot_groups_by_column[(region, page_number, record.rarity, record.variant, column_number)].append(points)

    row_completions = 0
    row_bonus = 0
    for key, points in slot_groups_by_row.items():
        region, page_number, _rarity, _variant, row_number = key
        if len(points) == row_targets[(region, page_number, row_number)]:
            row_completions += 1
            row_bonus += round(sum(points) * ROW_BONUS_RATE)

    column_completions = 0
    column_bonus = 0
    for key, points in slot_groups_by_column.items():
        region, page_number, _rarity, _variant, column_number = key
        if len(points) == column_targets[(region, page_number, column_number)]:
            column_completions += 1
            column_bonus += round(sum(points) * COLUMN_BONUS_RATE)

    generation_completions = 0
    generation_bonus = 0
    for region, total_slots in region_slot_totals.items():
        if total_slots > 0 and region_counts.get(region, 0) == total_slots:
            generation_completions += 1
            generation_bonus += round(region_scores.get(region, 0) * GENERATION_BONUS_RATE)

    total_score = sticker_score + row_bonus + column_bonus + generation_bonus
    return StickerCollectionStats(
        soul_bound_count=len(records),
        sticker_score=sticker_score,
        row_completions=row_completions,
        row_bonus=row_bonus,
        column_completions=column_completions,
        column_bonus=column_bonus,
        generation_completions=generation_completions,
        generation_bonus=generation_bonus,
        total_score=total_score,
    )


def build_personal_collection_stats(user) -> StickerCollectionStats:
    """Return collection stats for a user's personal soul-bound placements."""
    records = [
        PlacementRecord(
            pokemon_id=row["pokemon_id"],
            pokedex_number=row["pokemon__pokedex_number"],
            rarity=row["rarity"],
            variant=row["variant"],
        )
        for row in Sticker.objects.filter(owner=user, is_album_placed=True).values(
            "pokemon_id",
            "pokemon__pokedex_number",
            "rarity",
            "variant",
        )
        if row["pokemon__pokedex_number"] is not None
    ]
    return build_collection_stats(records)


def build_user_leaderboard(limit: int = 100) -> list[dict]:
    """Build the sticker-first leaderboard ordered by album score."""
    placements_by_user: dict[int, list[PlacementRecord]] = defaultdict(list)
    placement_rows = Sticker.objects.filter(is_album_placed=True).values(
        "owner_id",
        "pokemon_id",
        "pokemon__pokedex_number",
        "rarity",
        "variant",
    )

    for row in placement_rows:
        dex = row["pokemon__pokedex_number"]
        if dex is None:
            continue
        placements_by_user[int(row["owner_id"])].append(
            PlacementRecord(
                pokemon_id=int(row["pokemon_id"]),
                pokedex_number=int(dex),
                rarity=row["rarity"],
                variant=row["variant"],
            )
        )

    if not placements_by_user:
        return []

    users = {
        user.pk: user
        for user in User.objects.filter(pk__in=placements_by_user.keys()).only(
            "id",
            "username",
            "display_name",
        )
    }

    rows: list[dict] = []
    for user_id, placements in placements_by_user.items():
        user = users.get(user_id)
        if user is None:
            continue
        stats = build_collection_stats(placements)
        rows.append(
            {
                "user": user,
                "display_name": user.display_name or user.username,
                "stats": stats,
            }
        )

    rows.sort(
        key=lambda row: (
            -row["stats"].total_score,
            -row["stats"].generation_completions,
            -row["stats"].column_completions,
            -row["stats"].row_completions,
            -row["stats"].soul_bound_count,
            row["user"].username.lower(),
        )
    )
    return rows[:limit]
