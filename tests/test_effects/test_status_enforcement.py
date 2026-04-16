"""
Phase 7 — Status enforcement tests.

Covers:
  - BLINDED: standard move is skipped; BattleLog created; no damage dealt
  - CONFUSED: 33% chance self-hit produces self-damage BattleLog
  - INFATUATED: 50% chance can_act returns False
  - SEEDED: applied_by_slot heals each tick equal to drain damage
"""
from unittest.mock import patch

import allure
import pytest

from apps.effects.constants import StatusCategory, StatusName
from apps.effects.engine import StatusEffectEngine
from apps.effects.models import ActiveStatusEffect, StatusEffect
from apps.game.models import BattleLog, BattleStatus, LogType
from apps.game.services import BattleService
from apps.pokemon.models import MoveSlotType

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.battle_factory import BattleFactory, BattleSlotFactory, BattleTeamFactory
from tests.framework.factories.effects_factory import ActiveStatusEffectFactory, StatusEffectFactory
from tests.framework.factories.pokemon_factory import MoveFactory, PokemonFactory, PokemonTypeFactory
from tests.framework.factories.user_factory import UserFactory
from tests.framework.helpers.battle_helpers import build_battle_pair, ensure_round

_svc = BattleService()
_engine = StatusEffectEngine()


def _get_or_create_se(name: str, category: str) -> StatusEffect:
    se, _ = StatusEffect.objects.get_or_create(
        name=name,
        defaults={"category": category, "description": "test"},
    )
    return se


def _minimal_round_setup():
    """Return (battle, team1, team2, slots1, slots2, round_obj)."""
    battle, team1, team2, slots1, slots2 = build_battle_pair()
    round_obj = ensure_round(battle, round_number=1)
    return battle, team1, team2, slots1, slots2, round_obj


def _execute_round_with_action(battle, attacker, move, target):
    """
    Call execute_round with a single action for attacker.

    Returns the BattleRound object.
    """
    actions = [{"slot_id": attacker.pk, "move_id": move.pk, "target_id": target.pk}]
    return _svc.execute_round(battle, actions, [])


# ===========================================================================
# TestBlinded
# ===========================================================================

@allure.epic("Battle")
@allure.feature("Phase 2 — Status Enforcement")
class TestBlinded(BaseTest):
    """BLINDED prevents standard moves; BattleLog created with reason."""

    @allure.story("BLINDED slot skips standard move — no BattleAction damage")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_blinded_skips_standard_attack(self):
        # Arrange
        blinded_se = _get_or_create_se(StatusName.BLINDED, StatusCategory.NARUTO)
        nt = PokemonTypeFactory(name="Normal")
        standard_move = MoveFactory(
            name="StdBlinded", move_type=nt, power=80,
            slot_type=MoveSlotType.STANDARD,
        )
        battle, team1, team2, slots1, slots2 = build_battle_pair(
            p1_moves=[standard_move],
        )
        attacker = slots1[0]
        target = slots2[0]
        initial_hp = target.current_hp

        ActiveStatusEffectFactory(slot=attacker, status=blinded_se)

        # Act — execute_round (creates its own BattleRound)
        _execute_round_with_action(battle, attacker, standard_move, target)

        # Assert — target HP unchanged (standard move was skipped)
        target.refresh_from_db()
        assert target.current_hp == initial_hp

    @allure.story("BLINDED creates a BattleLog explaining the skip")
    @allure.severity(allure.severity_level.NORMAL)
    def test_blinded_creates_log(self):
        # Arrange
        blinded_se = _get_or_create_se(StatusName.BLINDED, StatusCategory.NARUTO)
        nt = PokemonTypeFactory(name="Normal")
        standard_move = MoveFactory(
            name="StdBlindedLog", move_type=nt, power=80,
            slot_type=MoveSlotType.STANDARD,
        )
        battle, team1, team2, slots1, slots2 = build_battle_pair(
            p1_moves=[standard_move],
        )
        attacker = slots1[0]
        target = slots2[0]
        ActiveStatusEffectFactory(slot=attacker, status=blinded_se)

        # Act
        _execute_round_with_action(battle, attacker, standard_move, target)

        # Assert — "blinded" log exists
        blind_log = BattleLog.objects.filter(
            battle=battle,
            log_type=LogType.STATUS,
            message__icontains="blinded",
        ).first()
        assert blind_log is not None


# ===========================================================================
# TestConfused
# ===========================================================================

@allure.epic("Battle")
@allure.feature("Phase 2 — Status Enforcement")
class TestConfused(BaseTest):
    """CONFUSED: 33% chance the attacker hits itself."""

    @allure.story("CONFUSED self-hit creates a self-damage BattleLog")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_confused_self_hit_creates_log(self):
        # Arrange
        confused_se = StatusEffectFactory(confused=True)
        nt = PokemonTypeFactory(name="Normal")
        standard_move = MoveFactory(
            name="StdConfused", move_type=nt, power=80,
            slot_type=MoveSlotType.STANDARD,
        )
        battle, team1, team2, slots1, slots2 = build_battle_pair(
            p1_moves=[standard_move],
        )
        attacker = slots1[0]
        target = slots2[0]
        ActiveStatusEffectFactory(slot=attacker, status=confused_se)

        # Act — force the 33% self-hit by patching random.random
        with patch("apps.game.services.random.random", return_value=0.10):
            _execute_round_with_action(battle, attacker, standard_move, target)

        # Assert — self-damage log created
        self_hit_log = BattleLog.objects.filter(
            battle=battle,
            log_type=LogType.STATUS,
            message__icontains="confused",
        ).first()
        assert self_hit_log is not None
        assert "hurt itself" in self_hit_log.message

    @allure.story("CONFUSED self-hit reduces attacker HP")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_confused_self_hit_damages_attacker(self):
        # Arrange
        confused_se = StatusEffectFactory(confused=True)
        nt = PokemonTypeFactory(name="Normal")
        standard_move = MoveFactory(
            name="StdConfusedDmg", move_type=nt, power=80,
            slot_type=MoveSlotType.STANDARD,
        )
        battle, team1, team2, slots1, slots2 = build_battle_pair(
            p1_moves=[standard_move],
        )
        attacker = slots1[0]
        target = slots2[0]
        initial_attacker_hp = attacker.current_hp
        initial_target_hp = target.current_hp
        ActiveStatusEffectFactory(slot=attacker, status=confused_se)

        # Act — force self-hit
        with patch("apps.game.services.random.random", return_value=0.10):
            _execute_round_with_action(battle, attacker, standard_move, target)

        # Assert — attacker HP reduced, target HP unchanged
        attacker.refresh_from_db()
        target.refresh_from_db()
        assert attacker.current_hp < initial_attacker_hp
        assert target.current_hp == initial_target_hp

    @allure.story("CONFUSED — no self-hit when random roll > 0.33")
    @allure.severity(allure.severity_level.NORMAL)
    def test_confused_no_self_hit_when_roll_misses(self):
        # Arrange
        confused_se = StatusEffectFactory(confused=True)
        nt = PokemonTypeFactory(name="Normal")
        standard_move = MoveFactory(
            name="StdConfusedMiss", move_type=nt, power=80,
            slot_type=MoveSlotType.STANDARD,
        )
        battle, team1, team2, slots1, slots2 = build_battle_pair(
            p1_moves=[standard_move],
        )
        attacker = slots1[0]
        target = slots2[0]
        initial_attacker_hp = attacker.current_hp
        ActiveStatusEffectFactory(slot=attacker, status=confused_se)

        # Act — roll > 0.33 → no self-hit
        # Also patch randint for damage calc determinism; random > 0.33 skip self-hit branch
        with patch("apps.game.services.random.random", return_value=0.99):
            with patch("apps.game.services.random.randint", return_value=100):
                _execute_round_with_action(battle, attacker, standard_move, target)

        # Assert — attacker HP unchanged (no self-hit)
        attacker.refresh_from_db()
        assert attacker.current_hp == initial_attacker_hp


# ===========================================================================
# TestInfatuated
# ===========================================================================

@allure.epic("Battle")
@allure.feature("Phase 2 — Status Enforcement")
class TestInfatuated(BaseTest):
    """INFATUATED: 50% chance can_act returns False."""

    @allure.story("can_act returns False when INFATUATED and random roll < 0.50")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_infatuated_refuses_on_low_roll(self):
        # Arrange — create a minimal slot with INFATUATED
        infatuated_se = _get_or_create_se(StatusName.INFATUATED, StatusCategory.VOLATILE)
        battle, team1, team2, slots1, slots2 = build_battle_pair()
        slot = slots1[0]
        ActiveStatusEffectFactory(slot=slot, status=infatuated_se)

        # Act — force refusal
        with patch("apps.effects.engine.random.random", return_value=0.10):
            can, reason = _engine.can_act(slot)

        # Assert
        assert can is False
        assert reason == "infatuated"

    @allure.story("can_act returns True when INFATUATED and random roll >= 0.50")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_infatuated_acts_on_high_roll(self):
        # Arrange
        infatuated_se = _get_or_create_se(StatusName.INFATUATED, StatusCategory.VOLATILE)
        battle, team1, team2, slots1, slots2 = build_battle_pair()
        slot = slots1[0]
        ActiveStatusEffectFactory(slot=slot, status=infatuated_se)

        # Act — roll above refusal threshold
        with patch("apps.effects.engine.random.random", return_value=0.90):
            can, reason = _engine.can_act(slot)

        # Assert
        assert can is True
        assert reason == ""

    @allure.story("can_act returns True when no INFATUATED status present")
    @allure.severity(allure.severity_level.NORMAL)
    def test_can_act_true_without_infatuated(self):
        # Arrange — no statuses
        battle, team1, team2, slots1, slots2 = build_battle_pair()
        slot = slots1[0]

        # Act
        can, reason = _engine.can_act(slot)

        # Assert
        assert can is True


# ===========================================================================
# TestSeeded
# ===========================================================================

@allure.epic("Battle")
@allure.feature("Phase 2 — Status Enforcement")
class TestSeeded(BaseTest):
    """SEEDED drains HP from target; applied_by_slot heals equal amount."""

    @allure.story("applied_by_slot heals when SEEDED ticks damage")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_seeded_healer_gains_hp_on_tick(self):
        # Arrange — two slots: seeder (healer) and seeded (victim)
        seeded_se = _get_or_create_se(StatusName.SEEDED, StatusCategory.VOLATILE)
        battle, team1, team2, slots1, slots2 = build_battle_pair()
        victim = slots2[0]
        healer = slots1[0]

        # Reduce healer HP so healing is visible
        healer.current_hp = healer.max_hp - 50
        healer.save(update_fields=["current_hp"])
        hp_before_tick = healer.current_hp

        # Apply SEEDED to victim, with healer as applied_by_slot
        ActiveStatusEffect.objects.create(
            slot=victim,
            status=seeded_se,
            remaining_turns=3,
            applied_at_round=1,
            turns_active=0,
            applied_by_slot=healer,
        )

        # Act — tick statuses on victim
        _engine.tick_statuses(victim, round_number=1)

        # Assert — healer gained HP
        healer.refresh_from_db()
        assert healer.current_hp > hp_before_tick

    @allure.story("SEEDED drains HP from victim each tick")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_seeded_drains_victim_hp(self):
        # Arrange
        seeded_se = _get_or_create_se(StatusName.SEEDED, StatusCategory.VOLATILE)
        battle, team1, team2, slots1, slots2 = build_battle_pair()
        victim = slots2[0]
        healer = slots1[0]
        hp_before = victim.current_hp

        ActiveStatusEffect.objects.create(
            slot=victim,
            status=seeded_se,
            remaining_turns=3,
            applied_at_round=1,
            turns_active=0,
            applied_by_slot=healer,
        )

        # Act
        _engine.tick_statuses(victim, round_number=1)

        # Assert — victim HP decreased
        victim.refresh_from_db()
        assert victim.current_hp < hp_before

    @allure.story("SEEDED does not heal an already-fainted healer")
    @allure.severity(allure.severity_level.NORMAL)
    def test_seeded_no_heal_if_healer_fainted(self):
        # Arrange
        seeded_se = _get_or_create_se(StatusName.SEEDED, StatusCategory.VOLATILE)
        battle, team1, team2, slots1, slots2 = build_battle_pair()
        victim = slots2[0]
        healer = slots1[0]

        # Faint the healer
        healer.current_hp = 0
        healer.is_fainted = True
        healer.save(update_fields=["current_hp", "is_fainted"])
        hp_healer_before = healer.current_hp

        ActiveStatusEffect.objects.create(
            slot=victim,
            status=seeded_se,
            remaining_turns=3,
            applied_at_round=1,
            turns_active=0,
            applied_by_slot=healer,
        )

        # Act
        _engine.tick_statuses(victim, round_number=1)

        # Assert — fainted healer unchanged
        healer.refresh_from_db()
        assert healer.current_hp == hp_healer_before
