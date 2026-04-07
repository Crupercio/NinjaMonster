"""
P1-1 — Sticker award wiring tests.

Covers:
- Pack granted on the 10th win (battles_won % 10 == 0)
- No pack granted when not on a 10-win multiple
- Full Art sticker granted when max_combo_chain >= 5
- No sticker when max_combo_chain < 5
- Both awards can fire in the same battle
- BattleLog entries are written for each award
"""
import allure
import pytest

from apps.game.models import BattleLog, BattleStatus, LogType
from apps.stickers.models import StickerPack, StickerRarity, StickerVariant

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.battle_factory import (
    BattleFactory,
    BattleSlotFactory,
    BattleTeamFactory,
)
from tests.framework.factories.pokemon_factory import PokemonFactory, PokemonTypeFactory
from tests.framework.factories.user_factory import UserFactory


def _build_finished_battle(winner, loser, max_combo_chain: int = 0):
    """Create a FINISHED battle between winner and loser with the given chain depth."""
    battle = BattleFactory(
        player_one=winner,
        player_two=loser,
        status=BattleStatus.FINISHED,
        winner=winner,
        max_combo_chain=max_combo_chain,
    )
    normal_type = PokemonTypeFactory(name="Normal")
    team1 = BattleTeamFactory(battle=battle, owner=winner)
    team2 = BattleTeamFactory(battle=battle, owner=loser)
    for pos in range(1, 7):
        poke = PokemonFactory(primary_type=normal_type)
        BattleSlotFactory(team=team1, pokemon=poke, position=pos)
        BattleSlotFactory(team=team2, pokemon=poke, position=pos)
    return battle


@allure.epic("Battle")
@allure.feature("Sticker Awards")
@pytest.mark.django_db
class TestStickerAwardOnBattleWin(BaseTest):

    @allure.story("Pack awarded on 10th win")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_pack_granted_on_tenth_win(self, svc):
        # Arrange — winner has 9 wins; _end_battle will increment to 10
        winner = UserFactory(battles_won=9, battles_played=9)
        loser = UserFactory()
        battle = _build_finished_battle(winner, loser)
        battle.status = BattleStatus.ACTIVE  # must be ACTIVE for _end_battle to process
        battle.winner = None
        battle.save(update_fields=["status", "winner"])

        # Act
        svc._end_battle(battle, winner)

        # Assert — winner now has 10 wins, pack was created
        winner.refresh_from_db()
        assert winner.battles_won == 10
        assert StickerPack.objects.filter(owner=winner).count() == 1

        # BattleLog mentions the pack
        assert BattleLog.objects.filter(
            battle=battle, log_type=LogType.INFO, message__icontains="sticker pack"
        ).exists()

    @allure.story("No pack when win count is not a multiple of 10")
    @allure.severity(allure.severity_level.NORMAL)
    def test_no_pack_on_non_milestone_win(self, svc):
        # Arrange — winner has 5 wins; 6th win is not a milestone
        winner = UserFactory(battles_won=5, battles_played=5)
        loser = UserFactory()
        battle = _build_finished_battle(winner, loser)
        battle.status = BattleStatus.ACTIVE
        battle.winner = None
        battle.save(update_fields=["status", "winner"])

        # Act
        svc._end_battle(battle, winner)

        # Assert — no pack created
        winner.refresh_from_db()
        assert winner.battles_won == 6
        assert StickerPack.objects.filter(owner=winner).count() == 0

    @allure.story("Full Art sticker awarded for combo chain >= 5")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_full_art_sticker_for_combo_chain_five(self, svc):
        # Arrange
        winner = UserFactory(battles_won=0, battles_played=0)
        loser = UserFactory()
        battle = _build_finished_battle(winner, loser, max_combo_chain=5)
        battle.status = BattleStatus.ACTIVE
        battle.winner = None
        battle.save(update_fields=["status", "winner"])

        # Act
        svc._end_battle(battle, winner)

        # Assert — a Full Art sticker was awarded
        from apps.stickers.models import Sticker
        stickers = Sticker.objects.filter(
            owner=winner,
            rarity=StickerRarity.FULL_ART,
            variant=StickerVariant.BASE,
        )
        assert stickers.count() == 1

        # BattleLog mentions the combo chain
        assert BattleLog.objects.filter(
            battle=battle, log_type=LogType.COMBO, message__icontains="Combo chain"
        ).exists()

    @allure.story("No sticker for combo chain below 5")
    @allure.severity(allure.severity_level.NORMAL)
    def test_no_sticker_for_short_combo_chain(self, svc):
        # Arrange — chain of 4, just below threshold
        winner = UserFactory(battles_won=0, battles_played=0)
        loser = UserFactory()
        battle = _build_finished_battle(winner, loser, max_combo_chain=4)
        battle.status = BattleStatus.ACTIVE
        battle.winner = None
        battle.save(update_fields=["status", "winner"])

        # Act
        svc._end_battle(battle, winner)

        # Assert — no Full Art sticker
        from apps.stickers.models import Sticker
        assert not Sticker.objects.filter(
            owner=winner, rarity=StickerRarity.FULL_ART
        ).exists()

    @allure.story("Both pack and sticker awarded in same battle")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_both_awards_fire_together(self, svc):
        # Arrange — 9 wins + chain of 7 means both thresholds hit
        winner = UserFactory(battles_won=9, battles_played=9)
        loser = UserFactory()
        battle = _build_finished_battle(winner, loser, max_combo_chain=7)
        battle.status = BattleStatus.ACTIVE
        battle.winner = None
        battle.save(update_fields=["status", "winner"])

        # Act
        svc._end_battle(battle, winner)

        # Assert pack
        assert StickerPack.objects.filter(owner=winner).count() == 1

        # Assert Full Art sticker
        from apps.stickers.models import Sticker
        assert Sticker.objects.filter(
            owner=winner, rarity=StickerRarity.FULL_ART
        ).exists()

    @allure.story("Loser battles_played is incremented")
    @allure.severity(allure.severity_level.NORMAL)
    def test_loser_battles_played_incremented(self, svc):
        # Arrange
        winner = UserFactory(battles_won=0, battles_played=0)
        loser = UserFactory(battles_won=0, battles_played=2)
        battle = _build_finished_battle(winner, loser)
        battle.status = BattleStatus.ACTIVE
        battle.winner = None
        battle.save(update_fields=["status", "winner"])

        # Act
        svc._end_battle(battle, winner)

        # Assert
        loser.refresh_from_db()
        assert loser.battles_played == 3
