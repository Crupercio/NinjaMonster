"""Reusable collector arcade helpers for the Fun hub."""
from __future__ import annotations

import random
from dataclasses import dataclass
from math import floor

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.pokemon.models import Pokemon
from apps.users.services import award_ryo, get_candy_inventory, use_candy

SILHOUETTE_SESSION_KEY = "fun_silhouette_run"
SILHOUETTE_REVEAL_SESSION_KEY = "fun_silhouette_reveal"
MEMORY_SESSION_KEY = "fun_memory_run"
MEMORY_RESULT_SESSION_KEY = "fun_memory_result"

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
        base_ryo=120,
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
        base_ryo=220,
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
        base_ryo=350,
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
        base_ryo=500,
        base_dust=20,
        speed_target_seconds=115,
    ),
}


def get_silhouette_tower_catalog() -> list[SilhouetteTowerConfig]:
    """Return all silhouette towers in nav order."""
    return list(SILHOUETTE_TOWERS.values())


def get_memory_board_catalog() -> list[MemoryBoardConfig]:
    """Return all memory boards in display order."""
    return list(MEMORY_BOARDS.values())


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
