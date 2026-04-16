"""
Phase 1 — Battle logging tests.

Verifies that every executed attack produces a BattleLog ACTION entry, including
faint logs, status-applied logs, and combo-typed logs for chain moves.
"""
import allure
import pytest

from apps.game.models import BattleLog, LogType
from apps.game.services import ComboChainEngine
from apps.pokemon.models import MoveSlotType

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.effects_factory import StatusEffectFactory
from tests.framework.factories.pokemon_factory import MoveFactory, PokemonTypeFactory
from tests.framework.helpers.battle_helpers import build_battle_pair, ensure_round

_chain = ComboChainEngine()


@allure.epic("Battle")
@allure.feature("Phase 1 — Battle Logging")
class TestBattleLogging(BaseTest):
    """Every _execute_move call must produce at least one BattleLog ACTION entry."""

    @allure.story("Normal attack produces an ACTION log entry")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_normal_attack_creates_action_log(self):
        # Arrange
        normal_type = PokemonTypeFactory(name="Normal")
        move = MoveFactory(slot_type=MoveSlotType.STANDARD, power=50, move_type=normal_type)

        battle, team1, team2, slots1, slots2 = build_battle_pair()
        round_obj = ensure_round(battle, round_number=1)
        attacker = slots1[0]
        target = slots2[0]
        target.current_hp = 500
        target.max_hp = 500
        target.save(update_fields=["current_hp", "max_hp"])

        initial_log_count = BattleLog.objects.filter(
            battle=battle, log_type=LogType.ACTION
        ).count()

        # Act
        _chain._execute_move(
            round_obj=round_obj,
            attacker_slot=attacker,
            move=move,
            target_slot=target,
            chain_position=0,
            is_combo=False,
        )

        # Assert
        new_log_count = BattleLog.objects.filter(
            battle=battle, log_type=LogType.ACTION
        ).count()
        assert new_log_count == initial_log_count + 1, (
            "Expected exactly 1 new ACTION log entry after a normal attack."
        )

    @allure.story("Combo move produces a COMBO log entry")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_combo_attack_creates_combo_log(self):
        # Arrange
        normal_type = PokemonTypeFactory(name="Normal")
        move = MoveFactory(slot_type=MoveSlotType.CHASE, power=50, move_type=normal_type)

        battle, team1, team2, slots1, slots2 = build_battle_pair()
        round_obj = ensure_round(battle, round_number=1)
        attacker = slots1[0]
        target = slots2[0]
        target.current_hp = 500
        target.max_hp = 500
        target.save(update_fields=["current_hp", "max_hp"])

        # Act
        _chain._execute_move(
            round_obj=round_obj,
            attacker_slot=attacker,
            move=move,
            target_slot=target,
            chain_position=1,
            is_combo=True,
        )

        # Assert
        combo_logs = BattleLog.objects.filter(battle=battle, log_type=LogType.COMBO)
        assert combo_logs.count() >= 1, "Expected at least 1 COMBO log entry for a combo move."
        assert "↳ [COMBO]" in combo_logs.first().message

    @allure.story("Faint produces a FAINT log entry")
    @allure.severity(allure.severity_level.NORMAL)
    def test_faint_creates_faint_log(self):
        # Arrange
        normal_type = PokemonTypeFactory(name="Normal")
        move = MoveFactory(slot_type=MoveSlotType.STANDARD, power=9999, move_type=normal_type)

        battle, team1, team2, slots1, slots2 = build_battle_pair()
        round_obj = ensure_round(battle, round_number=1)
        attacker = slots1[0]
        target = slots2[0]
        # Low HP so the hit is lethal
        target.current_hp = 1
        target.max_hp = 1
        target.save(update_fields=["current_hp", "max_hp"])

        # Act
        _chain._execute_move(
            round_obj=round_obj,
            attacker_slot=attacker,
            move=move,
            target_slot=target,
            chain_position=0,
            is_combo=False,
        )

        # Assert
        faint_logs = BattleLog.objects.filter(battle=battle, log_type=LogType.FAINT)
        assert faint_logs.count() >= 1, "Expected at least 1 FAINT log entry when target faints."
        assert "fainted" in faint_logs.first().message.lower()

    @allure.story("Log message includes attacker, move name, target, and damage")
    @allure.severity(allure.severity_level.NORMAL)
    def test_action_log_message_content(self):
        # Arrange
        normal_type = PokemonTypeFactory(name="Normal")
        move = MoveFactory(name="TestSlam", slot_type=MoveSlotType.STANDARD, power=50, move_type=normal_type)

        battle, team1, team2, slots1, slots2 = build_battle_pair()
        round_obj = ensure_round(battle, round_number=1)
        attacker = slots1[0]
        target = slots2[0]
        target.current_hp = 500
        target.max_hp = 500
        target.save(update_fields=["current_hp", "max_hp"])

        # Act
        _chain._execute_move(
            round_obj=round_obj,
            attacker_slot=attacker,
            move=move,
            target_slot=target,
            chain_position=0,
            is_combo=False,
        )

        # Assert
        log = BattleLog.objects.filter(battle=battle, log_type=LogType.ACTION).last()
        assert log is not None
        assert attacker.pokemon.name in log.message
        assert "TestSlam" in log.message
        assert target.pokemon.name in log.message
