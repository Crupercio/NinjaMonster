"""Tests for the Fun hub silhouette tower MVP."""
import pytest
from django.urls import reverse

from apps.game.fun import (
    ROOKIE_25_DEXES,
    SILHOUETTE_REVEAL_SESSION_KEY,
    SILHOUETTE_SESSION_KEY,
    get_silhouette_tower_config,
)
from tests.framework.factories.pokemon_factory import PokemonFactory
from tests.framework.factories.user_factory import UserFactory


@pytest.mark.django_db
def test_rookie_tower_start_creates_session_run(client):
    user = UserFactory(candy_trail_mix=3)
    user.save()

    for dex in ROOKIE_25_DEXES:
        PokemonFactory(pokedex_number=dex, name=f"Mon{dex}")

    client.force_login(user)
    response = client.post(reverse("game:silhouette_tower", args=["rookie"]), {"action": "start_run"})

    assert response.status_code == 302
    run_state = client.session[SILHOUETTE_SESSION_KEY]
    assert run_state["tower_key"] == "rookie"
    assert run_state["current_floor"] == 1
    assert len(run_state["question"]["option_dex_numbers"]) == 6


@pytest.mark.django_db
def test_rookie_tower_correct_answer_then_cash_out_awards_ryo(client):
    user = UserFactory(candy_trail_mix=3, ryo=0)
    user.save()

    for dex in ROOKIE_25_DEXES:
        PokemonFactory(pokedex_number=dex, name=f"Mon{dex}")

    client.force_login(user)
    tower_url = reverse("game:silhouette_tower", args=["rookie"])
    client.post(tower_url, {"action": "start_run"})
    run_state = client.session[SILHOUETTE_SESSION_KEY]
    correct_dex = run_state["question"]["correct_dex"]

    client.post(tower_url, {"action": "guess", "selected_dex": correct_dex})
    reveal_state = client.session[SILHOUETTE_REVEAL_SESSION_KEY]
    assert reveal_state["banked_ryo"] == get_silhouette_tower_config("rookie").floor_rewards[0]

    client.post(tower_url, {"action": "advance"})
    run_state = client.session[SILHOUETTE_SESSION_KEY]
    assert run_state["banked_ryo"] == get_silhouette_tower_config("rookie").floor_rewards[0]

    client.post(tower_url, {"action": "cash_out"})
    user.refresh_from_db()

    assert SILHOUETTE_SESSION_KEY not in client.session
    assert SILHOUETTE_REVEAL_SESSION_KEY not in client.session
    assert user.ryo == get_silhouette_tower_config("rookie").floor_rewards[0]


@pytest.mark.django_db
def test_rookie_tower_wrong_answer_salvages_half_banked_reward(client):
    user = UserFactory(candy_trail_mix=3, ryo=0)
    user.save()

    for dex in ROOKIE_25_DEXES:
        PokemonFactory(pokedex_number=dex, name=f"Mon{dex}")

    client.force_login(user)
    tower_url = reverse("game:silhouette_tower", args=["rookie"])
    client.post(tower_url, {"action": "start_run"})
    first_run = client.session[SILHOUETTE_SESSION_KEY]
    client.post(tower_url, {"action": "guess", "selected_dex": first_run["question"]["correct_dex"]})
    client.post(tower_url, {"action": "advance"})

    second_run = client.session[SILHOUETTE_SESSION_KEY]
    wrong_dex = next(dex for dex in second_run["question"]["option_dex_numbers"] if dex != second_run["question"]["correct_dex"])
    client.post(tower_url, {"action": "guess", "selected_dex": wrong_dex})

    user.refresh_from_db()
    assert SILHOUETTE_SESSION_KEY not in client.session
    assert SILHOUETTE_REVEAL_SESSION_KEY in client.session
    assert user.ryo == get_silhouette_tower_config("rookie").floor_rewards[0] // 2


@pytest.mark.django_db
def test_regional_tower_starts_with_all_generation_sample_pool(client):
    user = UserFactory(candy_sweet_berry=3)
    user.save()

    for dex in range(1, 101):
        PokemonFactory(pokedex_number=dex, name=f"Mon{dex}")

    client.force_login(user)
    response = client.post(reverse("game:silhouette_tower", args=["regional_100"]), {"action": "start_run"})

    assert response.status_code == 302
    run_state = client.session[SILHOUETTE_SESSION_KEY]
    assert run_state["tower_key"] == "regional_100"
    assert len(run_state["pool_dex_numbers"]) == 100
    assert len(run_state["question"]["option_dex_numbers"]) == 6
