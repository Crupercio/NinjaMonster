"""
Phase 7 — Physical State System tests (StatusEffectEngine layer).

Covers:
  - Mutual exclusivity of AIRBORNE / LAUNCHED / KNOCKBACK
  - is_grounded() query
  - clear_physical_statuses()
  - remove_volatile_statuses() clears physical / utility / advanced states
  - STATE_LOCKED recorded in engine constants
"""
import allure
import pytest

from apps.effects.constants import (
    ADVANCED_STATUSES,
    PHYSICAL_STATUSES,
    UTILITY_STATUSES,
    StatusCategory,
    StatusName,
)
from apps.effects.engine import StatusEffectEngine
from apps.effects.models import ActiveStatusEffect, StatusEffect

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.battle_factory import BattleSlotFactory
from tests.framework.factories.effects_factory import (
    ActiveStatusEffectFactory,
    StatusEffectFactory,
)
from tests.framework.factories.pokemon_factory import PokemonFactory, PokemonTypeFactory

_engine = StatusEffectEngine()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_create_status(name: str, category: str) -> StatusEffect:
    se, _ = StatusEffect.objects.get_or_create(
        name=name,
        defaults={"category": category, "description": "test"},
    )
    return se


def _normal_slot(hp: int = 150) -> "BattleSlot":  # type: ignore[name-defined]
    ptype = PokemonTypeFactory(name="Normal")
    poke = PokemonFactory(primary_type=ptype, base_hp=100)
    return BattleSlotFactory(pokemon=poke, current_hp=hp, max_hp=hp)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def slot():
    return _normal_slot()


@pytest.fixture()
def airborne_status():
    return _get_or_create_status(StatusName.AIRBORNE, StatusCategory.PHYSICAL)


@pytest.fixture()
def launched_status():
    return _get_or_create_status(StatusName.LAUNCHED, StatusCategory.PHYSICAL)


@pytest.fixture()
def knockback_status():
    return _get_or_create_status(StatusName.KNOCKBACK, StatusCategory.PHYSICAL)


@pytest.fixture()
def grounded_status():
    return _get_or_create_status(StatusName.GROUNDED, StatusCategory.PHYSICAL)


@pytest.fixture()
def shielded_status():
    return _get_or_create_status(StatusName.SHIELDED, StatusCategory.UTILITY)


@pytest.fixture()
def hidden_status():
    return _get_or_create_status(StatusName.HIDDEN, StatusCategory.UTILITY)


@pytest.fixture()
def immune_status():
    return _get_or_create_status(StatusName.IMMUNE, StatusCategory.UTILITY)


@pytest.fixture()
def chain_breaker_status():
    return _get_or_create_status(StatusName.CHAIN_BREAKER, StatusCategory.ADVANCED)


@pytest.fixture()
def state_locked_status():
    return _get_or_create_status(StatusName.STATE_LOCKED, StatusCategory.ADVANCED)


# ===========================================================================
# TestPhysicalStateMutualExclusivity
# ===========================================================================

@allure.epic("Effects")
@allure.feature("Physical States")
class TestPhysicalStateMutualExclusivity(BaseTest):

    @allure.story("Applying AIRBORNE clears existing LAUNCHED")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_airborne_clears_launched(self, slot, airborne_status, launched_status):
        # Arrange — slot already has LAUNCHED
        ActiveStatusEffectFactory(slot=slot, status=launched_status, remaining_turns=1)
        assert _engine.has_status(slot, StatusName.LAUNCHED)

        # Act — apply AIRBORNE
        result = _engine.apply_status(slot, airborne_status, round_number=1)

        # Assert — LAUNCHED gone, AIRBORNE active
        assert result is not None
        assert _engine.has_status(slot, StatusName.AIRBORNE)
        assert not _engine.has_status(slot, StatusName.LAUNCHED)

    @allure.story("Applying LAUNCHED clears existing AIRBORNE")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_launched_clears_airborne(self, slot, airborne_status, launched_status):
        # Arrange
        ActiveStatusEffectFactory(slot=slot, status=airborne_status)
        assert _engine.has_status(slot, StatusName.AIRBORNE)

        # Act
        result = _engine.apply_status(slot, launched_status, round_number=1)

        # Assert
        assert result is not None
        assert _engine.has_status(slot, StatusName.LAUNCHED)
        assert not _engine.has_status(slot, StatusName.AIRBORNE)

    @allure.story("Applying KNOCKBACK clears existing AIRBORNE")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_knockback_clears_airborne(self, slot, airborne_status, knockback_status):
        # Arrange
        ActiveStatusEffectFactory(slot=slot, status=airborne_status)

        # Act
        result = _engine.apply_status(slot, knockback_status, round_number=1)

        # Assert
        assert result is not None
        assert _engine.has_status(slot, StatusName.KNOCKBACK)
        assert not _engine.has_status(slot, StatusName.AIRBORNE)

    @allure.story("Applying AIRBORNE when KNOCKBACK active clears KNOCKBACK")
    @allure.severity(allure.severity_level.NORMAL)
    def test_airborne_clears_knockback(self, slot, airborne_status, knockback_status):
        # Arrange
        ActiveStatusEffectFactory(slot=slot, status=knockback_status, remaining_turns=1)

        # Act
        result = _engine.apply_status(slot, airborne_status, round_number=1)

        # Assert
        assert result is not None
        assert _engine.has_status(slot, StatusName.AIRBORNE)
        assert not _engine.has_status(slot, StatusName.KNOCKBACK)

    @allure.story("Only one physical state exists at a time")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_only_one_physical_state_at_a_time(self, slot, airborne_status, launched_status, knockback_status):
        _engine.apply_status(slot, airborne_status, round_number=1)
        _engine.apply_status(slot, launched_status, round_number=1)
        _engine.apply_status(slot, knockback_status, round_number=1)

        physical_count = ActiveStatusEffect.objects.filter(
            slot=slot,
            status__name__in=list(PHYSICAL_STATUSES),
        ).count()
        assert physical_count == 1
        assert _engine.has_status(slot, StatusName.KNOCKBACK)


# ===========================================================================
# TestIsGrounded
# ===========================================================================

@allure.epic("Effects")
@allure.feature("Physical States")
class TestIsGrounded(BaseTest):

    @allure.story("Slot with no physical state is grounded")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_no_physical_state_is_grounded(self, slot):
        assert _engine.is_grounded(slot) is True

    @allure.story("AIRBORNE slot is not grounded")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_airborne_is_not_grounded(self, slot, airborne_status):
        ActiveStatusEffectFactory(slot=slot, status=airborne_status)
        assert _engine.is_grounded(slot) is False

    @allure.story("LAUNCHED slot is not grounded")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_launched_is_not_grounded(self, slot, launched_status):
        ActiveStatusEffectFactory(slot=slot, status=launched_status, remaining_turns=1)
        assert _engine.is_grounded(slot) is False

    @allure.story("KNOCKBACK slot is not grounded")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_knockback_is_not_grounded(self, slot, knockback_status):
        ActiveStatusEffectFactory(slot=slot, status=knockback_status, remaining_turns=1)
        assert _engine.is_grounded(slot) is False

    @allure.story("Grounded after physical state cleared")
    @allure.severity(allure.severity_level.NORMAL)
    def test_grounded_after_clear(self, slot, airborne_status):
        ActiveStatusEffectFactory(slot=slot, status=airborne_status)
        assert _engine.is_grounded(slot) is False

        _engine.clear_physical_statuses(slot)
        assert _engine.is_grounded(slot) is True


# ===========================================================================
# TestClearPhysicalStatuses
# ===========================================================================

@allure.epic("Effects")
@allure.feature("Physical States")
class TestClearPhysicalStatuses(BaseTest):

    @allure.story("clear_physical_statuses removes all physical states")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_clear_removes_physical(self, slot, airborne_status):
        ActiveStatusEffectFactory(slot=slot, status=airborne_status)

        count = _engine.clear_physical_statuses(slot)

        assert count == 1
        assert not _engine.has_status(slot, StatusName.AIRBORNE)

    @allure.story("clear_physical_statuses does not remove persistent/volatile statuses")
    @allure.severity(allure.severity_level.NORMAL)
    def test_clear_physical_preserves_other_statuses(self, slot):
        burned = StatusEffectFactory(burned=True)
        confused = StatusEffectFactory(confused=True)
        airborne = _get_or_create_status(StatusName.AIRBORNE, StatusCategory.PHYSICAL)

        from tests.framework.factories.effects_factory import ActiveStatusEffectFactory as ASEF
        ASEF(slot=slot, status=burned)
        ASEF(slot=slot, status=confused)
        ASEF(slot=slot, status=airborne)

        _engine.clear_physical_statuses(slot)

        assert _engine.has_status(slot, StatusName.BURNED)
        assert _engine.has_status(slot, StatusName.CONFUSED)
        assert not _engine.has_status(slot, StatusName.AIRBORNE)


# ===========================================================================
# TestRemoveVolatileIncludesPhysicalUtilityAdvanced
# ===========================================================================

@allure.epic("Effects")
@allure.feature("Physical States")
class TestRemoveVolatileIncludesPhysicalUtilityAdvanced(BaseTest):

    @allure.story("remove_volatile_statuses clears physical states")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_removes_physical_states(self, slot, airborne_status):
        ActiveStatusEffectFactory(slot=slot, status=airborne_status)

        count = _engine.remove_volatile_statuses(slot)

        assert count >= 1
        assert not _engine.has_status(slot, StatusName.AIRBORNE)

    @allure.story("remove_volatile_statuses clears utility states")
    @allure.severity(allure.severity_level.NORMAL)
    def test_removes_utility_states(self, slot, shielded_status):
        ActiveStatusEffectFactory(slot=slot, status=shielded_status)

        count = _engine.remove_volatile_statuses(slot)

        assert count >= 1
        assert not _engine.has_status(slot, StatusName.SHIELDED)

    @allure.story("remove_volatile_statuses clears advanced states")
    @allure.severity(allure.severity_level.NORMAL)
    def test_removes_advanced_states(self, slot, chain_breaker_status):
        ActiveStatusEffectFactory(slot=slot, status=chain_breaker_status)

        count = _engine.remove_volatile_statuses(slot)

        assert count >= 1
        assert not _engine.has_status(slot, StatusName.CHAIN_BREAKER)

    @allure.story("remove_volatile_statuses preserves persistent status")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_preserves_persistent_on_volatile_clear(self, slot, airborne_status):
        burned = StatusEffectFactory(burned=True)
        ActiveStatusEffectFactory(slot=slot, status=burned)
        ActiveStatusEffectFactory(slot=slot, status=airborne_status)

        _engine.remove_volatile_statuses(slot)

        assert _engine.has_status(slot, StatusName.BURNED)
        assert not _engine.has_status(slot, StatusName.AIRBORNE)


# ===========================================================================
# TestPhysicalStateConstants
# ===========================================================================

@allure.epic("Effects")
@allure.feature("Physical States")
class TestPhysicalStateConstants(BaseTest):

    @allure.story("GROUNDED is not in PHYSICAL_STATUSES set (implicit default)")
    @allure.severity(allure.severity_level.NORMAL)
    def test_grounded_not_in_physical_set(self):
        assert StatusName.GROUNDED not in PHYSICAL_STATUSES

    @allure.story("AIRBORNE LAUNCHED KNOCKBACK are in PHYSICAL_STATUSES")
    @allure.severity(allure.severity_level.NORMAL)
    def test_airborne_launched_knockback_in_physical(self):
        assert StatusName.AIRBORNE in PHYSICAL_STATUSES
        assert StatusName.LAUNCHED in PHYSICAL_STATUSES
        assert StatusName.KNOCKBACK in PHYSICAL_STATUSES

    @allure.story("SHIELDED HIDDEN IMMUNE are in UTILITY_STATUSES")
    @allure.severity(allure.severity_level.NORMAL)
    def test_utility_statuses_complete(self):
        assert StatusName.SHIELDED in UTILITY_STATUSES
        assert StatusName.HIDDEN in UTILITY_STATUSES
        assert StatusName.IMMUNE in UTILITY_STATUSES

    @allure.story("CHAIN_BREAKER and STATE_LOCKED are in ADVANCED_STATUSES")
    @allure.severity(allure.severity_level.NORMAL)
    def test_advanced_statuses_complete(self):
        assert StatusName.CHAIN_BREAKER in ADVANCED_STATUSES
        assert StatusName.STATE_LOCKED in ADVANCED_STATUSES
