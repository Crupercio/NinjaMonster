"""
P4-4 — Sticker album visual overhaul: PokemonAlbumDetailView tests.

Covers:
- Detail page returns 200 for valid pokemon owned by user
- Detail page returns 404 for nonexistent pokemon
- Grid contains 42 slot entries (7 rarities × 6 variants)
- Owned slot is marked owned=True in context
- Unowned slot is marked owned=False in context
- is_complete False when slots missing
- is_complete True when all 42 slots owned
- slots_owned count matches actual owned slots
- Album grid links to pokemon_album URL for each pokemon
- pokemon_album URL in nav renders correctly
"""
import allure
import pytest
from django.test import Client
from django.urls import reverse

from apps.stickers.models import StickerRarity, StickerVariant
from apps.stickers.services import (
    POKEMON_COMPLETION_SLOTS,
    _COMPLETION_RARITIES,
    _COMPLETION_VARIANTS,
)

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.pokemon_factory import PokemonFactory
from tests.framework.factories.sticker_factory import StickerFactory
from tests.framework.factories.user_factory import UserFactory


def _client(user) -> Client:
    user.set_password("pw")
    user.save(update_fields=["password"])
    c = Client()
    c.force_login(user)
    return c


def _fill_all_slots(user, pokemon) -> None:
    for rarity in _COMPLETION_RARITIES:
        for variant in _COMPLETION_VARIANTS:
            StickerFactory(owner=user, pokemon=pokemon, rarity=rarity, variant=variant)


@allure.epic("Stickers")
@allure.feature("Album Visual Overhaul")
@pytest.mark.django_db
class TestPokemonAlbumDetailView(BaseTest):

    @allure.story("Detail page returns 200 for authenticated user")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_detail_page_ok(self):
        user = UserFactory()
        pokemon = PokemonFactory()
        response = _client(user).get(reverse("stickers:pokemon_album", args=[pokemon.pk]))
        assert response.status_code == 200

    @allure.story("Detail page returns 404 for nonexistent pokemon")
    @allure.severity(allure.severity_level.NORMAL)
    def test_detail_page_404_for_missing_pokemon(self):
        user = UserFactory()
        response = _client(user).get(reverse("stickers:pokemon_album", args=[999999]))
        assert response.status_code == 404

    @allure.story("Grid context contains exactly 42 slot entries")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_grid_has_42_entries(self):
        user = UserFactory()
        pokemon = PokemonFactory()
        response = _client(user).get(reverse("stickers:pokemon_album", args=[pokemon.pk]))
        assert len(response.context["grid"]) == POKEMON_COMPLETION_SLOTS

    @allure.story("Owned slot marked owned=True in grid")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_owned_slot_marked_true(self):
        user = UserFactory()
        pokemon = PokemonFactory()
        StickerFactory(
            owner=user, pokemon=pokemon,
            rarity=StickerRarity.COMMON, variant=StickerVariant.BASE,
        )
        response = _client(user).get(reverse("stickers:pokemon_album", args=[pokemon.pk]))
        grid = response.context["grid"]
        common_base = next(
            s for s in grid if s["rarity"] == "common" and s["variant"] == "base"
        )
        assert common_base["owned"] is True

    @allure.story("Missing slot marked owned=False in grid")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_missing_slot_marked_false(self):
        user = UserFactory()
        pokemon = PokemonFactory()
        response = _client(user).get(reverse("stickers:pokemon_album", args=[pokemon.pk]))
        grid = response.context["grid"]
        assert all(not s["owned"] for s in grid)

    @allure.story("is_complete False when not all slots owned")
    @allure.severity(allure.severity_level.NORMAL)
    def test_is_complete_false_when_incomplete(self):
        user = UserFactory()
        pokemon = PokemonFactory()
        StickerFactory(owner=user, pokemon=pokemon)
        response = _client(user).get(reverse("stickers:pokemon_album", args=[pokemon.pk]))
        assert response.context["is_complete"] is False

    @allure.story("is_complete True when all 42 slots owned")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_is_complete_true_when_all_slots_owned(self):
        user = UserFactory()
        pokemon = PokemonFactory()
        _fill_all_slots(user, pokemon)
        response = _client(user).get(reverse("stickers:pokemon_album", args=[pokemon.pk]))
        assert response.context["is_complete"] is True

    @allure.story("slots_owned matches count of distinct owned slots")
    @allure.severity(allure.severity_level.NORMAL)
    def test_slots_owned_count_correct(self):
        user = UserFactory()
        pokemon = PokemonFactory()
        StickerFactory(owner=user, pokemon=pokemon, rarity=StickerRarity.COMMON, variant=StickerVariant.BASE)
        StickerFactory(owner=user, pokemon=pokemon, rarity=StickerRarity.RARE,   variant=StickerVariant.SHINY)
        # Duplicate of the first — should NOT inflate the count
        StickerFactory(owner=user, pokemon=pokemon, rarity=StickerRarity.COMMON, variant=StickerVariant.BASE)
        response = _client(user).get(reverse("stickers:pokemon_album", args=[pokemon.pk]))
        assert response.context["slots_owned"] == 2

    @allure.story("Album page links each pokemon card to its detail URL")
    @allure.severity(allure.severity_level.NORMAL)
    def test_album_links_to_pokemon_detail(self):
        from apps.pokemon.models import PokemonType
        ptype = PokemonType.objects.create(name="Fire")
        pokemon = PokemonFactory(primary_type=ptype)
        user = UserFactory()
        StickerFactory(owner=user, pokemon=pokemon)
        response = _client(user).get(reverse("stickers:album"))
        assert response.status_code == 200
        detail_url = reverse("stickers:pokemon_album", args=[pokemon.pk])
        assert detail_url in response.content.decode()
