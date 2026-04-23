"""Tests for the collector arcade memory game."""
import pytest
from django.urls import reverse

from apps.game.fun import MEMORY_RESULT_SESSION_KEY, MEMORY_SESSION_KEY, get_memory_board_config
from tests.framework.factories.pokemon_factory import PokemonFactory
from tests.framework.factories.user_factory import UserFactory


def _seed_memory_species(total: int) -> None:
    for dex in range(1, total + 1):
        PokemonFactory(
            pokedex_number=dex,
            name=f"Mon{dex}",
            sprite_url=f"/media/pokemon/sprites/{dex:03d}.png",
        )


@pytest.mark.django_db
def test_memory_hub_loads_board_catalog(client):
    user = UserFactory(candy_trail_mix=2, candy_sweet_berry=1, candy_golden_apple=1)
    user.save()
    client.force_login(user)

    response = client.get(reverse("game:memory_game"))

    assert response.status_code == 200
    assert b"Sticker Memory" in response.content
    assert b"Rookie Board" in response.content
    assert b"Collector Board" in response.content


@pytest.mark.django_db
def test_rookie_memory_board_start_creates_session_run(client):
    user = UserFactory(candy_trail_mix=1)
    user.save()
    _seed_memory_species(12)

    client.force_login(user)
    response = client.post(reverse("game:memory_board", args=["rookie_3x4"]), {"action": "start_run"})

    assert response.status_code == 302
    run_state = client.session[MEMORY_SESSION_KEY]
    assert run_state["board_key"] == "rookie_3x4"
    assert len(run_state["cards"]) == get_memory_board_config("rookie_3x4").total_cards

    user.refresh_from_db()
    assert user.candy_trail_mix == 0


@pytest.mark.django_db
def test_memory_board_completion_awards_ryo_and_dust(client):
    user = UserFactory(candy_trail_mix=1, ryo=0, sticker_dust=0)
    user.save()
    _seed_memory_species(12)

    client.force_login(user)
    board_url = reverse("game:memory_board", args=["rookie_3x4"])
    client.post(board_url, {"action": "start_run"})
    response = client.post(
        board_url,
        {
            "action": "complete_run",
            "turns": 6,
            "elapsed_seconds": 40,
            "best_streak": 6,
        },
    )

    assert response.status_code == 302
    user.refresh_from_db()
    result = client.session[MEMORY_RESULT_SESSION_KEY]

    assert MEMORY_SESSION_KEY not in client.session
    assert result["grade"] == "Perfect"
    assert user.ryo == result["reward_ryo"]
    assert user.sticker_dust == result["reward_dust"]
