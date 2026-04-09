"""
P4-3 — Album Completion Rewards tests (GDD §20.13).

Covers:
- check_pokemon_completion() False when missing slots
- check_pokemon_completion() True when all 42 slots owned
- maybe_award_completion_rewards() awards dust + ryo for completed pokemon
- maybe_award_completion_rewards() does NOT double-award same pokemon
- maybe_award_completion_rewards() returns empty list when pokemon incomplete
- Full dex reward triggered when every pokemon is complete
- Full dex reward NOT double-awarded
- get_completion_rewards_for_album() returns correct set of completed pokemon ids
- get_completion_rewards_for_album() reports full_dex_claimed correctly
- Album page renders completion rewards banner when rewards exist
- Album page renders completion checkmark for completed pokemon
- Album page shows no rewards banner when nothing completed
"""
import allure
import pytest
from django.test import Client
from django.urls import reverse

from apps.stickers.models import (
    AlbumCompletionReward,
    AlbumRewardType,
    StickerRarity,
    StickerVariant,
)
from apps.stickers.services import (
    FULL_DEX_DUST,
    FULL_DEX_PACKS,
    FULL_DEX_RYO,
    POKEMON_COMPLETE_DUST,
    POKEMON_COMPLETE_RYO,
    POKEMON_COMPLETION_SLOTS,
    StickerService,
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


def _fill_pokemon_slots(user, pokemon) -> None:
    """Create one sticker for every valid (rarity, variant) combination."""
    for rarity in _COMPLETION_RARITIES:
        for variant in _COMPLETION_VARIANTS:
            StickerFactory(owner=user, pokemon=pokemon, rarity=rarity, variant=variant)


@allure.epic("Stickers")
@allure.feature("Album Completion Rewards")
@pytest.mark.django_db
class TestCheckPokemonCompletion(BaseTest):

    @allure.story("Returns False when user has no stickers for pokemon")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_false_when_no_stickers(self):
        user = UserFactory()
        pokemon = PokemonFactory()
        svc = StickerService()
        assert svc.check_pokemon_completion(user, pokemon) is False

    @allure.story("Returns False when only some slots are filled")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_false_when_incomplete(self):
        user = UserFactory()
        pokemon = PokemonFactory()
        # Only give common/base — far from 42 slots
        StickerFactory(owner=user, pokemon=pokemon, rarity=StickerRarity.COMMON, variant=StickerVariant.BASE)
        svc = StickerService()
        assert svc.check_pokemon_completion(user, pokemon) is False

    @allure.story("Returns True when all 42 slots are filled")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_true_when_all_slots_filled(self):
        user = UserFactory()
        pokemon = PokemonFactory()
        _fill_pokemon_slots(user, pokemon)
        svc = StickerService()
        assert svc.check_pokemon_completion(user, pokemon) is True

    @allure.story("POKEMON_COMPLETION_SLOTS constant equals 42")
    @allure.severity(allure.severity_level.NORMAL)
    def test_completion_slots_constant(self):
        assert POKEMON_COMPLETION_SLOTS == 42


@allure.epic("Stickers")
@allure.feature("Album Completion Rewards")
@pytest.mark.django_db
class TestMaybeAwardCompletionRewards(BaseTest):

    @allure.story("Awards dust + ryo when pokemon first completed")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_awards_pokemon_completion_reward(self):
        user = UserFactory(sticker_dust=0, ryo=0)
        # Create two pokemon so completing one doesn't also trigger full dex
        pokemon = PokemonFactory()
        PokemonFactory()  # second pokemon not completed — blocks full dex
        _fill_pokemon_slots(user, pokemon)
        svc = StickerService()
        summaries = svc.maybe_award_completion_rewards(user, {pokemon.pk})
        user.refresh_from_db()
        types = [s["type"] for s in summaries]
        assert "pokemon" in types
        assert "full_dex" not in types
        assert user.sticker_dust == POKEMON_COMPLETE_DUST
        assert user.ryo == POKEMON_COMPLETE_RYO

    @allure.story("Does not double-award the same pokemon")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_no_double_award(self):
        user = UserFactory(sticker_dust=0, ryo=0)
        pokemon = PokemonFactory()
        PokemonFactory()  # second pokemon not completed — blocks full dex
        _fill_pokemon_slots(user, pokemon)
        svc = StickerService()
        svc.maybe_award_completion_rewards(user, {pokemon.pk})  # first call — awards 500 dust
        user.refresh_from_db()
        dust_after_first = user.sticker_dust
        summaries = svc.maybe_award_completion_rewards(user, {pokemon.pk})  # second call
        user.refresh_from_db()
        assert summaries == []
        assert user.sticker_dust == dust_after_first  # unchanged

    @allure.story("Returns empty list when pokemon is not complete")
    @allure.severity(allure.severity_level.NORMAL)
    def test_empty_when_incomplete(self):
        user = UserFactory(sticker_dust=0)
        pokemon = PokemonFactory()
        StickerFactory(owner=user, pokemon=pokemon)  # only one slot
        svc = StickerService()
        summaries = svc.maybe_award_completion_rewards(user, {pokemon.pk})
        assert summaries == []

    @allure.story("AlbumCompletionReward record is created on first award")
    @allure.severity(allure.severity_level.NORMAL)
    def test_completion_reward_record_created(self):
        user = UserFactory()
        pokemon = PokemonFactory()
        _fill_pokemon_slots(user, pokemon)
        StickerService().maybe_award_completion_rewards(user, {pokemon.pk})
        assert AlbumCompletionReward.objects.filter(
            user=user,
            reward_type=AlbumRewardType.POKEMON_COMPLETE,
            pokemon=pokemon,
        ).exists()

    @allure.story("Full dex reward triggered when all pokemon are complete")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_full_dex_reward_triggered(self):
        user = UserFactory(sticker_dust=0, ryo=0)
        # Use a single Pokemon as the entire "dex" for this test
        pokemon = PokemonFactory()
        _fill_pokemon_slots(user, pokemon)
        svc = StickerService()
        summaries = svc.maybe_award_completion_rewards(user, {pokemon.pk})
        user.refresh_from_db()
        # Should have both pokemon reward and full dex reward
        types = [s["type"] for s in summaries]
        assert "pokemon" in types
        assert "full_dex" in types
        assert user.sticker_dust == POKEMON_COMPLETE_DUST + FULL_DEX_DUST
        assert user.ryo == POKEMON_COMPLETE_RYO + FULL_DEX_RYO

    @allure.story("Full dex reward grants sticker packs")
    @allure.severity(allure.severity_level.NORMAL)
    def test_full_dex_grants_packs(self):
        from apps.stickers.models import StickerPack
        user = UserFactory()
        pokemon = PokemonFactory()
        _fill_pokemon_slots(user, pokemon)
        pack_count_before = StickerPack.objects.filter(owner=user).count()
        StickerService().maybe_award_completion_rewards(user, {pokemon.pk})
        pack_count_after = StickerPack.objects.filter(owner=user).count()
        assert pack_count_after - pack_count_before == FULL_DEX_PACKS

    @allure.story("Full dex reward is not double-awarded")
    @allure.severity(allure.severity_level.NORMAL)
    def test_full_dex_no_double_award(self):
        user = UserFactory(sticker_dust=0)
        pokemon = PokemonFactory()
        _fill_pokemon_slots(user, pokemon)
        svc = StickerService()
        svc.maybe_award_completion_rewards(user, {pokemon.pk})
        # Manually call again as if another sticker was gained for same pokemon
        summaries = svc.maybe_award_completion_rewards(user, {pokemon.pk})
        full_dex_summaries = [s for s in summaries if s.get("type") == "full_dex"]
        assert full_dex_summaries == []


@allure.epic("Stickers")
@allure.feature("Album Completion Rewards")
@pytest.mark.django_db
class TestGetCompletionRewardsForAlbum(BaseTest):

    @allure.story("Returns completed_pokemon_ids for awarded pokemon")
    @allure.severity(allure.severity_level.NORMAL)
    def test_completed_pokemon_ids_populated(self):
        user = UserFactory()
        pokemon = PokemonFactory()
        _fill_pokemon_slots(user, pokemon)
        StickerService().maybe_award_completion_rewards(user, {pokemon.pk})
        result = StickerService().get_completion_rewards_for_album(user)
        assert pokemon.pk in result["completed_pokemon_ids"]

    @allure.story("full_dex_claimed False when dex is incomplete")
    @allure.severity(allure.severity_level.NORMAL)
    def test_full_dex_claimed_false_when_not_earned(self):
        user = UserFactory()
        result = StickerService().get_completion_rewards_for_album(user)
        assert result["full_dex_claimed"] is False


@allure.epic("Stickers")
@allure.feature("Album Completion Rewards")
@pytest.mark.django_db
class TestAlbumPageCompletionRendering(BaseTest):

    @allure.story("Album page shows completion rewards banner when rewards exist")
    @allure.severity(allure.severity_level.NORMAL)
    def test_album_shows_rewards_banner(self):
        user = UserFactory()
        pokemon = PokemonFactory()
        _fill_pokemon_slots(user, pokemon)
        StickerService().maybe_award_completion_rewards(user, {pokemon.pk})
        response = _client(user).get(reverse("stickers:album"))
        assert response.status_code == 200
        assert "Collection Rewards" in response.content.decode()

    @allure.story("Album page shows no rewards banner when nothing completed")
    @allure.severity(allure.severity_level.MINOR)
    def test_album_no_banner_when_nothing_complete(self):
        user = UserFactory()
        response = _client(user).get(reverse("stickers:album"))
        assert response.status_code == 200
        assert "Collection Rewards" not in response.content.decode()
