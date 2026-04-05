"""Tests for the Sticker award system (StickerService)."""
import pytest
import allure
from unittest.mock import patch

from apps.stickers.models import (
    CRAFT_COSTS,
    DUST_VALUES,
    Sticker,
    StickerAlbum,
    StickerPack,
    StickerRarity,
    StickerVariant,
)

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.sticker_factory import StickerFactory, StickerPackFactory
from tests.framework.factories.pokemon_factory import PokemonFactory


# ===========================================================================
# StickerService — award_on_catch
# ===========================================================================

@allure.epic("Stickers")
@allure.feature("Award on Catch")
class TestStickerAwardOnCatch(BaseTest):

    @allure.story("Catching at full HP gives a common sticker")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_catch_at_full_hp_gives_common(self, sticker_svc, player, bulbasaur):
        # Act
        sticker = sticker_svc.award_on_catch(player, bulbasaur, hp_remaining=100)

        # Assert
        assert sticker.owner == player
        assert sticker.pokemon == bulbasaur
        assert sticker.rarity == StickerRarity.COMMON
        assert sticker.awarded_from == "catch"

    @allure.story("Catching at 1 HP with 100% secret-rare roll gives secret_rare")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_catch_at_1_hp_can_give_secret_rare(self, sticker_svc, player, bulbasaur):
        # Force the random roll to always succeed
        with patch("apps.stickers.services.random.random", return_value=0.0):
            sticker = sticker_svc.award_on_catch(player, bulbasaur, hp_remaining=1)

        assert sticker.rarity == StickerRarity.SECRET_RARE

    @allure.story("Catching at 1 HP with failed roll gives common sticker")
    @allure.severity(allure.severity_level.NORMAL)
    def test_catch_at_1_hp_failed_roll_gives_common(self, sticker_svc, player, bulbasaur):
        # Force the random roll to always fail (> 3%)
        with patch("apps.stickers.services.random.random", return_value=1.0):
            sticker = sticker_svc.award_on_catch(player, bulbasaur, hp_remaining=1)

        assert sticker.rarity == StickerRarity.COMMON

    @allure.story("Catching creates a StickerAlbum if one doesn't exist")
    @allure.severity(allure.severity_level.NORMAL)
    def test_catch_creates_album(self, sticker_svc, player, bulbasaur):
        assert not StickerAlbum.objects.filter(owner=player).exists()

        sticker_svc.award_on_catch(player, bulbasaur, hp_remaining=50)

        assert StickerAlbum.objects.filter(owner=player).exists()


# ===========================================================================
# StickerService — award_on_level_up
# ===========================================================================

@allure.epic("Stickers")
@allure.feature("Award on Level Up")
class TestStickerAwardOnLevelUp(BaseTest):

    @allure.story("Non-milestone level returns None")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.parametrize("level", [1, 10, 24, 26, 49, 51, 74, 76, 99])
    def test_non_milestone_returns_none(self, sticker_svc, player, bulbasaur, level):
        result = sticker_svc.award_on_level_up(player, bulbasaur, new_level=level)
        assert result is None

    @allure.story("Level 25 awards uncommon sticker")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_level_25_uncommon(self, sticker_svc, player, bulbasaur):
        sticker = sticker_svc.award_on_level_up(player, bulbasaur, new_level=25)
        assert sticker is not None
        assert sticker.rarity == StickerRarity.UNCOMMON
        assert sticker.awarded_from == "level_up"

    @allure.story("Level 50 awards rare sticker")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_level_50_rare(self, sticker_svc, player, bulbasaur):
        sticker = sticker_svc.award_on_level_up(player, bulbasaur, new_level=50)
        assert sticker is not None
        assert sticker.rarity == StickerRarity.RARE

    @allure.story("Level 75 awards epic sticker")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_level_75_epic(self, sticker_svc, player, bulbasaur):
        sticker = sticker_svc.award_on_level_up(player, bulbasaur, new_level=75)
        assert sticker is not None
        assert sticker.rarity == StickerRarity.EPIC

    @allure.story("Level 100 awards holographic sticker")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_level_100_holographic(self, sticker_svc, player, bulbasaur):
        sticker = sticker_svc.award_on_level_up(player, bulbasaur, new_level=100)
        assert sticker is not None
        assert sticker.rarity == StickerRarity.HOLOGRAPHIC


# ===========================================================================
# StickerService — award_on_combo_win
# ===========================================================================

@allure.epic("Stickers")
@allure.feature("Award on Combo Win")
class TestStickerAwardOnComboWin(BaseTest):

    @allure.story("Chain < 5 returns None")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.parametrize("chain_len", [0, 1, 4])
    def test_short_chain_returns_none(self, sticker_svc, player, bulbasaur, chain_len):
        result = sticker_svc.award_on_combo_win(player, chain_len, pokemon=bulbasaur)
        assert result is None

    @allure.story("Chain >= 5 awards full_art sticker")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.parametrize("chain_len", [5, 6, 10])
    def test_long_chain_awards_full_art(self, sticker_svc, player, bulbasaur, chain_len):
        sticker = sticker_svc.award_on_combo_win(player, chain_len, pokemon=bulbasaur)
        assert sticker is not None
        assert sticker.rarity == StickerRarity.FULL_ART
        assert sticker.awarded_from == "combo_win"


# ===========================================================================
# StickerService — convert_duplicate
# ===========================================================================

@allure.epic("Stickers")
@allure.feature("Sticker Dust Conversion")
class TestStickerConvertDuplicate(BaseTest):

    @allure.story("Converting a duplicate adds dust to player account")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_convert_duplicate_adds_dust(self, sticker_svc, player, bulbasaur):
        # Arrange — create 2 identical stickers
        s1 = StickerFactory(
            owner=player, pokemon=bulbasaur,
            rarity=StickerRarity.COMMON, variant=StickerVariant.BASE,
        )
        StickerFactory(
            owner=player, pokemon=bulbasaur,
            rarity=StickerRarity.COMMON, variant=StickerVariant.BASE,
        )
        initial_dust = player.sticker_dust

        # Act
        dust_gained = sticker_svc.convert_duplicate(player, s1)

        # Assert
        expected_dust = DUST_VALUES[StickerRarity.COMMON]
        assert dust_gained == expected_dust
        player.refresh_from_db()
        assert player.sticker_dust == initial_dust + expected_dust
        # The sticker was deleted
        assert not Sticker.objects.filter(pk=s1.pk).exists()

    @allure.story("Cannot convert the only copy of a sticker")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_cannot_convert_only_copy(self, sticker_svc, player, bulbasaur):
        # Arrange — only one copy
        sticker = StickerFactory(
            owner=player, pokemon=bulbasaur,
            rarity=StickerRarity.COMMON, variant=StickerVariant.BASE,
        )

        # Act / Assert
        with pytest.raises(ValueError, match="only copy"):
            sticker_svc.convert_duplicate(player, sticker)

    @allure.story("Cannot convert a sticker you don't own")
    @allure.severity(allure.severity_level.NORMAL)
    def test_cannot_convert_others_sticker(self, sticker_svc, player, other_player, bulbasaur):
        sticker = StickerFactory(owner=other_player, pokemon=bulbasaur)

        with pytest.raises(ValueError, match="does not belong"):
            sticker_svc.convert_duplicate(player, sticker)

    @allure.story("Cannot convert a sticker currently in a trade")
    @allure.severity(allure.severity_level.NORMAL)
    def test_cannot_convert_trading_sticker(self, sticker_svc, player, bulbasaur):
        # Two copies, but one is in a trade
        sticker = StickerFactory(
            owner=player, pokemon=bulbasaur,
            rarity=StickerRarity.COMMON, variant=StickerVariant.BASE,
            is_trading=True,
        )
        StickerFactory(
            owner=player, pokemon=bulbasaur,
            rarity=StickerRarity.COMMON, variant=StickerVariant.BASE,
        )

        with pytest.raises(ValueError, match="currently in a trade"):
            sticker_svc.convert_duplicate(player, sticker)


# ===========================================================================
# StickerService — craft_sticker
# ===========================================================================

@allure.epic("Stickers")
@allure.feature("Sticker Crafting")
class TestStickerCraft(BaseTest):

    @allure.story("Crafting a common sticker deducts 10 dust")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_craft_common_deducts_dust(self, sticker_svc, player, bulbasaur):
        # Arrange
        player.sticker_dust = 50
        player.save(update_fields=["sticker_dust"])

        # Act
        sticker = sticker_svc.craft_sticker(
            player, bulbasaur, StickerVariant.BASE, StickerRarity.COMMON
        )

        # Assert
        cost = CRAFT_COSTS[StickerRarity.COMMON]
        player.refresh_from_db()
        assert player.sticker_dust == 50 - cost
        assert sticker.rarity == StickerRarity.COMMON
        assert sticker.awarded_from == "craft"
        assert sticker.owner == player

    @allure.story("Crafting with insufficient dust raises ValueError")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_craft_insufficient_dust(self, sticker_svc, player, bulbasaur):
        player.sticker_dust = 0
        player.save(update_fields=["sticker_dust"])

        with pytest.raises(ValueError, match="Insufficient dust"):
            sticker_svc.craft_sticker(
                player, bulbasaur, StickerVariant.BASE, StickerRarity.HOLOGRAPHIC
            )

    @allure.story("Crafting with invalid rarity raises ValueError")
    @allure.severity(allure.severity_level.NORMAL)
    def test_craft_invalid_rarity(self, sticker_svc, player, bulbasaur):
        player.sticker_dust = 9999
        player.save(update_fields=["sticker_dust"])

        with pytest.raises(ValueError, match="Unknown rarity"):
            sticker_svc.craft_sticker(
                player, bulbasaur, StickerVariant.BASE, "legendary"
            )

    @allure.story("Crafting with invalid variant raises ValueError")
    @allure.severity(allure.severity_level.NORMAL)
    def test_craft_invalid_variant(self, sticker_svc, player, bulbasaur):
        player.sticker_dust = 9999
        player.save(update_fields=["sticker_dust"])

        with pytest.raises(ValueError, match="Unknown variant"):
            sticker_svc.craft_sticker(
                player, bulbasaur, "gold_foil", StickerRarity.COMMON
            )


# ===========================================================================
# StickerService — grant_pack_if_eligible / open_pack
# ===========================================================================

@allure.epic("Stickers")
@allure.feature("Sticker Packs")
class TestStickerPacks(BaseTest):

    @allure.story("Player with 10 wins gets a pack")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_grant_pack_at_10_wins(self, sticker_svc, player):
        player.battles_won = 10
        player.save(update_fields=["battles_won"])

        pack = sticker_svc.grant_pack_if_eligible(player)

        assert pack is not None
        assert isinstance(pack, StickerPack)
        assert pack.owner == player
        assert pack.opened is False

    @allure.story("Player with 9 wins gets no pack")
    @allure.severity(allure.severity_level.NORMAL)
    def test_no_pack_at_9_wins(self, sticker_svc, player):
        player.battles_won = 9
        player.save(update_fields=["battles_won"])

        pack = sticker_svc.grant_pack_if_eligible(player)

        assert pack is None

    @allure.story("Pack with 0 wins returns None (edge: 0 % 10 == 0 but 0 > 0 guard)")
    @allure.severity(allure.severity_level.NORMAL)
    def test_no_pack_at_0_wins(self, sticker_svc, player):
        player.battles_won = 0
        player.save(update_fields=["battles_won"])

        pack = sticker_svc.grant_pack_if_eligible(player)

        assert pack is None

    @allure.story("Opening a pack creates 5 stickers")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_open_pack_gives_5_stickers(self, sticker_svc, player, bulbasaur):
        # Need at least one Pokemon in the DB for random.choice
        pack = StickerPackFactory(owner=player)

        stickers = sticker_svc.open_pack(player, pack)

        assert len(stickers) == 5
        pack.refresh_from_db()
        assert pack.opened is True
        assert pack.opened_at is not None

    @allure.story("Opening an already-opened pack raises ValueError")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_open_pack_twice_raises(self, sticker_svc, player, bulbasaur):
        pack = StickerPackFactory(owner=player)
        sticker_svc.open_pack(player, pack)

        with pytest.raises(ValueError, match="already been opened"):
            sticker_svc.open_pack(player, pack)

    @allure.story("Opening another player's pack raises ValueError")
    @allure.severity(allure.severity_level.NORMAL)
    def test_open_others_pack_raises(self, sticker_svc, player, other_player, bulbasaur):
        pack = StickerPackFactory(owner=other_player)

        with pytest.raises(ValueError, match="does not belong"):
            sticker_svc.open_pack(player, pack)
