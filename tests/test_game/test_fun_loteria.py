"""Tests for the player-owned Pokemon Loteria quick-play flow."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.game.fun import create_quick_loteria_room, ensure_default_loteria_board, get_loteria_deck_config, start_loteria_room
from apps.game.models import LoteriaBoardTemplate, LoteriaRoom, LoteriaStatus
from tests.framework.factories.pokemon_factory import OwnedPokemonFactory, PokemonFactory
from tests.framework.factories.user_factory import UserFactory


def _seed_kanto_species(total: int = 24):
    species = []
    for dex in range(1, total + 1):
        species.append(
            PokemonFactory(
                pokedex_number=dex,
                name=f"Kanto{dex}",
                sprite_url=f"/media/pokemon/sprites/{dex:03d}.png",
            )
        )
    return species


@pytest.mark.django_db
def test_loteria_hub_seeds_default_board_without_autostart(client):
    user = UserFactory(candy_trail_mix=3)
    user.save()
    _seed_kanto_species(24)
    client.force_login(user)

    response = client.get(reverse("game:loteria_game"))

    assert response.status_code == 200
    assert b"Kanto Loteria" in response.content
    assert LoteriaBoardTemplate.objects.filter(owner=user, deck_key="kanto").count() == 1
    assert not LoteriaRoom.objects.filter(created_by=user).exists()


@pytest.mark.django_db
def test_loteria_hub_creates_quick_play_room_and_opens_lobby(client):
    user = UserFactory(candy_trail_mix=3)
    user.save()
    _seed_kanto_species(24)
    client.force_login(user)

    response = client.post(reverse("game:loteria_game"), {"action": "create_room", "npc_count": "4"})

    room = LoteriaRoom.objects.get(created_by=user)
    assert response.status_code == 302
    assert response.url == reverse("game:loteria_lobby", args=[room.pk])
    assert room.npc_count == 4
    assert room.status == LoteriaStatus.LOBBY


@pytest.mark.django_db
def test_loteria_lobby_start_consumes_candy_and_creates_player_and_npc_entries(client):
    user = UserFactory(candy_trail_mix=3)
    user.save()
    species = _seed_kanto_species(24)
    for pokemon in species[:16]:
        OwnedPokemonFactory(owner=user, species=pokemon)

    client.force_login(user)
    config = get_loteria_deck_config("kanto")
    ensure_default_loteria_board(user, config)
    room = create_quick_loteria_room(user, config, 2)
    board = LoteriaBoardTemplate.objects.get(owner=user, deck_key="kanto", board_slot=1)

    response = client.post(
        reverse("game:loteria_lobby", args=[room.pk]),
        {"action": "start_room", "board_ids": [str(board.pk)]},
    )

    room.refresh_from_db()
    user.refresh_from_db()

    assert response.status_code == 302
    assert response.url == reverse("game:loteria_room", args=[room.pk])
    assert room.status == LoteriaStatus.ACTIVE
    assert room.entries.filter(user=user).count() == 1
    assert room.entries.filter(is_npc=True).count() == 2
    assert user.candy_trail_mix == 2
    assert room.prize_pool_ryo == config.prize_for_npc_count(2) + config.prize_boost_per_player_board


@pytest.mark.django_db
def test_loteria_room_finishes_on_full_board_and_redirects_to_results(client):
    user = UserFactory(candy_trail_mix=3, ryo=0)
    user.save()
    species = _seed_kanto_species(24)
    for pokemon in species[:16]:
        OwnedPokemonFactory(owner=user, species=pokemon)

    client.force_login(user)
    config = get_loteria_deck_config("kanto")
    ensure_default_loteria_board(user, config)
    room = create_quick_loteria_room(user, config, 2)
    board = LoteriaBoardTemplate.objects.get(owner=user, deck_key="kanto", board_slot=1)
    start_loteria_room(user, room, config, [board.pk])

    room.refresh_from_db()
    room.deck_order = list(board.species_ids)
    room.called_species_ids = list(board.species_ids[:-1])
    room.next_tick_at = timezone.now() - timedelta(seconds=1)
    room.prize_pool_ryo = 1200
    room.save(update_fields=["deck_order", "called_species_ids", "next_tick_at", "prize_pool_ryo", "updated_at"])

    response = client.get(reverse("game:loteria_room", args=[room.pk]))

    room.refresh_from_db()
    user.refresh_from_db()

    assert response.status_code == 302
    assert response.url == reverse("game:loteria_results", args=[room.pk])
    assert room.status == LoteriaStatus.FINISHED
    assert room.entries.filter(is_winner=True).exists()
    assert user.ryo > 0


@pytest.mark.django_db
def test_loteria_results_page_shows_winner_summary(client):
    user = UserFactory(candy_trail_mix=3, ryo=0)
    user.save()
    species = _seed_kanto_species(24)
    for pokemon in species[:16]:
        OwnedPokemonFactory(owner=user, species=pokemon)

    client.force_login(user)
    config = get_loteria_deck_config("kanto")
    ensure_default_loteria_board(user, config)
    room = create_quick_loteria_room(user, config, 2)
    board = LoteriaBoardTemplate.objects.get(owner=user, deck_key="kanto", board_slot=1)
    start_loteria_room(user, room, config, [board.pk])

    room.refresh_from_db()
    room.called_species_ids = list(board.species_ids)
    room.prize_pool_ryo = 900
    room.status = LoteriaStatus.FINISHED
    room.finished_at = timezone.now()
    room.next_tick_at = None
    room.save(update_fields=["called_species_ids", "prize_pool_ryo", "status", "finished_at", "next_tick_at", "updated_at"])
    entry = room.entries.get(user=user)
    entry.is_winner = True
    entry.reward_ryo = 900
    entry.save(update_fields=["is_winner", "reward_ryo"])

    response = client.get(reverse("game:loteria_results", args=[room.pk]))

    assert response.status_code == 200
    assert b"Winning Boards" in response.content
    assert b"Loteria Tables" in response.content
