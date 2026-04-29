"""Reusable collector arcade helpers for the Fun hub."""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import timedelta
from math import floor

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.game.models import (
    LoteriaBoardTemplate,
    LoteriaMode,
    LoteriaPrizeClaim,
    LoteriaRoom,
    LoteriaRoomEntry,
    LoteriaRoomParticipant,
    LoteriaStatus,
)
from apps.pokemon.models import Pokemon
from apps.users.services import award_ryo, deduct_ryo, get_candy_inventory, use_candy

SILHOUETTE_SESSION_KEY = "fun_silhouette_run"
SILHOUETTE_REVEAL_SESSION_KEY = "fun_silhouette_reveal"
MEMORY_SESSION_KEY = "fun_memory_run"
MEMORY_RESULT_SESSION_KEY = "fun_memory_result"
LOTERIA_STARTER_BOARD_TITLE_SUFFIX = "Starter Board"
LOTERIA_PRIVATE_ENTRY_FEE_RYO = 500
LOTERIA_ROOM_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
LOTERIA_SHARED_PAUSE_SECONDS = 600
LOTERIA_FIRST_CALL_DELAY_SECONDS = 15

User = get_user_model()


@dataclass(frozen=True)
class SilhouetteTowerConfig:
    """Config for one silhouette tower."""

    key: str
    title: str
    subtitle: str
    scope_label: str
    description: str
    pool_dex_numbers: tuple[int, ...]
    pool_target_size: int
    floor_rewards: tuple[int, ...]
    entry_candy_type: str
    image_name: str
    entry_qty: int = 1
    enabled: bool = False

    @property
    def pool_size(self) -> int:
        return self.pool_target_size or len(self.pool_dex_numbers)

    @property
    def max_floors(self) -> int:
        return len(self.floor_rewards)

    @property
    def max_bank(self) -> int:
        return sum(self.floor_rewards)

    @property
    def entry_label(self) -> str:
        labels = {
            "trail_mix": "Trail Mix",
            "sweet_berry": "Sweet Berry",
            "golden_apple": "Golden Apple",
        }
        return labels.get(self.entry_candy_type, self.entry_candy_type.replace("_", " ").title())


@dataclass(frozen=True)
class MemoryBoardConfig:
    """Config for one memory board."""

    key: str
    title: str
    subtitle: str
    description: str
    rows: int
    cols: int
    entry_candy_type: str
    base_ryo: int
    base_dust: int
    speed_target_seconds: int
    image_name: str = "memory_game_logo.png"
    entry_qty: int = 1
    enabled: bool = True

    @property
    def total_cards(self) -> int:
        return self.rows * self.cols

    @property
    def pair_count(self) -> int:
        return self.total_cards // 2

    @property
    def entry_label(self) -> str:
        labels = {
            "trail_mix": "Trail Mix",
            "sweet_berry": "Sweet Berry",
            "golden_apple": "Golden Apple",
        }
        return labels.get(self.entry_candy_type, self.entry_candy_type.replace("_", " ").title())


@dataclass(frozen=True)
class LoteriaDeckConfig:
    """Config for one Loteria generation room."""

    key: str
    title: str
    subtitle: str
    description: str
    region_label: str
    deck_dex_numbers: tuple[int, ...]
    entry_candy_type: str
    entry_qty_per_board: int
    max_saved_boards: int
    board_rows: int = 4
    board_cols: int = 4
    lobby_countdown_seconds: int = 10
    draw_interval_seconds: int = 4
    quick_play_prizes: dict[int, int] | None = None
    quick_play_entry_fees: dict[int, int] | None = None
    prize_boost_per_player_board: int = 150
    enabled: bool = True
    logo_image: str = "loteria_game_logo.png"

    @property
    def board_size(self) -> int:
        return self.board_rows * self.board_cols

    @property
    def deck_size(self) -> int:
        return len(self.deck_dex_numbers)

    @property
    def entry_label(self) -> str:
        labels = {
            "trail_mix": "Trail Mix",
            "sweet_berry": "Sweet Berry",
            "golden_apple": "Golden Apple",
        }
        return labels.get(self.entry_candy_type, self.entry_candy_type.replace("_", " ").title())

    def prize_for_npc_count(self, npc_count: int) -> int:
        """Return the base room prize for a quick-play NPC table."""
        prize_map = self.quick_play_prizes or {2: 900, 4: 1500, 6: 2400}
        return prize_map.get(npc_count, prize_map[max(prize_map)])

    def entry_fee_for_npc_count(self, npc_count: int) -> int:
        """Return the extra Ryo fee to open one quick-play NPC table."""
        fee_map = self.quick_play_entry_fees or {2: 100, 4: 300, 6: 600}
        return fee_map.get(npc_count, fee_map[max(fee_map)])


ROOKIE_25_DEXES: tuple[int, ...] = (
    1, 4, 7, 10, 16, 19, 25, 39, 52, 54,
    58, 63, 66, 74, 81, 92, 95, 104, 113, 120,
    123, 129, 131, 133, 150,
)


def build_floor_rewards(total_floors: int, base_reward: int, step_reward: int, milestone_every: int, milestone_bonus: int) -> tuple[int, ...]:
    """Generate a gently escalating reward table for long silhouette towers."""
    rewards: list[int] = []
    for floor in range(1, total_floors + 1):
        reward = base_reward + ((floor - 1) * step_reward) + (((floor - 1) // milestone_every) * milestone_bonus)
        rewards.append(int(reward))
    return tuple(rewards)

SILHOUETTE_TOWERS: dict[str, SilhouetteTowerConfig] = {
    "rookie": SilhouetteTowerConfig(
        key="rookie",
        title="Rookie Tower",
        subtitle="25 iconic Pokemon",
        scope_label="Kanto only",
        description=(
            "Climb a beginner-friendly silhouette tower built from the most recognizable faces "
            "in the collection. Cash out after any correct guess or push your luck for a bigger prize."
        ),
        pool_dex_numbers=ROOKIE_25_DEXES,
        pool_target_size=25,
        floor_rewards=(
            20, 25, 30, 35, 40,
            50, 60, 70, 80, 90,
            100, 120, 140, 160, 180,
            200, 225, 250, 275, 300,
            350, 400, 450, 525, 650,
        ),
        entry_candy_type="trail_mix",
        image_name="tower_rookie.png",
        entry_qty=3,
        enabled=True,
    ),
    "regional_100": SilhouetteTowerConfig(
        key="regional_100",
        title="Regional Tower",
        subtitle="100 Pokemon",
        scope_label="All generations",
        description="A broader collector climb that samples from the full national pool instead of staying inside Kanto.",
        pool_dex_numbers=(),
        pool_target_size=100,
        floor_rewards=build_floor_rewards(100, 30, 2, 10, 6),
        entry_candy_type="sweet_berry",
        image_name="tower_regional.png",
        entry_qty=3,
        enabled=True,
    ),
    "master_500": SilhouetteTowerConfig(
        key="master_500",
        title="Master Tower",
        subtitle="500 Pokemon",
        scope_label="All generations",
        description="A long-form silhouette gauntlet for players who want a real collector marathon with bigger payouts.",
        pool_dex_numbers=(),
        pool_target_size=500,
        floor_rewards=build_floor_rewards(500, 26, 1, 20, 5),
        entry_candy_type="golden_apple",
        image_name="tower_master.png",
        entry_qty=3,
        enabled=True,
    ),
    "national_905": SilhouetteTowerConfig(
        key="national_905",
        title="National Tower",
        subtitle="905 Pokemon",
        scope_label="All generations",
        description="The full nostalgia gauntlet. Every generation, every floor, and no regional shortcuts.",
        pool_dex_numbers=(),
        pool_target_size=905,
        floor_rewards=build_floor_rewards(905, 24, 1, 25, 6),
        entry_candy_type="golden_apple",
        image_name="tower_national.png",
        entry_qty=3,
        enabled=True,
    ),
}

MEMORY_BOARDS: dict[str, MemoryBoardConfig] = {
    "rookie_3x4": MemoryBoardConfig(
        key="rookie_3x4",
        title="Rookie Board",
        subtitle="3 x 4 classic pairs",
        description="A fast warm-up board for quick collector clears and low-pressure daily play.",
        rows=3,
        cols=4,
        entry_candy_type="trail_mix",
        entry_qty=1,
        base_ryo=600,
        base_dust=5,
        speed_target_seconds=45,
    ),
    "standard_4x4": MemoryBoardConfig(
        key="standard_4x4",
        title="Standard Board",
        subtitle="4 x 4 sticker memory",
        description="The clean default cabinet. More pairs, better payout, and still easy to finish in one sitting.",
        rows=4,
        cols=4,
        entry_candy_type="trail_mix",
        entry_qty=1,
        base_ryo=800,
        base_dust=10,
        speed_target_seconds=65,
    ),
    "collector_4x5": MemoryBoardConfig(
        key="collector_4x5",
        title="Collector Board",
        subtitle="4 x 5 steady grind",
        description="A denser card spread built for players who want stronger rewards without moving into marathon territory.",
        rows=4,
        cols=5,
        entry_candy_type="sweet_berry",
        entry_qty=1,
        base_ryo=1000,
        base_dust=15,
        speed_target_seconds=90,
    ),
    "master_6x4": MemoryBoardConfig(
        key="master_6x4",
        title="Master Board",
        subtitle="6 x 4 long clear",
        description="A full collector table with the best reliable memory payout in the arcade lane.",
        rows=4,
        cols=6,
        entry_candy_type="golden_apple",
        entry_qty=1,
        base_ryo=2400,
        base_dust=20,
        speed_target_seconds=115,
    ),
}

KANTO_LOTERIA_DEXES: tuple[int, ...] = tuple(range(1, 152))

LOTERIA_DECKS: dict[str, LoteriaDeckConfig] = {
    "kanto": LoteriaDeckConfig(
        key="kanto",
        title="Kanto Loteria",
        subtitle="4 x 4 event board",
        description=(
            "A live collector table built around classic Kanto calls, shared prize splits, "
            "and full-board wins. Bring up to three saved boards and let the room mark matches for you."
        ),
        region_label="Generation 1 · Kanto",
        deck_dex_numbers=KANTO_LOTERIA_DEXES,
        entry_candy_type="trail_mix",
        entry_qty_per_board=1,
        max_saved_boards=3,
        lobby_countdown_seconds=10,
        draw_interval_seconds=4,
        quick_play_prizes={2: 900, 4: 1500, 6: 2400},
        quick_play_entry_fees={2: 100, 4: 300, 6: 600},
        prize_boost_per_player_board=150,
    ),
}

LOTERIA_NPC_NAMES: tuple[str, ...] = (
    "Collector Mina",
    "Bug Catcher Theo",
    "Lass Emi",
    "Card Shark Jo",
    "Arcade Ren",
    "Camper Yumi",
)

LOTERIA_PATTERN_ORDER: tuple[str, ...] = (
    "chorro",
    "centrito",
    "cuatro_esquinas",
    "buena",
)
LOTERIA_PATTERN_LABELS: dict[str, str] = {
    "chorro": "Chorro",
    "centrito": "Centrito",
    "cuatro_esquinas": "Cuatro Esquinas",
    "buena": "Buena",
}
LOTERIA_PATTERN_PREVIEW_CELLS: dict[str, tuple[int, ...]] = {
    "chorro": (0, 1, 2, 3),
    "centrito": (5, 6, 9, 10),
    "cuatro_esquinas": (0, 3, 12, 15),
    "buena": tuple(range(16)),
}


def get_silhouette_tower_catalog() -> list[SilhouetteTowerConfig]:
    """Return all silhouette towers in nav order."""
    return list(SILHOUETTE_TOWERS.values())


def get_memory_board_catalog() -> list[MemoryBoardConfig]:
    """Return all memory boards in display order."""
    return list(MEMORY_BOARDS.values())


def get_loteria_deck_catalog() -> list[LoteriaDeckConfig]:
    """Return configured Loteria decks in hub order."""
    return list(LOTERIA_DECKS.values())


def get_silhouette_tower_config(tower_key: str) -> SilhouetteTowerConfig:
    """Fetch a configured tower by key."""
    try:
        return SILHOUETTE_TOWERS[tower_key]
    except KeyError as exc:
        raise ValueError(f"Unknown silhouette tower: {tower_key}") from exc


def get_memory_board_config(board_key: str) -> MemoryBoardConfig:
    """Fetch a configured memory board by key."""
    try:
        return MEMORY_BOARDS[board_key]
    except KeyError as exc:
        raise ValueError(f"Unknown memory board: {board_key}") from exc


def get_loteria_deck_config(deck_key: str) -> LoteriaDeckConfig:
    """Fetch a configured Loteria deck by key."""
    try:
        return LOTERIA_DECKS[deck_key]
    except KeyError as exc:
        raise ValueError(f"Unknown loteria deck: {deck_key}") from exc


def get_silhouette_run_state(session) -> dict | None:
    """Return the current silhouette run state from session storage."""
    return session.get(SILHOUETTE_SESSION_KEY)


def save_silhouette_run_state(session, run_state: dict) -> None:
    """Persist the current silhouette run state."""
    session[SILHOUETTE_SESSION_KEY] = run_state
    session.modified = True


def clear_silhouette_run_state(session) -> None:
    """Clear the current silhouette run state."""
    if SILHOUETTE_SESSION_KEY in session:
        session.pop(SILHOUETTE_SESSION_KEY, None)
        session.modified = True


def get_silhouette_reveal_state(session) -> dict | None:
    """Return the current silhouette reveal state from session storage."""
    return session.get(SILHOUETTE_REVEAL_SESSION_KEY)


def save_silhouette_reveal_state(session, reveal_state: dict) -> None:
    """Persist the current silhouette reveal state."""
    session[SILHOUETTE_REVEAL_SESSION_KEY] = reveal_state
    session.modified = True


def clear_silhouette_reveal_state(session) -> None:
    """Clear the current silhouette reveal state."""
    if SILHOUETTE_REVEAL_SESSION_KEY in session:
        session.pop(SILHOUETTE_REVEAL_SESSION_KEY, None)
        session.modified = True


def get_memory_run_state(session) -> dict | None:
    """Return the current memory run state from session storage."""
    return session.get(MEMORY_SESSION_KEY)


def save_memory_run_state(session, run_state: dict) -> None:
    """Persist the current memory run state."""
    session[MEMORY_SESSION_KEY] = run_state
    session.modified = True


def clear_memory_run_state(session) -> None:
    """Clear the active memory run."""
    if MEMORY_SESSION_KEY in session:
        session.pop(MEMORY_SESSION_KEY, None)
        session.modified = True


def get_memory_result_state(session) -> dict | None:
    """Return the last memory result state from session storage."""
    return session.get(MEMORY_RESULT_SESSION_KEY)


def save_memory_result_state(session, result_state: dict) -> None:
    """Persist the last memory result summary."""
    session[MEMORY_RESULT_SESSION_KEY] = result_state
    session.modified = True


def clear_memory_result_state(session) -> None:
    """Clear the last memory result summary."""
    if MEMORY_RESULT_SESSION_KEY in session:
        session.pop(MEMORY_RESULT_SESSION_KEY, None)
        session.modified = True


def get_fun_hub_context(user) -> dict:
    """Shared hub context for the Fun home page."""
    candy = get_candy_inventory(user)
    active_run = None
    return {
        "candy_inventory": candy,
        "active_silhouette_run": active_run,
    }


def get_loteria_species_queryset(config: LoteriaDeckConfig):
    """Base queryset for one Loteria deck's available species."""
    return (
        Pokemon.objects.filter(pokedex_number__in=config.deck_dex_numbers)
        .exclude(pokedex_number__isnull=True)
        .exclude(sprite_url="")
        .only("id", "name", "pokedex_number", "sprite_url")
        .order_by("pokedex_number")
    )


def get_loteria_species_map(config: LoteriaDeckConfig) -> dict[int, Pokemon]:
    """Return a species map keyed by Pokemon id for one Loteria deck."""
    return {pokemon.id: pokemon for pokemon in get_loteria_species_queryset(config)}


def get_user_owned_loteria_species(user, config: LoteriaDeckConfig) -> list[Pokemon]:
    """Return unique owned level-20+ species that are valid for this deck."""
    return list(
        Pokemon.objects.filter(
            owned_instances__owner=user,
            owned_instances__level__gte=20,
            pokedex_number__in=config.deck_dex_numbers,
        )
        .exclude(sprite_url="")
        .distinct()
        .only("id", "name", "pokedex_number", "sprite_url")
        .order_by("pokedex_number")
    )


def _random_board_species_ids_from_pool(pool_species_ids: list[int], board_size: int) -> list[int]:
    """Pick a full 4x4 board from a species pool."""
    if len(pool_species_ids) < board_size:
        raise ValueError(f"Loteria needs at least {board_size} Pokemon to build a board.")
    return random.sample(pool_species_ids, board_size)


def _next_available_board_slot(user, config: LoteriaDeckConfig) -> int | None:
    """Find the next open saved board slot for this deck."""
    used_slots = set(
        LoteriaBoardTemplate.objects.filter(
            owner=user,
            deck_key=config.key,
            seeded_by_system=False,
        ).values_list("board_slot", flat=True)
    )
    for slot in range(1, config.max_saved_boards + 1):
        if slot not in used_slots:
            return slot
    return None


def get_loteria_starter_board_slot(config: LoteriaDeckConfig) -> int:
    """Return the reserved slot number used for the locked starter board."""
    return config.max_saved_boards + 1


def get_loteria_board_label(board_slot: int, *, seeded_by_system: bool = False) -> str:
    """Return the fixed label used for one board slot."""
    if seeded_by_system:
        return LOTERIA_STARTER_BOARD_TITLE_SUFFIX
    return f"Board {board_slot}"


def get_loteria_entry_display_name(user, board_slot: int, *, seeded_by_system: bool = False) -> str:
    """Return the live-room display name for one player's board entry."""
    user_label = getattr(user, "username", "Player")
    return f"{user_label} - {get_loteria_board_label(board_slot, seeded_by_system=seeded_by_system)}"


def ensure_default_loteria_board(user, config: LoteriaDeckConfig) -> None:
    """Seed one random locked starter board the first time a user opens the deck."""
    starter_slot = get_loteria_starter_board_slot(config)
    starter_board = (
        LoteriaBoardTemplate.objects.filter(
            owner=user,
            deck_key=config.key,
            seeded_by_system=True,
        )
        .order_by("created_at", "pk")
        .first()
    )
    if starter_board:
        if starter_board.board_slot != starter_slot:
            starter_board.board_slot = starter_slot
            starter_board.save(update_fields=["board_slot", "updated_at"])
        return

    species_ids = list(get_loteria_species_queryset(config).values_list("id", flat=True))
    if len(species_ids) < config.board_size:
        return

    LoteriaBoardTemplate.objects.create(
        owner=user,
        deck_key=config.key,
        board_slot=starter_slot,
        title=get_loteria_board_label(starter_slot, seeded_by_system=True),
        species_ids=_random_board_species_ids_from_pool(species_ids, config.board_size),
        seeded_by_system=True,
    )


def get_user_loteria_boards(user, config: LoteriaDeckConfig):
    """Return the user's editable custom boards for this deck."""
    return list(
        LoteriaBoardTemplate.objects.filter(
            owner=user,
            deck_key=config.key,
            seeded_by_system=False,
            board_slot__lte=config.max_saved_boards,
        ).order_by("board_slot", "pk")
    )


def get_user_loteria_starter_board(user, config: LoteriaDeckConfig) -> LoteriaBoardTemplate | None:
    """Return the locked starter board for this deck, if one exists."""
    return (
        LoteriaBoardTemplate.objects.filter(
            owner=user,
            deck_key=config.key,
            seeded_by_system=True,
        )
        .order_by("created_at", "pk")
        .first()
    )


def save_loteria_board_template(user, config: LoteriaDeckConfig, *, board_slot: int, title: str, species_ids: list[int]) -> LoteriaBoardTemplate:
    """Create or update one saved Loteria board from owned level-20+ species."""
    if board_slot < 1 or board_slot > config.max_saved_boards:
        raise ValueError("That board slot is outside the allowed save range.")

    clean_species_ids = [int(species_id) for species_id in species_ids]
    if len(clean_species_ids) != config.board_size:
        raise ValueError(f"A {config.board_rows}x{config.board_cols} board needs exactly {config.board_size} Pokemon.")
    if len(set(clean_species_ids)) != config.board_size:
        raise ValueError("A Loteria board cannot repeat the same Pokemon.")

    owned_species_ids = set(
        Pokemon.objects.filter(
            id__in=clean_species_ids,
            owned_instances__owner=user,
            owned_instances__level__gte=20,
            pokedex_number__in=config.deck_dex_numbers,
        ).values_list("id", flat=True)
    )
    if owned_species_ids != set(clean_species_ids):
        raise ValueError("You can only build Loteria boards from Pokemon you own that are at least level 20.")

    board_title = get_loteria_board_label(board_slot, seeded_by_system=False)
    board, _created = LoteriaBoardTemplate.objects.update_or_create(
        owner=user,
        deck_key=config.key,
        board_slot=board_slot,
        defaults={
            "title": board_title,
            "species_ids": clean_species_ids,
            "seeded_by_system": False,
        },
    )
    return board


def _serialize_loteria_cells(species_ids: list[int], species_map: dict[int, Pokemon], called_species_ids: set[int]) -> list[dict]:
    """Turn a board's species ids into renderable cells."""
    cells: list[dict] = []
    for species_id in species_ids:
        pokemon = species_map.get(species_id)
        if pokemon is None:
            continue
        cells.append(
            {
                "id": pokemon.id,
                "name": pokemon.name,
                "dex": pokemon.pokedex_number,
                "image_url": pokemon.sprite_url or "",
                "marked": pokemon.id in called_species_ids,
            }
        )
    return cells


def serialize_loteria_board(board, species_map: dict[int, Pokemon], called_species_ids: set[int]) -> dict:
    """Convert a saved board or room entry into template-friendly data."""
    species_ids = list(board.species_ids)
    cells = _serialize_loteria_cells(species_ids, species_map, called_species_ids)
    marked_count = sum(1 for cell in cells if cell["marked"])
    board_slot = getattr(board, "board_slot", 1)
    seeded_by_system = getattr(board, "seeded_by_system", False)
    if not seeded_by_system:
        board_template = getattr(board, "board_template", None)
        seeded_by_system = bool(getattr(board_template, "seeded_by_system", False))
    return {
        "id": getattr(board, "id", None),
        "board_slot": board_slot,
        "title": get_loteria_board_label(board_slot, seeded_by_system=seeded_by_system),
        "cells": cells,
        "marked_count": marked_count,
        "board_size": len(cells),
        "is_complete": marked_count == len(cells) and bool(cells),
        "seeded_by_system": seeded_by_system,
    }


def _resolve_loteria_pause_state(room: LoteriaRoom, *, now=None) -> LoteriaRoom:
    """Expire or preserve the shared pause window for one active room."""
    if not room.paused_at:
        return room
    current_time = now or timezone.now()
    elapsed_seconds = max(0, int((current_time - room.paused_at).total_seconds()))
    if elapsed_seconds < room.pause_remaining_seconds:
        return room
    consumed_seconds = room.pause_remaining_seconds
    room.pause_remaining_seconds = 0
    room.paused_at = None
    if room.next_tick_at:
        room.next_tick_at = room.next_tick_at + timedelta(seconds=consumed_seconds)
    room.save(update_fields=["pause_remaining_seconds", "paused_at", "next_tick_at", "updated_at"])
    return room


@transaction.atomic
def toggle_loteria_pause(user, room: LoteriaRoom, *, pause: bool) -> LoteriaRoom:
    """Pause or resume one private/guild Loteria room using the shared timer budget."""
    if room.mode != LoteriaMode.PRIVATE:
        raise ValueError("Pause is only available in private or guild tables.")
    if room.status != LoteriaStatus.ACTIVE:
        raise ValueError("Only live Loteria rooms can be paused.")
    participant = room.participants.filter(user=user).first()
    if participant is None and room.created_by_id != user.id:
        raise ValueError("Join the table before changing the pause state.")

    room = _resolve_loteria_pause_state(room)
    if pause:
        if room.paused_at:
            raise ValueError("This Loteria table is already paused.")
        if room.pause_remaining_seconds <= 0:
            raise ValueError("This table already used the full 10-minute pause budget.")
        room.paused_at = timezone.now()
        room.save(update_fields=["paused_at", "updated_at"])
        return room

    if not room.paused_at:
        raise ValueError("This Loteria table is already running.")
    elapsed_seconds = max(0, int((timezone.now() - room.paused_at).total_seconds()))
    consumed_seconds = min(room.pause_remaining_seconds, elapsed_seconds)
    room.pause_remaining_seconds = max(0, room.pause_remaining_seconds - consumed_seconds)
    if room.next_tick_at:
        room.next_tick_at = room.next_tick_at + timedelta(seconds=consumed_seconds)
    room.paused_at = None
    room.save(update_fields=["pause_remaining_seconds", "paused_at", "next_tick_at", "updated_at"])
    return room


def _build_loteria_line_groups(config: LoteriaDeckConfig) -> list[tuple[int, ...]]:
    """Return every row, column, and diagonal for the current board shape."""
    rows = [
        tuple((row * config.board_cols) + col for col in range(config.board_cols))
        for row in range(config.board_rows)
    ]
    cols = [
        tuple((row * config.board_cols) + col for row in range(config.board_rows))
        for col in range(config.board_cols)
    ]
    diag_lr = tuple((idx * config.board_cols) + idx for idx in range(min(config.board_rows, config.board_cols)))
    diag_rl = tuple((idx * config.board_cols) + (config.board_cols - 1 - idx) for idx in range(min(config.board_rows, config.board_cols)))
    return rows + cols + [diag_lr, diag_rl]


def _loteria_pattern_groups(config: LoteriaDeckConfig) -> dict[str, list[tuple[int, ...]]]:
    """Return the board index groups that complete each named Loteria prize."""
    center_rows = [max(0, (config.board_rows // 2) - 1), min(config.board_rows - 1, config.board_rows // 2)]
    center_cols = [max(0, (config.board_cols // 2) - 1), min(config.board_cols - 1, config.board_cols // 2)]
    center_group = tuple((row * config.board_cols) + col for row in center_rows for col in center_cols)
    corner_group = (
        0,
        config.board_cols - 1,
        ((config.board_rows - 1) * config.board_cols),
        (config.board_rows * config.board_cols) - 1,
    )
    full_group = tuple(range(config.board_size))
    return {
        "chorro": _build_loteria_line_groups(config),
        "centrito": [center_group],
        "cuatro_esquinas": [corner_group],
        "buena": [full_group],
    }


def _entry_matches_pattern(entry: LoteriaRoomEntry, called_species_ids: set[int], config: LoteriaDeckConfig, pattern_key: str) -> bool:
    """True when a room entry has completed the named prize pattern."""
    groups = _loteria_pattern_groups(config).get(pattern_key, [])
    if not groups:
        return False
    species_ids = list(entry.species_ids)
    for group in groups:
        if all(index < len(species_ids) and species_ids[index] in called_species_ids for index in group):
            return True
    return False


def _split_pattern_reward(total_reward: int, winners: list[LoteriaRoomEntry]) -> list[dict]:
    """Split one room prize across tied winners while preserving the full amount."""
    if not winners or total_reward <= 0:
        return []
    base_share, remainder = divmod(total_reward, len(winners))
    allocations = []
    for index, winner in enumerate(winners):
        allocations.append(
            {
                "entry_id": winner.pk,
                "display_name": winner.display_name,
                "board_slot": winner.board_slot,
                "is_npc": winner.is_npc,
                "reward_ryo": base_share + (1 if index < remainder else 0),
            }
        )
    return allocations


def _build_loteria_split_summary(winner_count: int) -> str:
    """Return a short shared-winner summary for room pattern copy."""
    if winner_count <= 1:
        return ""
    return f"Split across {winner_count} boards"


def build_loteria_pattern_tracker(
    room: LoteriaRoom,
    config: LoteriaDeckConfig,
    viewer_user=None,
) -> list[dict]:
    """Return display-ready room prize states for the live tracker and results page."""
    claim_map = {str(claim.get("pattern_key")): claim for claim in room.pattern_claims}
    viewer_claim_map: dict[str, LoteriaPrizeClaim] = {}
    if viewer_user and getattr(viewer_user, "is_authenticated", False):
        viewer_claim_map = {
            claim.pattern_key: claim
            for claim in room.prize_claims.filter(user=viewer_user).select_related("entry")
        }

    tracker = []
    for pattern_key in LOTERIA_PATTERN_ORDER:
        claim = claim_map.get(pattern_key)
        reward_ryo = room.prize_pool_ryo if pattern_key == "buena" else room.side_pattern_reward_ryo
        winner_allocations = list(claim.get("winner_allocations", [])) if claim else []
        winner_names = [allocation.get("display_name", "Board") for allocation in winner_allocations]
        viewer_claim = viewer_claim_map.get(pattern_key)
        viewer_names = list(viewer_claim.winner_names_snapshot) if viewer_claim else []
        viewer_other_winners = [name for name in viewer_names if name != getattr(viewer_claim.entry, "display_name", "")]
        tracker.append(
            {
                "key": pattern_key,
                "label": LOTERIA_PATTERN_LABELS[pattern_key],
                "reward_ryo": int(claim.get("reward_ryo", reward_ryo)) if claim else int(reward_ryo),
                "preview_cells": list(LOTERIA_PATTERN_PREVIEW_CELLS[pattern_key]),
                "is_claimed": claim is not None,
                "winner_allocations": winner_allocations,
                "winner_names": winner_names,
                "winner_count": len(winner_allocations),
                "is_split": len(winner_allocations) > 1,
                "split_summary": _build_loteria_split_summary(len(winner_allocations)),
                "viewer_won": viewer_claim is not None,
                "viewer_claimed": bool(viewer_claim and viewer_claim.claimed_at),
                "viewer_claim_id": viewer_claim.pk if viewer_claim else None,
                "viewer_reward_ryo": viewer_claim.reward_ryo if viewer_claim else 0,
                "viewer_board_name": viewer_claim.entry.display_name if viewer_claim else "",
                "viewer_other_winners": viewer_other_winners,
                "viewer_other_winner_count": len(viewer_other_winners),
            }
        )
    return tracker


def get_user_pending_loteria_claims(user):
    """Return the caller's pending Loteria prize claims newest first."""
    return (
        LoteriaPrizeClaim.objects.filter(user=user, claimed_at__isnull=True)
        .select_related("room", "entry")
        .order_by("-created_at", "pk")
    )


@transaction.atomic
def claim_loteria_prize(user, claim_id: int, room: LoteriaRoom | None = None) -> LoteriaPrizeClaim:
    """Award one pending Loteria prize to its owner and mark it claimed."""
    queryset = (
        LoteriaPrizeClaim.objects.select_related("user", "room", "entry")
        .select_for_update()
        .filter(pk=claim_id, user=user)
    )
    if room is not None:
        queryset = queryset.filter(room=room)
    claim = queryset.first()
    if claim is None:
        raise ValueError("That Loteria prize is not available.")
    if claim.claimed_at:
        raise ValueError("That Loteria prize was already claimed.")
    award_ryo(user, claim.reward_ryo)
    claim.claimed_at = timezone.now()
    claim.save(update_fields=["claimed_at"])
    return claim


@transaction.atomic
def claim_all_loteria_prizes(user, room: LoteriaRoom | None = None) -> tuple[int, int]:
    """Claim all pending Loteria prizes for a user, optionally scoped to one room."""
    queryset = (
        LoteriaPrizeClaim.objects.select_related("room")
        .select_for_update()
        .filter(user=user, claimed_at__isnull=True)
        .order_by("created_at", "pk")
    )
    if room is not None:
        queryset = queryset.filter(room=room)
    claims = list(queryset)
    if not claims:
        raise ValueError("No unclaimed Loteria prizes are waiting.")
    total_ryo = sum(claim.reward_ryo for claim in claims)
    award_ryo(user, total_ryo)
    timestamp = timezone.now()
    LoteriaPrizeClaim.objects.filter(pk__in=[claim.pk for claim in claims]).update(claimed_at=timestamp)
    return len(claims), total_ryo


def _generate_loteria_room_code(length: int = 6) -> str:
    """Return a short human-shareable room code."""
    for _ in range(32):
        code = "".join(random.choices(LOTERIA_ROOM_CODE_ALPHABET, k=length))
        if not LoteriaRoom.objects.filter(room_code=code).exists():
            return code
    raise ValueError("Could not reserve a private Loteria room code right now.")


def _get_user_guild_membership(user):
    """Best-effort guild membership lookup without forcing callers to handle DoesNotExist."""
    try:
        return user.guild_membership
    except Exception:
        return None


def ensure_loteria_host_participant(room: LoteriaRoom) -> LoteriaRoomParticipant | None:
    """Mirror the room host into participant state so access/readiness stay consistent."""
    if not room.created_by_id:
        return None
    participant, created = LoteriaRoomParticipant.objects.get_or_create(
        room=room,
        user=room.created_by,
        defaults={"is_host": True, "is_ready": False},
    )
    if not participant.is_host:
        participant.is_host = True
        participant.save(update_fields=["is_host"])
    return participant


def get_loteria_room_participants(room: LoteriaRoom) -> list[LoteriaRoomParticipant]:
    """Return all room participants with the host normalized into the list."""
    ensure_loteria_host_participant(room)
    return list(room.participants.select_related("user").order_by("-is_host", "joined_at", "pk"))


def _configure_loteria_rewards(room: LoteriaRoom, config: LoteriaDeckConfig, player_board_count: int) -> tuple[int, int, int]:
    """Return buena reward, side reward, and per-board fee for the current room mode."""
    if room.mode == LoteriaMode.PRIVATE:
        entry_fee_ryo = room.entry_fee_ryo or LOTERIA_PRIVATE_ENTRY_FEE_RYO
        paid_board_count = max(player_board_count, 0)
        total_entry_fees = entry_fee_ryo * paid_board_count
        house_match_bonus = LOTERIA_PRIVATE_ENTRY_FEE_RYO * paid_board_count
        total_pot = total_entry_fees + house_match_bonus
        buena_reward = total_pot // 2
        side_pool = total_pot - buena_reward
        side_reward = side_pool // 3 if side_pool else 0
        buena_reward += side_pool - (side_reward * 3)
        return buena_reward, side_reward, entry_fee_ryo
    return (
        config.prize_for_npc_count(room.npc_count) + (config.prize_boost_per_player_board * player_board_count),
        1000,
        config.entry_fee_for_npc_count(room.npc_count),
    )


def _claim_loteria_patterns(room: LoteriaRoom, config: LoteriaDeckConfig, called_species_ids: set[int]) -> tuple[LoteriaRoom, bool]:
    """Resolve any newly won pattern prizes after a card call."""
    claimed_keys = {str(claim.get("pattern_key")) for claim in room.pattern_claims}
    room_entries = list(room.entries.select_related("user").order_by("entered_at", "pk"))
    claims = list(room.pattern_claims)
    buena_claimed = False
    for pattern_key in LOTERIA_PATTERN_ORDER:
        if pattern_key in claimed_keys:
            continue
        winners = [entry for entry in room_entries if _entry_matches_pattern(entry, called_species_ids, config, pattern_key)]
        if not winners:
            continue
        reward_ryo = room.prize_pool_ryo if pattern_key == "buena" else room.side_pattern_reward_ryo
        claims.append(
            {
                "pattern_key": pattern_key,
                "label": LOTERIA_PATTERN_LABELS[pattern_key],
                "reward_ryo": int(reward_ryo),
                "winner_allocations": _split_pattern_reward(int(reward_ryo), winners),
                "claimed_call_count": len(called_species_ids),
            }
        )
        claimed_keys.add(pattern_key)
        if pattern_key == "buena":
            buena_claimed = True
    if claims != list(room.pattern_claims):
        room.pattern_claims = claims
        room.save(update_fields=["pattern_claims", "updated_at"])
    return room, buena_claimed


def get_allowed_loteria_npc_counts(config: LoteriaDeckConfig) -> list[int]:
    """Return the supported quick-play NPC seat counts for a deck."""
    prize_map = config.quick_play_prizes or {}
    return sorted(prize_map.keys())


def get_user_open_loteria_room(user, config: LoteriaDeckConfig) -> LoteriaRoom | None:
    """Return the user's most recent unfinished room for this deck, if any."""
    return (
        LoteriaRoom.objects.filter(
            deck_key=config.key,
            status__in=[LoteriaStatus.DRAFT, LoteriaStatus.LOBBY, LoteriaStatus.ACTIVE],
        )
        .filter(
            Q(created_by=user) | Q(participants__user=user)
        )
        .distinct()
        .order_by("-created_at")
        .first()
    )


def get_user_recent_finished_loteria_room(user, config: LoteriaDeckConfig) -> LoteriaRoom | None:
    """Return the user's latest finished room for this deck."""
    return (
        LoteriaRoom.objects.filter(
            deck_key=config.key,
            status=LoteriaStatus.FINISHED,
        )
        .filter(
            Q(created_by=user) | Q(participants__user=user) | Q(entries__user=user)
        )
        .distinct()
        .order_by("-finished_at", "-created_at")
        .first()
    )


def _next_loteria_round_number(config: LoteriaDeckConfig) -> int:
    """Assign an incrementing room number per deck for display."""
    latest = LoteriaRoom.objects.filter(deck_key=config.key).order_by("-round_number").values_list("round_number", flat=True).first()
    return int(latest or 0) + 1


def _build_loteria_deck_order(config: LoteriaDeckConfig) -> list[int]:
    """Build a shuffled deal order for one room."""
    species_ids = list(get_loteria_species_queryset(config).values_list("id", flat=True))
    if len(species_ids) < config.board_size:
        raise ValueError(f"{config.title} needs at least {config.board_size} Pokemon with artwork before it can open.")
    random.shuffle(species_ids)
    return species_ids


@transaction.atomic
def create_quick_loteria_room(user, config: LoteriaDeckConfig, npc_count: int) -> LoteriaRoom:
    """Create a player-owned quick-play room against a chosen NPC count."""
    allowed_counts = get_allowed_loteria_npc_counts(config)
    if npc_count not in allowed_counts:
        raise ValueError("That NPC count is not available for this Loteria room.")

    open_room = get_user_open_loteria_room(user, config)
    if open_room:
        raise ValueError("Finish or abandon your current Loteria room before creating a new one.")

    room = LoteriaRoom.objects.create(
        created_by=user,
        deck_key=config.key,
        title=f"{config.title} Quick Play",
        mode=LoteriaMode.QUICK_NPC,
        status=LoteriaStatus.LOBBY,
        npc_count=npc_count,
        round_number=_next_loteria_round_number(config),
        prize_pool_ryo=0,
        entry_fee_ryo=config.entry_fee_for_npc_count(npc_count),
        deck_order=[],
        called_species_ids=[],
    )
    ensure_loteria_host_participant(room)
    return room


@transaction.atomic
def create_private_loteria_room(user, config: LoteriaDeckConfig, *, guild_only: bool = False) -> LoteriaRoom:
    """Create a private or guild-locked Loteria room with a share code."""
    open_room = get_user_open_loteria_room(user, config)
    if open_room:
        raise ValueError("Finish, leave, or abandon your current Loteria room before opening another one.")

    guild_membership = _get_user_guild_membership(user)
    if guild_only and guild_membership is None:
        raise ValueError("Join a guild before opening a guild-only Loteria room.")

    room = LoteriaRoom.objects.create(
        created_by=user,
        deck_key=config.key,
        title=f"{config.title} {'Guild Table' if guild_only else 'Private Table'}",
        mode=LoteriaMode.PRIVATE,
        status=LoteriaStatus.LOBBY,
        room_code=_generate_loteria_room_code(),
        guild=guild_membership.guild if guild_only and guild_membership else None,
        npc_count=0,
        round_number=_next_loteria_round_number(config),
        prize_pool_ryo=0,
        entry_fee_ryo=LOTERIA_PRIVATE_ENTRY_FEE_RYO,
        deck_order=[],
        called_species_ids=[],
    )
    ensure_loteria_host_participant(room)
    return room


@transaction.atomic
def join_private_loteria_room(user, config: LoteriaDeckConfig, room_code: str) -> LoteriaRoom:
    """Join a private or guild-locked Loteria room by code."""
    normalized_code = "".join(ch for ch in (room_code or "").upper() if ch.isalnum())
    if not normalized_code:
        raise ValueError("Enter a room code before joining a private Loteria table.")

    room = (
        LoteriaRoom.objects.select_related("guild", "created_by")
        .filter(
            deck_key=config.key,
            mode=LoteriaMode.PRIVATE,
            room_code=normalized_code,
            status__in=[LoteriaStatus.DRAFT, LoteriaStatus.LOBBY],
        )
        .first()
    )
    if room is None:
        raise ValueError("That private Loteria room code could not be found.")

    open_room = get_user_open_loteria_room(user, config)
    if open_room and open_room.pk != room.pk:
        raise ValueError("Leave, finish, or abandon your current Loteria room before joining another one.")

    if room.guild_id:
        membership = _get_user_guild_membership(user)
        if membership is None or membership.guild_id != room.guild_id:
            raise ValueError("This Loteria room is locked to guild members only.")

    participant, created = LoteriaRoomParticipant.objects.get_or_create(
        room=room,
        user=user,
        defaults={"is_host": room.created_by_id == user.id, "is_ready": False},
    )
    if not created and room.created_by_id == user.id and not participant.is_host:
        participant.is_host = True
        participant.save(update_fields=["is_host"])
    return room


def _ensure_exact_npc_entries(room: LoteriaRoom, config: LoteriaDeckConfig) -> None:
    """Create the configured NPC count for a room if they do not exist yet."""
    current_npcs = list(room.entries.filter(is_npc=True).order_by("entered_at", "pk"))
    if len(current_npcs) >= room.npc_count:
        return

    pool_species_ids = list(room.deck_order)
    used_names = set(room.entries.values_list("display_name", flat=True))
    for idx in range(len(current_npcs), room.npc_count):
        npc_name = LOTERIA_NPC_NAMES[idx % len(LOTERIA_NPC_NAMES)]
        suffix = 2
        while npc_name in used_names:
            npc_name = f"{LOTERIA_NPC_NAMES[idx % len(LOTERIA_NPC_NAMES)]} {suffix}"
            suffix += 1
        used_names.add(npc_name)
        LoteriaRoomEntry.objects.create(
            room=room,
            display_name=npc_name,
            board_slot=idx + 1,
            species_ids=_random_board_species_ids_from_pool(pool_species_ids, config.board_size),
            is_npc=True,
        )


def _board_entry_is_complete(entry: LoteriaRoomEntry, called_species_ids: set[int]) -> bool:
    """True when every tile on a board has been called."""
    return bool(entry.species_ids) and all(species_id in called_species_ids for species_id in entry.species_ids)


def _validate_loteria_board_templates(user, config: LoteriaDeckConfig, board_ids: list[int]) -> list[LoteriaBoardTemplate]:
    """Load and validate a user's selected Loteria boards."""
    cleaned_ids = [int(board_id) for board_id in board_ids]
    if not cleaned_ids:
        raise ValueError("Pick at least one saved board before continuing.")

    templates = list(
        LoteriaBoardTemplate.objects.filter(owner=user, deck_key=config.key, id__in=cleaned_ids).order_by("board_slot")
    )
    if len(templates) != len(set(cleaned_ids)):
        raise ValueError("One or more selected boards could not be found.")
    if len(templates) > config.max_saved_boards:
        raise ValueError(f"You can only bring up to {config.max_saved_boards} boards for your seat, starter included.")

    eligible_species_ids = set(
        Pokemon.objects.filter(
            owned_instances__owner=user,
            owned_instances__level__gte=20,
            pokedex_number__in=config.deck_dex_numbers,
        ).values_list("id", flat=True)
    )
    for board in templates:
        if board.seeded_by_system:
            continue
        if set(board.species_ids) - eligible_species_ids:
            raise ValueError(
                "One of the selected boards has Pokemon you no longer own at level 20 or higher. Edit the board first."
            )
    return templates


@transaction.atomic
def save_loteria_room_boards(user, room: LoteriaRoom, config: LoteriaDeckConfig, board_ids: list[int], *, mark_ready: bool = True) -> LoteriaRoomParticipant:
    """Save one participant's board selection for a room lobby."""
    if room.status not in [LoteriaStatus.DRAFT, LoteriaStatus.LOBBY]:
        raise ValueError("This Loteria room has already started.")
    if room.mode == LoteriaMode.PRIVATE and room.guild_id:
        membership = _get_user_guild_membership(user)
        if membership is None or membership.guild_id != room.guild_id:
            raise ValueError("This Loteria room is locked to guild members only.")

    templates = _validate_loteria_board_templates(user, config, board_ids)
    participant, _created = LoteriaRoomParticipant.objects.get_or_create(
        room=room,
        user=user,
        defaults={"is_host": room.created_by_id == user.id, "is_ready": False},
    )
    if room.created_by_id == user.id and not participant.is_host:
        participant.is_host = True

    room.entries.filter(user=user, is_npc=False).delete()
    for board in templates:
        LoteriaRoomEntry.objects.create(
            room=room,
            user=user,
            board_template=board,
            display_name=get_loteria_entry_display_name(user, board.board_slot, seeded_by_system=board.seeded_by_system),
            board_slot=board.board_slot,
            species_ids=list(board.species_ids),
            is_npc=False,
        )

    participant.is_ready = mark_ready
    participant.save(update_fields=["is_host", "is_ready"])
    return participant


@transaction.atomic
def set_loteria_room_participant_ready(user, room: LoteriaRoom, *, is_ready: bool) -> LoteriaRoomParticipant:
    """Toggle ready state for one participant inside a lobby."""
    participant = LoteriaRoomParticipant.objects.filter(room=room, user=user).first()
    if participant is None:
        raise ValueError("Join the room before changing your ready state.")
    if is_ready and not room.entries.filter(user=user, is_npc=False).exists():
        raise ValueError("Save at least one board before readying up.")
    participant.is_ready = is_ready
    participant.save(update_fields=["is_ready"])
    return participant


@transaction.atomic
def _finalize_loteria_room(room: LoteriaRoom, config: LoteriaDeckConfig) -> LoteriaRoom:
    """Lock winners, split rewards, and close the room."""
    if room.status == LoteriaStatus.FINISHED:
        return room

    called_species_ids = set(room.called_species_ids)
    room, _ = _claim_loteria_patterns(room, config, called_species_ids)
    entries = list(room.entries.select_related("user"))
    entry_map = {entry.pk: entry for entry in entries}
    buena_winner_ids = set()
    reward_totals: dict[int, int] = {}
    existing_claim_keys = set(
        LoteriaPrizeClaim.objects.filter(room=room).values_list("entry_id", "pattern_key")
    )
    created_claims: list[LoteriaPrizeClaim] = []

    for claim in room.pattern_claims:
        pattern_key = str(claim.get("pattern_key"))
        winner_allocations = list(claim.get("winner_allocations", []))
        winner_names = [allocation.get("display_name", "Board") for allocation in winner_allocations]
        for allocation in claim.get("winner_allocations", []):
            entry_id = int(allocation.get("entry_id", 0) or 0)
            reward_ryo = int(allocation.get("reward_ryo", 0) or 0)
            if entry_id <= 0 or reward_ryo <= 0:
                continue
            reward_totals[entry_id] = reward_totals.get(entry_id, 0) + reward_ryo
            if pattern_key == "buena":
                buena_winner_ids.add(entry_id)
            entry = entry_map.get(entry_id)
            if entry is None or entry.user_id is None or entry.is_npc:
                continue
            if (entry.pk, pattern_key) in existing_claim_keys:
                continue
            created_claims.append(
                LoteriaPrizeClaim(
                    room=room,
                    entry=entry,
                    user=entry.user,
                    pattern_key=pattern_key,
                    pattern_label=str(claim.get("label", LOTERIA_PATTERN_LABELS.get(pattern_key, pattern_key.title()))),
                    reward_ryo=reward_ryo,
                    shared_winner_count=max(1, len(winner_allocations)),
                    winner_names_snapshot=winner_names,
                )
            )
            existing_claim_keys.add((entry.pk, pattern_key))

    for entry in entries:
        entry.reward_ryo = reward_totals.get(entry.pk, 0)
        entry.is_winner = entry.pk in buena_winner_ids
        entry.save(update_fields=["is_winner", "reward_ryo"])

    if created_claims:
        LoteriaPrizeClaim.objects.bulk_create(created_claims)

    room.status = LoteriaStatus.FINISHED
    room.finished_at = timezone.now()
    room.next_tick_at = None
    room.save(update_fields=["status", "finished_at", "next_tick_at", "updated_at"])
    return room


def advance_loteria_room(room: LoteriaRoom, config: LoteriaDeckConfig) -> LoteriaRoom:
    """Advance an active room up to the current time."""
    now = timezone.now()
    room = _resolve_loteria_pause_state(room, now=now)

    if room.status != LoteriaStatus.ACTIVE or not room.next_tick_at or room.paused_at:
        return room

    deck_order = list(room.deck_order)
    called_species_ids = list(room.called_species_ids)

    while room.status == LoteriaStatus.ACTIVE and room.next_tick_at and now >= room.next_tick_at:
        next_index = len(called_species_ids)
        if next_index >= len(deck_order):
            room = _finalize_loteria_room(room, config)
            break

        called_species_ids.append(deck_order[next_index])
        room.called_species_ids = called_species_ids
        room.next_tick_at = room.next_tick_at + timedelta(seconds=config.draw_interval_seconds)
        room.save(update_fields=["called_species_ids", "next_tick_at", "updated_at"])

        called_set = set(called_species_ids)
        room, buena_claimed = _claim_loteria_patterns(room, config, called_set)
        if buena_claimed or any(_board_entry_is_complete(entry, called_set) for entry in room.entries.all()):
            room = _finalize_loteria_room(room, config)
            break

    return room


@transaction.atomic
def start_loteria_room(user, room: LoteriaRoom, config: LoteriaDeckConfig, board_ids: list[int] | None = None) -> LoteriaRoom:
    """Lock in boards, charge entry costs, and start the room countdown."""
    if room.created_by_id != user.id:
        raise ValueError("Only the room host can start this Loteria match.")
    if room.status not in [LoteriaStatus.DRAFT, LoteriaStatus.LOBBY]:
        raise ValueError("This room has already started.")

    if room.mode == LoteriaMode.PRIVATE:
        participants = get_loteria_room_participants(room)
        if not participants:
            raise ValueError("Invite at least one player before starting a private Loteria room.")
        if any(not participant.is_ready for participant in participants):
            raise ValueError("Every joined player must save boards and ready up before the host can start the table.")

        human_entries = list(
            room.entries.filter(user__isnull=False, is_npc=False).select_related("user", "board_template").order_by("user_id", "board_slot")
        )
        if not human_entries:
            raise ValueError("This private table has no saved boards yet.")

        board_counts: dict[int, int] = {}
        for entry in human_entries:
            if entry.user_id is None:
                continue
            board_counts[entry.user_id] = board_counts.get(entry.user_id, 0) + 1
            entry.reward_ryo = 0
            entry.is_winner = False
            entry.save(update_fields=["reward_ryo", "is_winner"])

        for participant in participants:
            board_count = board_counts.get(participant.user_id, 0)
            if board_count <= 0:
                raise ValueError(f"{participant.user} still needs to bring at least one board to the room.")
            if board_count > config.max_saved_boards:
                raise ValueError(f"Each player can only bring up to {config.max_saved_boards} boards into a private table.")
            deduct_ryo(participant.user, (room.entry_fee_ryo or LOTERIA_PRIVATE_ENTRY_FEE_RYO) * board_count)

        room.entries.filter(is_npc=True).delete()
        player_board_count = len(human_entries)
    else:
        selected_board_ids = list(board_ids or [])
        templates = _validate_loteria_board_templates(user, config, selected_board_ids)
        quick_play_fee_ryo = room.entry_fee_ryo or config.entry_fee_for_npc_count(room.npc_count)
        if quick_play_fee_ryo > 0:
            deduct_ryo(user, quick_play_fee_ryo)
        for _ in range(len(templates) * config.entry_qty_per_board):
            use_candy(user, config.entry_candy_type)
        save_loteria_room_boards(user, room, config, selected_board_ids, mark_ready=True)
        room.entries.filter(is_npc=False).update(reward_ryo=0, is_winner=False)
        player_board_count = len(templates)

    buena_reward, side_reward, entry_fee_ryo = _configure_loteria_rewards(room, config, player_board_count)
    room.deck_order = _build_loteria_deck_order(config)
    room.called_species_ids = []
    room.pattern_claims = []
    room.entry_fee_ryo = entry_fee_ryo
    room.side_pattern_reward_ryo = side_reward
    room.prize_pool_ryo = buena_reward
    room.status = LoteriaStatus.ACTIVE
    room.started_at = timezone.now()
    room.finished_at = None
    room.pause_remaining_seconds = LOTERIA_SHARED_PAUSE_SECONDS
    room.paused_at = None
    room.next_tick_at = room.started_at + timedelta(seconds=LOTERIA_FIRST_CALL_DELAY_SECONDS)
    room.save(
        update_fields=[
            "deck_order",
            "called_species_ids",
            "pattern_claims",
            "entry_fee_ryo",
            "side_pattern_reward_ryo",
            "prize_pool_ryo",
            "status",
            "started_at",
            "finished_at",
            "pause_remaining_seconds",
            "paused_at",
            "next_tick_at",
            "updated_at",
        ]
    )
    if room.mode == LoteriaMode.QUICK_NPC:
        _ensure_exact_npc_entries(room, config)
    return room


@transaction.atomic
def abandon_loteria_room(user, room: LoteriaRoom) -> None:
    """Drop a room or leave it, depending on whether the caller is the host."""
    if room.status == LoteriaStatus.FINISHED:
        raise ValueError("This room is already finished.")
    if room.created_by_id == user.id:
        room.entries.all().delete()
        room.participants.all().delete()
        room.delete()
        return

    participant = LoteriaRoomParticipant.objects.filter(room=room, user=user).first()
    if participant is None:
        raise ValueError("You are not part of this Loteria room.")
    if room.status == LoteriaStatus.ACTIVE:
        raise ValueError("This room is already live. The host has to finish or abandon it.")

    room.entries.filter(user=user, is_npc=False).delete()
    participant.delete()


def get_tower_species_map(config: SilhouetteTowerConfig) -> dict[int, Pokemon]:
    """Load and map species for a tower pool by dex number."""
    if config.pool_dex_numbers:
        queryset = Pokemon.objects.filter(pokedex_number__in=config.pool_dex_numbers)
    else:
        queryset = Pokemon.objects.exclude(pokedex_number__isnull=True)

    species = list(
        queryset
        .only("id", "name", "pokedex_number", "sprite_url")
        .order_by("pokedex_number")
    )
    return {pokemon.pokedex_number: pokemon for pokemon in species if pokemon.pokedex_number is not None}


def get_random_silhouette_species(count: int) -> list[Pokemon]:
    """Return a few random Pokemon to use as decorative silhouette accents."""
    return list(
        Pokemon.objects.exclude(pokedex_number__isnull=True)
        .exclude(sprite_url="")
        .order_by("?")[:count]
        .only("id", "name", "pokedex_number", "sprite_url")
    )


def get_random_memory_species(count: int) -> list[Pokemon]:
    """Return random Pokemon with sprite art for memory boards."""
    return list(
        Pokemon.objects.exclude(pokedex_number__isnull=True)
        .exclude(sprite_url="")
        .order_by("?")[:count]
        .only("id", "name", "pokedex_number", "sprite_url")
    )


def build_tower_pool_dex_numbers(config: SilhouetteTowerConfig) -> list[int]:
    """Build the concrete dex pool for a run from the configured tower source."""
    if config.pool_dex_numbers:
        pool_dex_numbers = sorted(config.pool_dex_numbers)
        if len(pool_dex_numbers) < 6:
            raise ValueError("This tower needs at least 6 configured Pokemon before it can open.")
        return pool_dex_numbers

    available_dex_numbers = list(
        Pokemon.objects.exclude(pokedex_number__isnull=True)
        .values_list("pokedex_number", flat=True)
        .distinct()
    )
    available_dex_numbers = [dex for dex in available_dex_numbers if dex is not None]
    if len(available_dex_numbers) < max(6, config.pool_target_size):
        raise ValueError(
            f"{config.title} needs at least {config.pool_target_size} Pokemon with silhouettes before it can open."
        )
    selected = random.sample(available_dex_numbers, k=config.pool_target_size)
    return sorted(selected)


def _build_memory_board_cards(config: MemoryBoardConfig) -> list[dict]:
    """Build a shuffled set of duplicate pairs for one memory run."""
    species_pool = get_random_memory_species(config.pair_count)
    if len(species_pool) < config.pair_count:
        raise ValueError(f"{config.title} needs at least {config.pair_count} Pokemon with sprites before it can open.")

    cards: list[dict] = []
    for idx, pokemon in enumerate(species_pool, start=1):
        for copy in range(2):
            cards.append(
                {
                    "card_id": f"{pokemon.pokedex_number}-{copy}",
                    "pair_id": idx,
                    "dex": pokemon.pokedex_number,
                    "name": pokemon.name,
                    "image_url": pokemon.sprite_url or "",
                }
            )
    random.shuffle(cards)
    return cards


def _grade_memory_run(config: MemoryBoardConfig, turns: int, elapsed_seconds: int) -> tuple[str, int, int]:
    """Return grade plus reward bonuses for a completed memory run."""
    perfect_turns = config.pair_count
    bonus_ryo = 0
    bonus_dust = 0

    if turns <= perfect_turns:
        grade = "Perfect"
        bonus_ryo += max(40, floor(config.base_ryo * 0.35))
        bonus_dust += max(3, floor(config.base_dust * 0.5))
    elif turns <= perfect_turns + 3:
        grade = "Great"
        bonus_ryo += max(24, floor(config.base_ryo * 0.2))
        bonus_dust += max(2, floor(config.base_dust * 0.3))
    elif turns <= perfect_turns + 6:
        grade = "Good"
        bonus_ryo += max(12, floor(config.base_ryo * 0.1))
    else:
        grade = "Clear"

    if elapsed_seconds <= config.speed_target_seconds:
        bonus_ryo += max(18, floor(config.base_ryo * 0.15))
        bonus_dust += max(1, floor(config.base_dust * 0.2))

    return grade, bonus_ryo, bonus_dust


def make_silhouette_question(pool_dex_numbers: list[int], asked_dex_numbers: list[int]) -> dict | None:
    """Build one 6-choice silhouette question from the tower pool."""
    remaining = [dex for dex in pool_dex_numbers if dex not in asked_dex_numbers]
    if not remaining:
        return None

    correct_dex = random.choice(remaining)
    distractors = random.sample([dex for dex in pool_dex_numbers if dex != correct_dex], k=5)
    option_dex_numbers = distractors + [correct_dex]
    random.shuffle(option_dex_numbers)
    return {
        "correct_dex": correct_dex,
        "option_dex_numbers": option_dex_numbers,
    }


def start_silhouette_run(user, session, config: SilhouetteTowerConfig) -> dict:
    """Consume entry candy and create a fresh silhouette run."""
    if not config.enabled:
        raise ValueError("This tower is not open yet.")

    field = f"candy_{config.entry_candy_type}"
    user.refresh_from_db(fields=[field])
    if getattr(user, field) < config.entry_qty:
        raise ValueError(f"You need {config.entry_qty} {config.entry_label} to enter {config.title}.")

    for _ in range(config.entry_qty):
        use_candy(user, config.entry_candy_type)

    pool_dex_numbers = build_tower_pool_dex_numbers(config)

    question = make_silhouette_question(pool_dex_numbers, [])
    if question is None:
        raise ValueError("This tower has no Pokemon configured yet.")

    run_state = {
        "tower_key": config.key,
        "pool_dex_numbers": pool_dex_numbers,
        "current_floor": 1,
        "banked_ryo": 0,
        "asked_dex_numbers": [],
        "question": question,
    }
    clear_silhouette_reveal_state(session)
    save_silhouette_run_state(session, run_state)
    return run_state


def start_memory_run(user, session, config: MemoryBoardConfig) -> dict:
    """Consume candy and create a fresh memory board run."""
    if not config.enabled:
        raise ValueError("This memory board is not open yet.")

    field = f"candy_{config.entry_candy_type}"
    user.refresh_from_db(fields=[field])
    if getattr(user, field) < config.entry_qty:
        raise ValueError(f"You need {config.entry_qty} {config.entry_label} to enter {config.title}.")

    for _ in range(config.entry_qty):
        use_candy(user, config.entry_candy_type)

    run_state = {
        "board_key": config.key,
        "cards": _build_memory_board_cards(config),
        "started_at": timezone.now().isoformat(),
    }
    clear_memory_result_state(session)
    save_memory_run_state(session, run_state)
    return run_state


@transaction.atomic
def complete_memory_run(user, session, config: MemoryBoardConfig, run_state: dict, *, turns: int, elapsed_seconds: int, best_streak: int) -> dict:
    """Finalize a memory run and award Ryo plus dust."""
    turns = max(config.pair_count, int(turns))
    elapsed_seconds = max(1, int(elapsed_seconds))
    best_streak = max(0, int(best_streak))

    grade, bonus_ryo, bonus_dust = _grade_memory_run(config, turns, elapsed_seconds)
    if best_streak >= config.pair_count:
        bonus_dust += max(1, floor(config.base_dust * 0.25))

    total_ryo = config.base_ryo + bonus_ryo
    total_dust = config.base_dust + bonus_dust

    award_ryo(user, total_ryo)
    # Dust does not have a shared helper yet, so keep the update local and atomic.
    User.objects.filter(pk=user.pk).update(sticker_dust=F("sticker_dust") + total_dust)
    user.refresh_from_db(fields=["ryo", "sticker_dust"])

    result_state = {
        "board_key": config.key,
        "grade": grade,
        "turns": turns,
        "elapsed_seconds": elapsed_seconds,
        "best_streak": best_streak,
        "reward_ryo": total_ryo,
        "reward_dust": total_dust,
    }
    clear_memory_run_state(session)
    save_memory_result_state(session, result_state)
    return result_state


def abandon_memory_run(session) -> None:
    """Drop the active memory run without awarding anything."""
    clear_memory_run_state(session)


def cash_out_silhouette_run(user, session, run_state: dict) -> int:
    """Award the full banked total and close the run."""
    payout = int(run_state.get("banked_ryo", 0))
    if payout > 0:
        award_ryo(user, payout)
    clear_silhouette_run_state(session)
    clear_silhouette_reveal_state(session)
    return payout


def answer_silhouette_question(user, session, config: SilhouetteTowerConfig, run_state: dict, selected_dex: int) -> dict:
    """Resolve one guess and update or close the run."""
    question = run_state.get("question") or {}
    correct_dex = int(question.get("correct_dex", 0))
    if correct_dex == 0:
        raise ValueError("This run has no active question.")

    if selected_dex == correct_dex:
        reward = config.floor_rewards[run_state["current_floor"] - 1]
        asked = [*run_state["asked_dex_numbers"], correct_dex]
        banked_ryo = int(run_state["banked_ryo"]) + reward
        next_floor = int(run_state["current_floor"]) + 1

        if next_floor > config.max_floors:
            award_ryo(user, banked_ryo)
            clear_silhouette_run_state(session)
            save_silhouette_reveal_state(
                session,
                {
                    "tower_key": config.key,
                    "status": "cleared",
                    "selected_dex": selected_dex,
                    "correct_dex": correct_dex,
                    "option_dex_numbers": question.get("option_dex_numbers", []),
                    "reward": reward,
                    "payout": banked_ryo,
                    "banked_ryo": banked_ryo,
                    "floor_answered": run_state["current_floor"],
                },
            )
            return {
                "status": "cleared",
                "reward": reward,
                "payout": banked_ryo,
                "correct_dex": correct_dex,
            }

        next_question = make_silhouette_question(run_state["pool_dex_numbers"], asked)
        if next_question is None:
            award_ryo(user, banked_ryo)
            clear_silhouette_run_state(session)
            save_silhouette_reveal_state(
                session,
                {
                    "tower_key": config.key,
                    "status": "cleared",
                    "selected_dex": selected_dex,
                    "correct_dex": correct_dex,
                    "option_dex_numbers": question.get("option_dex_numbers", []),
                    "reward": reward,
                    "payout": banked_ryo,
                    "banked_ryo": banked_ryo,
                    "floor_answered": run_state["current_floor"],
                },
            )
            return {
                "status": "cleared",
                "reward": reward,
                "payout": banked_ryo,
                "correct_dex": correct_dex,
            }

        clear_silhouette_run_state(session)
        save_silhouette_reveal_state(
            session,
            {
                "tower_key": config.key,
                "status": "correct",
                "selected_dex": selected_dex,
                "correct_dex": correct_dex,
                "option_dex_numbers": question.get("option_dex_numbers", []),
                "reward": reward,
                "banked_ryo": banked_ryo,
                "floor_answered": run_state["current_floor"],
                "next_run_state": {
                    "tower_key": config.key,
                    "pool_dex_numbers": run_state["pool_dex_numbers"],
                    "current_floor": next_floor,
                    "banked_ryo": banked_ryo,
                    "asked_dex_numbers": asked,
                    "question": next_question,
                },
            },
        )
        return {
            "status": "correct",
            "reward": reward,
            "banked_ryo": banked_ryo,
            "correct_dex": correct_dex,
        }

    payout = int(run_state.get("banked_ryo", 0)) // 2
    if payout > 0:
        award_ryo(user, payout)
    clear_silhouette_run_state(session)
    save_silhouette_reveal_state(
        session,
        {
            "tower_key": config.key,
            "status": "wrong",
            "selected_dex": selected_dex,
            "correct_dex": correct_dex,
            "option_dex_numbers": question.get("option_dex_numbers", []),
            "payout": payout,
            "banked_ryo": int(run_state.get("banked_ryo", 0)),
            "floor_answered": run_state["current_floor"],
        },
    )
    return {
        "status": "wrong",
        "payout": payout,
        "correct_dex": correct_dex,
    }


def advance_silhouette_run(session, tower_key: str) -> dict:
    """Promote a pending next question after a reveal has finished."""
    reveal_state = get_silhouette_reveal_state(session)
    if not reveal_state or reveal_state.get("tower_key") != tower_key:
        raise ValueError("There is no pending reveal to advance.")

    next_run_state = reveal_state.get("next_run_state")
    if not next_run_state:
        raise ValueError("This reveal does not have a next floor to advance to.")

    save_silhouette_run_state(session, next_run_state)
    clear_silhouette_reveal_state(session)
    return next_run_state
