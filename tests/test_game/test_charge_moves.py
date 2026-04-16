"""
Phase 7 — Charge move 2-round flow tests.

Covers:
  - Round 1 (charge): CHARGING status applied to attacker; BattleAction.damage_dealt == 0
  - Round 2 (release): CHARGING removed; full damage dealt to target
  - Non-charge move: no CHARGING applied; damage dealt normally in round 1
"""
import allure
import pytest

from apps.effects.constants import StatusCategory, StatusName
from apps.effects.engine import StatusEffectEngine
from apps.effects.models import StatusEffect
from apps.game.services import ComboChainEngine

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.pokemon_factory import MoveFactory, PokemonTypeFactory
from tests.framework.helpers.battle_helpers import build_battle_pair, ensure_round

_chain = ComboChainEngine()
_engine = StatusEffectEngine()


def _ensure_charging_se() -> StatusEffect:
    """Get or create the CHARGING StatusEffect (seeded as pk=40 in fixture)."""
    se, _ = StatusEffect.objects.get_or_create(
        name=StatusName.CHARGING,
        defaults={
            "category": StatusCategory.ADVANCED,
            "description": "Charging move — releases next round.",
            "default_duration": 1,
        },
    )
    return se


def _minimal_battle():
    """Return (battle, team1, team2, slots1, slots2, round_obj)."""
    battle, team1, team2, slots1, slots2 = build_battle_pair()
    round_obj = ensure_round(battle, round_number=1)
    return battle, team1, team2, slots1, slots2, round_obj


# ===========================================================================
# TestChargeRound1
# ===========================================================================

@allure.epic("Battle")
@allure.feature("Phase 6 — Charge Move")
class TestChargeRound1(BaseTest):
    """Round 1 (charge): CHARGING applied to attacker; damage_dealt == 0."""

    @allure.story("Round 1 charge: damage_dealt is zero")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_charge_round1_damage_is_zero(self):
        # Arrange
        _ensure_charging_se()
        nt = PokemonTypeFactory(name="Normal")
        charge_move = MoveFactory(
            name="ChargeRound1Dmg",
            move_type=nt,
            power=120,
            is_charge_move=True,
        )
        battle, team1, team2, slots1, slots2, round_obj = _minimal_battle()
        attacker = slots1[0]
        target = slots2[0]

        # Act — first call (charging round)
        action = _chain._execute_move(
            round_obj=round_obj,
            attacker_slot=attacker,
            move=charge_move,
            target_slot=target,
            chain_position=0,
            is_combo=False,
        )

        # Assert — no damage in round 1
        assert action.damage_dealt == 0

    @allure.story("Round 1 charge: CHARGING status applied to attacker")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_charge_round1_charging_status_applied(self):
        # Arrange
        _ensure_charging_se()
        nt = PokemonTypeFactory(name="Normal")
        charge_move = MoveFactory(
            name="ChargeRound1Status",
            move_type=nt,
            power=120,
            is_charge_move=True,
        )
        battle, team1, team2, slots1, slots2, round_obj = _minimal_battle()
        attacker = slots1[0]
        target = slots2[0]

        # Act
        _chain._execute_move(
            round_obj=round_obj,
            attacker_slot=attacker,
            move=charge_move,
            target_slot=target,
            chain_position=0,
            is_combo=False,
        )

        # Assert — attacker has CHARGING status
        assert _engine.has_status(attacker, StatusName.CHARGING)

    @allure.story("Round 1 charge: target HP unchanged")
    @allure.severity(allure.severity_level.NORMAL)
    def test_charge_round1_target_hp_unchanged(self):
        # Arrange
        _ensure_charging_se()
        nt = PokemonTypeFactory(name="Normal")
        charge_move = MoveFactory(
            name="ChargeRound1HP",
            move_type=nt,
            power=120,
            is_charge_move=True,
        )
        battle, team1, team2, slots1, slots2, round_obj = _minimal_battle()
        attacker = slots1[0]
        target = slots2[0]
        initial_hp = target.current_hp

        # Act
        _chain._execute_move(
            round_obj=round_obj,
            attacker_slot=attacker,
            move=charge_move,
            target_slot=target,
            chain_position=0,
            is_combo=False,
        )

        # Assert — target untouched
        target.refresh_from_db()
        assert target.current_hp == initial_hp


# ===========================================================================
# TestChargeRound2
# ===========================================================================

@allure.epic("Battle")
@allure.feature("Phase 6 — Charge Move")
class TestChargeRound2(BaseTest):
    """Round 2 (release): CHARGING removed; full damage dealt."""

    @allure.story("Round 2 release: full damage dealt to target")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_charge_round2_deals_damage(self):
        # Arrange
        charging_se = _ensure_charging_se()
        nt = PokemonTypeFactory(name="Normal")
        charge_move = MoveFactory(
            name="ChargeRound2Dmg",
            move_type=nt,
            power=120,
            is_charge_move=True,
        )
        battle, team1, team2, slots1, slots2, round_obj = _minimal_battle()
        attacker = slots1[0]
        target = slots2[0]

        # Pre-apply CHARGING (simulates that round 1 already happened)
        _engine.apply_status(attacker, charging_se, round_number=1)

        # Act — second call (release round)
        action = _chain._execute_move(
            round_obj=round_obj,
            attacker_slot=attacker,
            move=charge_move,
            target_slot=target,
            chain_position=0,
            is_combo=False,
        )

        # Assert — damage dealt
        assert action.damage_dealt > 0

    @allure.story("Round 2 release: CHARGING status removed from attacker")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_charge_round2_charging_status_removed(self):
        # Arrange
        charging_se = _ensure_charging_se()
        nt = PokemonTypeFactory(name="Normal")
        charge_move = MoveFactory(
            name="ChargeRound2Remove",
            move_type=nt,
            power=120,
            is_charge_move=True,
        )
        battle, team1, team2, slots1, slots2, round_obj = _minimal_battle()
        attacker = slots1[0]
        target = slots2[0]

        # Pre-apply CHARGING
        _engine.apply_status(attacker, charging_se, round_number=1)
        assert _engine.has_status(attacker, StatusName.CHARGING)

        # Act
        _chain._execute_move(
            round_obj=round_obj,
            attacker_slot=attacker,
            move=charge_move,
            target_slot=target,
            chain_position=0,
            is_combo=False,
        )

        # Assert — CHARGING removed after release
        assert not _engine.has_status(attacker, StatusName.CHARGING)

    @allure.story("Round 2 release: target HP is reduced")
    @allure.severity(allure.severity_level.NORMAL)
    def test_charge_round2_target_hp_reduced(self):
        # Arrange
        charging_se = _ensure_charging_se()
        nt = PokemonTypeFactory(name="Normal")
        charge_move = MoveFactory(
            name="ChargeRound2HPDrop",
            move_type=nt,
            power=120,
            is_charge_move=True,
        )
        battle, team1, team2, slots1, slots2, round_obj = _minimal_battle()
        attacker = slots1[0]
        target = slots2[0]
        initial_hp = target.current_hp

        _engine.apply_status(attacker, charging_se, round_number=1)

        # Act
        _chain._execute_move(
            round_obj=round_obj,
            attacker_slot=attacker,
            move=charge_move,
            target_slot=target,
            chain_position=0,
            is_combo=False,
        )

        # Assert
        target.refresh_from_db()
        assert target.current_hp < initial_hp


# ===========================================================================
# TestNonChargeMove
# ===========================================================================

@allure.epic("Battle")
@allure.feature("Phase 6 — Charge Move")
class TestNonChargeMove(BaseTest):
    """Non-charge moves deal damage immediately with no CHARGING state."""

    @allure.story("Non-charge move deals damage in round 1")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_non_charge_move_deals_damage_immediately(self):
        # Arrange
        _ensure_charging_se()
        nt = PokemonTypeFactory(name="Normal")
        regular_move = MoveFactory(
            name="RegularInstant",
            move_type=nt,
            power=80,
            is_charge_move=False,
        )
        battle, team1, team2, slots1, slots2, round_obj = _minimal_battle()
        attacker = slots1[0]
        target = slots2[0]

        # Act
        action = _chain._execute_move(
            round_obj=round_obj,
            attacker_slot=attacker,
            move=regular_move,
            target_slot=target,
            chain_position=0,
            is_combo=False,
        )

        # Assert — damage dealt immediately
        assert action.damage_dealt > 0

    @allure.story("Non-charge move does not apply CHARGING status")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_non_charge_move_no_charging_status(self):
        # Arrange
        _ensure_charging_se()
        nt = PokemonTypeFactory(name="Normal")
        regular_move = MoveFactory(
            name="RegularNoCharge",
            move_type=nt,
            power=80,
            is_charge_move=False,
        )
        battle, team1, team2, slots1, slots2, round_obj = _minimal_battle()
        attacker = slots1[0]
        target = slots2[0]

        # Act
        _chain._execute_move(
            round_obj=round_obj,
            attacker_slot=attacker,
            move=regular_move,
            target_slot=target,
            chain_position=0,
            is_combo=False,
        )

        # Assert — no CHARGING on attacker
        assert not _engine.has_status(attacker, StatusName.CHARGING)

    @allure.story("Charge round 1 vs non-charge: only charge move defers damage")
    @allure.severity(allure.severity_level.NORMAL)
    def test_charge_defers_while_regular_fires_immediately(self):
        # Arrange — two different slots: one uses charge move, one uses regular
        _ensure_charging_se()
        nt = PokemonTypeFactory(name="Normal")
        charge_move = MoveFactory(
            name="ChargeSideBySide",
            move_type=nt,
            power=120,
            is_charge_move=True,
        )
        regular_move = MoveFactory(
            name="RegularSideBySide",
            move_type=nt,
            power=80,
            is_charge_move=False,
        )
        battle, team1, team2, slots1, slots2, round_obj = _minimal_battle()
        charge_attacker = slots1[0]
        regular_attacker = slots1[1]
        target = slots2[0]

        # Act
        charge_action = _chain._execute_move(
            round_obj=round_obj,
            attacker_slot=charge_attacker,
            move=charge_move,
            target_slot=target,
            chain_position=0,
            is_combo=False,
        )
        regular_action = _chain._execute_move(
            round_obj=round_obj,
            attacker_slot=regular_attacker,
            move=regular_move,
            target_slot=target,
            chain_position=0,
            is_combo=False,
        )

        # Assert — charge deferred (0 dmg), regular immediate (>0 dmg)
        assert charge_action.damage_dealt == 0
        assert regular_action.damage_dealt > 0
