"""
Phase 7 — Held-Effect System tests.

Covers:
  - passive: heal_fraction restores HP each round start
  - passive: activation_chance = 0.0 never fires
  - on_hit: heal_fraction restores HP when target is hit
  - on_hit: damage_reflect deals fraction of damage_taken back to attacker
  - on_hit: max_activations cap prevents firing beyond limit
  - on_faint: revive_hp_fraction brings slot back from faint
  - on_status: status_cleanse removes all active statuses
  - on_status: status_cleanse + heal_fraction both fire in one activation
  - can_activate: False when cap reached
"""
import unittest.mock as mock

import allure
import pytest

from apps.game.models import BattleLog, BattleRound, BattleSlot, BattleStatus, LogType
from apps.game.models import BattleSlotHeldEffect
from apps.game.services import _resolve_held_effect
from apps.effects.models import ActiveStatusEffect
from apps.pokemon.models import HeldEffect

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.battle_factory import (
    BattleFactory,
    BattleSlotFactory,
    BattleTeamFactory,
)
from tests.framework.factories.effects_factory import (
    ActiveStatusEffectFactory,
    StatusEffectFactory,
)
from tests.framework.factories.pokemon_factory import PokemonFactory, PokemonTypeFactory
from tests.framework.factories.user_factory import UserFactory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_slot(hp: int = 200):
    ptype = PokemonTypeFactory(name="Normal")
    poke = PokemonFactory(primary_type=ptype, base_hp=100)
    return BattleSlotFactory(pokemon=poke, current_hp=hp, max_hp=hp, level=50)


def _make_round(slot) -> BattleRound:
    battle = slot.team.battle
    round_obj, _ = BattleRound.objects.get_or_create(battle=battle, round_number=1)
    return round_obj


def _attach_held_effect(
    slot: BattleSlot,
    trigger: str,
    effect_data: dict,
    activation_chance: float = 1.0,
    max_activations: int = 0,
) -> BattleSlotHeldEffect:
    """Create a HeldEffect and attach it to a slot via BattleSlotHeldEffect."""
    effect = HeldEffect.objects.create(
        name=f"TestEffect_{trigger}_{id(slot)}",
        trigger_condition=trigger,
        effect_data=effect_data,
        activation_chance=activation_chance,
        max_activations=max_activations,
    )
    return BattleSlotHeldEffect.objects.create(slot=slot, effect=effect)


# ===========================================================================
# TestPassiveHeldEffect
# ===========================================================================

@allure.epic("Battle")
@allure.feature("Held Effects — Passive")
class TestPassiveHeldEffect(BaseTest):

    @allure.story("passive heal_fraction restores HP each round")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_passive_heal_fraction_restores_hp(self):
        # Arrange — slot at 100 HP (out of 200)
        slot = _make_slot(hp=200)
        slot.current_hp = 100
        slot.save(update_fields=["current_hp"])
        round_obj = _make_round(slot)
        _attach_held_effect(slot, "passive", {"heal_fraction": 0.10})  # heal 10% max HP = 20

        # Act
        _resolve_held_effect("passive", slot, round_obj)
        slot.refresh_from_db()

        # Assert — healed by 20 (10% of 200)
        assert slot.current_hp == 120

    @allure.story("passive does not overheal beyond max_hp")
    @allure.severity(allure.severity_level.NORMAL)
    def test_passive_heal_does_not_overheal(self):
        slot = _make_slot(hp=200)
        slot.current_hp = 195
        slot.save(update_fields=["current_hp"])
        round_obj = _make_round(slot)
        _attach_held_effect(slot, "passive", {"heal_fraction": 0.20})  # would heal 40 → cap at 200

        _resolve_held_effect("passive", slot, round_obj)
        slot.refresh_from_db()

        assert slot.current_hp == 200

    @allure.story("passive with activation_chance = 0.0 never fires")
    @allure.severity(allure.severity_level.NORMAL)
    def test_passive_zero_chance_never_fires(self):
        slot = _make_slot(hp=200)
        slot.current_hp = 100
        slot.save(update_fields=["current_hp"])
        round_obj = _make_round(slot)
        _attach_held_effect(slot, "passive", {"heal_fraction": 0.50}, activation_chance=0.0)

        # With activation_chance=0.0, random.random() will always be > 0.0
        _resolve_held_effect("passive", slot, round_obj)
        slot.refresh_from_db()

        # No healing happened
        assert slot.current_hp == 100

    @allure.story("passive fires only for matching trigger (on_hit does not fire passive)")
    @allure.severity(allure.severity_level.MINOR)
    def test_passive_trigger_mismatch_does_not_fire(self):
        slot = _make_slot(hp=200)
        slot.current_hp = 100
        slot.save(update_fields=["current_hp"])
        round_obj = _make_round(slot)
        _attach_held_effect(slot, "on_hit", {"heal_fraction": 0.50})

        # Call with passive trigger — should not fire on_hit effect
        _resolve_held_effect("passive", slot, round_obj)
        slot.refresh_from_db()

        assert slot.current_hp == 100


# ===========================================================================
# TestOnHitHeldEffect
# ===========================================================================

@allure.epic("Battle")
@allure.feature("Held Effects — On Hit")
class TestOnHitHeldEffect(BaseTest):

    @allure.story("on_hit heal_fraction restores HP when slot takes damage")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_on_hit_heal_fraction(self):
        slot = _make_slot(hp=200)
        slot.current_hp = 100
        slot.save(update_fields=["current_hp"])
        round_obj = _make_round(slot)
        _attach_held_effect(slot, "on_hit", {"heal_fraction": 0.10})  # 20 HP

        _resolve_held_effect("on_hit", slot, round_obj, damage_taken=50)
        slot.refresh_from_db()

        assert slot.current_hp == 120

    @allure.story("on_hit damage_reflect deals fraction of damage_taken back to attacker")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_on_hit_damage_reflect(self):
        slot = _make_slot(hp=200)
        attacker = _make_slot(hp=200)
        round_obj = _make_round(slot)
        _attach_held_effect(slot, "on_hit", {"damage_reflect": 0.50})  # reflect 50% of 80 = 40

        _resolve_held_effect("on_hit", slot, round_obj, damage_taken=80, attacker_slot=attacker)
        attacker.refresh_from_db()

        assert attacker.current_hp == 200 - 40  # 160

    @allure.story("on_hit damage_reflect does not fire when damage_taken = 0")
    @allure.severity(allure.severity_level.NORMAL)
    def test_on_hit_reflect_skipped_on_zero_damage(self):
        slot = _make_slot(hp=200)
        attacker = _make_slot(hp=200)
        round_obj = _make_round(slot)
        _attach_held_effect(slot, "on_hit", {"damage_reflect": 1.0})

        _resolve_held_effect("on_hit", slot, round_obj, damage_taken=0, attacker_slot=attacker)
        attacker.refresh_from_db()

        assert attacker.current_hp == 200  # untouched

    @allure.story("on_hit max_activations = 1 caps at one activation")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_on_hit_max_activations_cap(self):
        slot = _make_slot(hp=200)
        slot.current_hp = 100
        slot.save(update_fields=["current_hp"])
        round_obj = _make_round(slot)
        _attach_held_effect(slot, "on_hit", {"heal_fraction": 0.10}, max_activations=1)

        # First activation — should fire
        _resolve_held_effect("on_hit", slot, round_obj, damage_taken=50)
        slot.refresh_from_db()
        hp_after_first = slot.current_hp

        # Second activation — should be blocked by cap
        _resolve_held_effect("on_hit", slot, round_obj, damage_taken=50)
        slot.refresh_from_db()

        assert slot.current_hp == hp_after_first  # no further healing

    @allure.story("can_activate is False once activations_used reaches max_activations")
    @allure.severity(allure.severity_level.NORMAL)
    def test_can_activate_false_when_capped(self):
        slot = _make_slot(hp=200)
        hes = _attach_held_effect(slot, "on_hit", {"heal_fraction": 0.10}, max_activations=2)
        hes.activations_used = 2
        hes.save(update_fields=["activations_used"])

        assert hes.can_activate is False

    @allure.story("can_activate is True when max_activations = 0 (unlimited)")
    @allure.severity(allure.severity_level.NORMAL)
    def test_can_activate_unlimited(self):
        slot = _make_slot(hp=200)
        hes = _attach_held_effect(slot, "on_hit", {"heal_fraction": 0.10}, max_activations=0)
        hes.activations_used = 999
        hes.save(update_fields=["activations_used"])

        assert hes.can_activate is True


# ===========================================================================
# TestOnFaintHeldEffect
# ===========================================================================

@allure.epic("Battle")
@allure.feature("Held Effects — On Faint")
class TestOnFaintHeldEffect(BaseTest):

    @allure.story("on_faint revive_hp_fraction revives fainted slot")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_on_faint_revives_slot(self):
        slot = _make_slot(hp=200)
        slot.current_hp = 0
        slot.is_fainted = True
        slot.save(update_fields=["current_hp", "is_fainted"])
        round_obj = _make_round(slot)
        _attach_held_effect(slot, "on_faint", {"revive_hp_fraction": 0.10})  # 20 HP

        _resolve_held_effect("on_faint", slot, round_obj, damage_taken=200)
        slot.refresh_from_db()

        assert slot.current_hp == 20
        assert slot.is_fainted is False

    @allure.story("on_faint revive only fires when slot is actually fainted")
    @allure.severity(allure.severity_level.NORMAL)
    def test_on_faint_skipped_when_not_fainted(self):
        slot = _make_slot(hp=200)
        # slot is alive (not fainted)
        round_obj = _make_round(slot)
        _attach_held_effect(slot, "on_faint", {"revive_hp_fraction": 0.50})

        _resolve_held_effect("on_faint", slot, round_obj, damage_taken=50)
        slot.refresh_from_db()

        # HP unchanged (not fainted, so revive doesn't apply)
        assert slot.current_hp == 200
        assert slot.is_fainted is False

    @allure.story("on_faint creates a BattleLog entry when it fires")
    @allure.severity(allure.severity_level.NORMAL)
    def test_on_faint_creates_log(self):
        slot = _make_slot(hp=200)
        slot.current_hp = 0
        slot.is_fainted = True
        slot.save(update_fields=["current_hp", "is_fainted"])
        round_obj = _make_round(slot)
        _attach_held_effect(slot, "on_faint", {"revive_hp_fraction": 0.10})

        _resolve_held_effect("on_faint", slot, round_obj, damage_taken=200)

        assert BattleLog.objects.filter(
            battle=slot.team.battle,
            log_type=LogType.STATUS,
        ).exists()


# ===========================================================================
# TestOnStatusHeldEffect
# ===========================================================================

@allure.epic("Battle")
@allure.feature("Held Effects — On Status")
class TestOnStatusHeldEffect(BaseTest):

    @allure.story("on_status status_cleanse removes all active statuses")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_on_status_cleanse_removes_statuses(self):
        slot = _make_slot(hp=200)
        round_obj = _make_round(slot)

        # Apply a couple of statuses
        burn = StatusEffectFactory(burned=True)
        confused = StatusEffectFactory(confused=True)
        ActiveStatusEffectFactory(slot=slot, status=burn)
        ActiveStatusEffectFactory(slot=slot, status=confused)
        assert ActiveStatusEffect.objects.filter(slot=slot).count() == 2

        _attach_held_effect(slot, "on_status", {"status_cleanse": True})

        _resolve_held_effect("on_status", slot, round_obj)

        assert ActiveStatusEffect.objects.filter(slot=slot).count() == 0

    @allure.story("on_status cleanse + heal both fire in one activation")
    @allure.severity(allure.severity_level.NORMAL)
    def test_on_status_cleanse_and_heal_combined(self):
        slot = _make_slot(hp=200)
        slot.current_hp = 120
        slot.save(update_fields=["current_hp"])
        round_obj = _make_round(slot)

        burn = StatusEffectFactory(burned=True)
        ActiveStatusEffectFactory(slot=slot, status=burn)
        _attach_held_effect(slot, "on_status", {"status_cleanse": True, "heal_fraction": 0.10})

        _resolve_held_effect("on_status", slot, round_obj)
        slot.refresh_from_db()

        # Status cleared
        assert ActiveStatusEffect.objects.filter(slot=slot).count() == 0
        # HP restored by 10% = 20 HP
        assert slot.current_hp == 140

    @allure.story("on_status creates BattleLog entry when fired")
    @allure.severity(allure.severity_level.MINOR)
    def test_on_status_creates_log(self):
        slot = _make_slot(hp=200)
        round_obj = _make_round(slot)
        _attach_held_effect(slot, "on_status", {"status_cleanse": True})

        _resolve_held_effect("on_status", slot, round_obj)

        assert BattleLog.objects.filter(
            battle=slot.team.battle,
            log_type=LogType.STATUS,
        ).exists()

    @allure.story("on_status does not fire when trigger is on_hit")
    @allure.severity(allure.severity_level.MINOR)
    def test_on_status_does_not_fire_on_wrong_trigger(self):
        slot = _make_slot(hp=200)
        slot.current_hp = 100
        slot.save(update_fields=["current_hp"])
        round_obj = _make_round(slot)
        _attach_held_effect(slot, "on_hit", {"heal_fraction": 0.50})

        # Fire with on_status trigger — should not heal
        _resolve_held_effect("on_status", slot, round_obj)
        slot.refresh_from_db()

        assert slot.current_hp == 100
