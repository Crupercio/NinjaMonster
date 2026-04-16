"""
Phase 5.5 — Support move rotation tests.

Verifies that _execute_support_moves automatically fires PASSIVE_1 moves
when no cooldown is active, and skips them when a cooldown exists.
"""
import allure
import pytest

from apps.game.models import BattleLog, LogType, MoveCooldown
from apps.game.services import BattleService
from apps.pokemon.models import MoveSlotType

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.pokemon_factory import (
    MoveFactory,
    OwnedPokemonFactory,
    PokemonFactory,
    PokemonTypeFactory,
)
from tests.framework.factories.user_factory import UserFactory
from tests.framework.helpers.battle_helpers import build_battle_pair, ensure_round

_service = BattleService()


@allure.epic("Battle")
@allure.feature("Phase 5.5 — Support Move Rotation")
class TestSupportMoveRotation(BaseTest):

    @allure.story("Support move fires automatically when no cooldown active")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_support_fires_when_no_cooldown(self):
        # Arrange
        normal_type = PokemonTypeFactory(name="Normal")
        support_move = MoveFactory(
            slot_type=MoveSlotType.PASSIVE_1,
            power=0,  # non-offensive — targets ally
            cooldown=3,
            move_type=normal_type,
        )
        standard_move = MoveFactory(slot_type=MoveSlotType.STANDARD, power=40, move_type=normal_type)

        battle, team1, team2, slots1, slots2 = build_battle_pair()
        round_obj = ensure_round(battle, round_number=1)

        slot = slots1[0]
        user = UserFactory()
        species = PokemonFactory(primary_type=normal_type)
        op = OwnedPokemonFactory(
            owner=user,
            species=species,
            move_standard=standard_move,
            move_support=support_move,
        )
        slot.owned_pokemon = op
        slot.save(update_fields=["owned_pokemon"])

        # No cooldown active
        assert not MoveCooldown.objects.filter(slot=slot, move=support_move).exists()

        initial_log_count = BattleLog.objects.filter(battle=battle).count()

        # Act
        _service._execute_support_moves(battle, round_obj)

        # Assert — a STATUS log about the support move should appear
        new_logs = BattleLog.objects.filter(battle=battle).count()
        assert new_logs > initial_log_count, "Expected support move to generate log entries."

        support_log = BattleLog.objects.filter(
            battle=battle, log_type=LogType.STATUS
        ).last()
        assert support_log is not None
        assert "[Support]" in support_log.message

    @allure.story("Support move does NOT fire when cooldown is active")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_support_skipped_when_on_cooldown(self):
        # Arrange
        normal_type = PokemonTypeFactory(name="Normal")
        support_move = MoveFactory(
            slot_type=MoveSlotType.PASSIVE_1,
            power=0,
            cooldown=3,
            move_type=normal_type,
        )
        standard_move = MoveFactory(slot_type=MoveSlotType.STANDARD, power=40, move_type=normal_type)

        battle, team1, team2, slots1, slots2 = build_battle_pair()
        round_obj = ensure_round(battle, round_number=1)

        slot = slots1[0]
        user = UserFactory()
        species = PokemonFactory(primary_type=normal_type)
        op = OwnedPokemonFactory(
            owner=user,
            species=species,
            move_standard=standard_move,
            move_support=support_move,
        )
        slot.owned_pokemon = op
        slot.save(update_fields=["owned_pokemon"])

        # Place support move on cooldown
        MoveCooldown.objects.create(slot=slot, move=support_move, remaining_rounds=2)

        initial_log_count = BattleLog.objects.filter(battle=battle, log_type=LogType.STATUS).count()

        # Act
        _service._execute_support_moves(battle, round_obj)

        # Assert — no new STATUS logs (support was skipped)
        new_count = BattleLog.objects.filter(battle=battle, log_type=LogType.STATUS).count()
        assert new_count == initial_log_count, (
            "Support move should NOT fire when cooldown is active."
        )

    @allure.story("Support move cooldown is applied after firing")
    @allure.severity(allure.severity_level.NORMAL)
    def test_support_cooldown_applied_after_firing(self):
        # Arrange
        normal_type = PokemonTypeFactory(name="Normal")
        support_move = MoveFactory(
            slot_type=MoveSlotType.PASSIVE_1,
            power=0,
            cooldown=3,
            move_type=normal_type,
        )
        standard_move = MoveFactory(slot_type=MoveSlotType.STANDARD, power=40, move_type=normal_type)

        battle, team1, team2, slots1, slots2 = build_battle_pair()
        round_obj = ensure_round(battle, round_number=1)

        slot = slots1[0]
        user = UserFactory()
        species = PokemonFactory(primary_type=normal_type)
        op = OwnedPokemonFactory(
            owner=user,
            species=species,
            move_standard=standard_move,
            move_support=support_move,
        )
        slot.owned_pokemon = op
        slot.save(update_fields=["owned_pokemon"])

        # Act
        _service._execute_support_moves(battle, round_obj)

        # Assert — cooldown should now be active for support_move
        assert MoveCooldown.objects.filter(slot=slot, move=support_move).exists(), (
            "Expected MoveCooldown to be created after support move fires."
        )
