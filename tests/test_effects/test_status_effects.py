"""
Phase 3 — Status Effect tests.

All tests follow: OOP class inheriting BaseTest, Allure metadata,
Arrange-Act-Assert, factory_boy for all data.
"""
import pytest
import allure

from apps.effects.constants import StatusName
from apps.effects.engine import StatusEffectEngine
from apps.effects.models import ActiveStatusEffect

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.effects_factory import ActiveStatusEffectFactory, StatusEffectFactory
from tests.framework.factories.pokemon_factory import PokemonFactory, PokemonTypeFactory
from tests.framework.factories.battle_factory import BattleSlotFactory

_engine = StatusEffectEngine()


# ---------------------------------------------------------------------------
# Helper: slot with given type name
# ---------------------------------------------------------------------------

def _slot_of_type(type_name: str, hp: int = 150):
    ptype = PokemonTypeFactory(name=type_name)
    poke = PokemonFactory(primary_type=ptype, base_hp=100)
    return BattleSlotFactory(pokemon=poke, current_hp=hp, max_hp=hp)


# ===========================================================================
# TestStatusEffectApplication
# ===========================================================================

@allure.epic("Effects")
@allure.feature("Status Application")
class TestStatusEffectApplication(BaseTest):

    @allure.story("Apply burn to normal slot")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_apply_burn_creates_active_record(self, normal_slot, burned_status):
        # Arrange — slot has no statuses
        assert not ActiveStatusEffect.objects.filter(slot=normal_slot).exists()

        # Act
        result = _engine.apply_status(normal_slot, burned_status, round_number=1)

        # Assert
        assert result is not None
        assert ActiveStatusEffect.objects.filter(slot=normal_slot, status=burned_status).exists()

    @allure.story("Fire type is immune to burn")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_fire_type_immune_to_burn(self, burned_status):
        # Arrange
        slot = _slot_of_type("Fire")

        # Act
        result = _engine.apply_status(slot, burned_status, round_number=1)

        # Assert
        assert result is None
        assert not ActiveStatusEffect.objects.filter(slot=slot).exists()

    @allure.story("Electric type is immune to paralysis")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_electric_type_immune_to_paralysis(self, paralyzed_status):
        # Arrange
        slot = _slot_of_type("Electric")

        # Act
        result = _engine.apply_status(slot, paralyzed_status, round_number=1)

        # Assert
        assert result is None

    @allure.story("Ice type is immune to freeze")
    @allure.severity(allure.severity_level.NORMAL)
    def test_ice_type_immune_to_freeze(self, frozen_status):
        slot = _slot_of_type("Ice")
        result = _engine.apply_status(slot, frozen_status, round_number=1)
        assert result is None

    @allure.story("Poison type is immune to poison")
    @allure.severity(allure.severity_level.NORMAL)
    def test_poison_type_immune_to_poison(self, poisoned_status):
        slot = _slot_of_type("Poison")
        result = _engine.apply_status(slot, poisoned_status, round_number=1)
        assert result is None

    @allure.story("Cannot stack two persistent statuses")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_cannot_stack_persistent_statuses(self, normal_slot, burned_status, paralyzed_status):
        # Arrange — apply burn first
        _engine.apply_status(normal_slot, burned_status, round_number=1)

        # Act — attempt to apply paralysis on top
        result = _engine.apply_status(normal_slot, paralyzed_status, round_number=1)

        # Assert — only one persistent status allowed
        assert result is None
        assert ActiveStatusEffect.objects.filter(slot=normal_slot).count() == 1

    @allure.story("Volatile statuses can coexist")
    @allure.severity(allure.severity_level.NORMAL)
    def test_volatile_statuses_coexist(self, normal_slot, confused_status, tagged_status):
        # Act
        r1 = _engine.apply_status(normal_slot, confused_status, round_number=1)
        r2 = _engine.apply_status(normal_slot, tagged_status, round_number=1)

        # Assert — both applied
        assert r1 is not None
        assert r2 is not None
        assert ActiveStatusEffect.objects.filter(slot=normal_slot).count() == 2

    @allure.story("Idempotent: applying same status twice does nothing")
    @allure.severity(allure.severity_level.NORMAL)
    def test_same_status_not_stacked(self, normal_slot, confused_status):
        _engine.apply_status(normal_slot, confused_status, round_number=1)
        result = _engine.apply_status(normal_slot, confused_status, round_number=2)

        assert result is None
        assert ActiveStatusEffect.objects.filter(slot=normal_slot, status=confused_status).count() == 1

    @allure.story("Apply all Naruto statuses to normal slot")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.parametrize("status_name", [
        StatusName.IGNITED, StatusName.IMMOBILE, StatusName.CHAOS,
        StatusName.BLINDED, StatusName.ACUPUNCTURED, StatusName.IMPRISONED,
        StatusName.TAGGED, StatusName.ENFEEBLED, StatusName.WEAKENED,
        StatusName.CORRODED, StatusName.INTERRUPTED,
    ])
    def test_naruto_statuses_apply_to_normal_slot(self, normal_slot, status_name):
        # Arrange — get or create the status by name
        from apps.effects.models import StatusEffect
        from apps.effects.constants import StatusCategory
        status, _ = StatusEffect.objects.get_or_create(
            name=status_name,
            defaults={"category": StatusCategory.NARUTO, "description": "test"},
        )

        # Act
        result = _engine.apply_status(normal_slot, status, round_number=1)

        # Assert
        assert result is not None

    @allure.story("Remove status clears the active record")
    @allure.severity(allure.severity_level.NORMAL)
    def test_remove_status(self, normal_slot, burned_status):
        _engine.apply_status(normal_slot, burned_status, round_number=1)
        removed = _engine.remove_status(normal_slot, burned_status)

        assert removed is True
        assert not ActiveStatusEffect.objects.filter(slot=normal_slot, status=burned_status).exists()

    @allure.story("Remove volatile statuses clears only volatile")
    @allure.severity(allure.severity_level.NORMAL)
    def test_remove_volatile_statuses_preserves_persistent(
        self, normal_slot, burned_status, confused_status
    ):
        _engine.apply_status(normal_slot, burned_status, round_number=1)
        _engine.apply_status(normal_slot, confused_status, round_number=1)

        count = _engine.remove_volatile_statuses(normal_slot)

        assert count == 1
        assert _engine.has_status(normal_slot, StatusName.BURNED)
        assert not _engine.has_status(normal_slot, StatusName.CONFUSED)


# ===========================================================================
# TestStatusEffectTicking
# ===========================================================================

@allure.epic("Effects")
@allure.feature("Status Ticking")
class TestStatusEffectTicking(BaseTest):

    @allure.story("Burn deals 1/16 max HP per turn")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_burn_deals_damage_per_turn(self, normal_slot, burned_status):
        # Arrange
        _engine.apply_status(normal_slot, burned_status, round_number=1)
        initial_hp = normal_slot.current_hp
        expected_damage = max(1, normal_slot.pokemon.calculate_max_hp(normal_slot.level) // 16)

        # Act
        results = _engine.tick_statuses(normal_slot, round_number=1)
        normal_slot.refresh_from_db()

        # Assert
        assert normal_slot.current_hp == initial_hp - expected_damage
        assert any(r["damage"] == expected_damage for r in results)

    @allure.story("Poison deals 2/16 max HP per turn")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_poison_deals_damage_per_turn(self, normal_slot, poisoned_status):
        _engine.apply_status(normal_slot, poisoned_status, round_number=1)
        initial_hp = normal_slot.current_hp
        expected_damage = max(1, (normal_slot.pokemon.calculate_max_hp(normal_slot.level) * 2) // 16)

        _engine.tick_statuses(normal_slot, round_number=1)
        normal_slot.refresh_from_db()

        assert normal_slot.current_hp == initial_hp - expected_damage

    @allure.story("Badly poisoned escalates damage each turn")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_badly_poisoned_escalates(self, normal_slot, badly_poisoned_status):
        _engine.apply_status(normal_slot, badly_poisoned_status, round_number=1)

        # Turn 1: 1/16
        _engine.tick_statuses(normal_slot, round_number=1)
        normal_slot.refresh_from_db()
        hp_after_turn1 = normal_slot.current_hp

        # Turn 2: 2/16 (more damage)
        _engine.tick_statuses(normal_slot, round_number=2)
        normal_slot.refresh_from_db()
        hp_after_turn2 = normal_slot.current_hp

        dmg_turn1 = 150 - hp_after_turn1
        dmg_turn2 = hp_after_turn1 - hp_after_turn2
        assert dmg_turn2 > dmg_turn1

    @allure.story("Volatile status expires after duration")
    @allure.severity(allure.severity_level.NORMAL)
    def test_volatile_expires_after_duration(self, normal_slot):
        from apps.effects.models import StatusEffect
        from apps.effects.constants import StatusCategory
        # flinched lasts exactly 1 turn
        flinch, _ = StatusEffect.objects.get_or_create(
            name=StatusName.FLINCHED,
            defaults={"category": StatusCategory.VOLATILE, "default_duration": 1},
        )
        _engine.apply_status(normal_slot, flinch, round_number=1)
        assert _engine.has_status(normal_slot, StatusName.FLINCHED)

        _engine.tick_statuses(normal_slot, round_number=1)

        assert not _engine.has_status(normal_slot, StatusName.FLINCHED)

    @allure.story("Corroded worsens sp_defense each turn")
    @allure.severity(allure.severity_level.NORMAL)
    def test_corroded_worsens_sp_defense(self, normal_slot, corroded_status):
        _engine.apply_status(normal_slot, corroded_status, round_number=1)

        _engine.tick_statuses(normal_slot, round_number=1)
        mods_turn1 = _engine.get_stat_modifiers(normal_slot)

        _engine.tick_statuses(normal_slot, round_number=2)
        mods_turn2 = _engine.get_stat_modifiers(normal_slot)

        # sp_defense penalty should be worse (lower multiplier) after turn 2
        assert mods_turn2.get("sp_defense", 1.0) <= mods_turn1.get("sp_defense", 1.0)

    @allure.story("Perish song faints Pokemon when counter expires")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_perish_song_faints_on_expiry(self, normal_slot, perish_song_status):
        # default_duration = 3 ticks
        _engine.apply_status(normal_slot, perish_song_status, round_number=1)

        for tick in range(1, 4):
            _engine.tick_statuses(normal_slot, round_number=tick)

        normal_slot.refresh_from_db()
        assert normal_slot.is_fainted
        assert normal_slot.current_hp == 0

    @allure.story("Ignited applies DoT and disables healing flag")
    @allure.severity(allure.severity_level.NORMAL)
    def test_ignited_dot_and_disables_healing(self, normal_slot, ignited_status):
        assert ignited_status.disables_healing is True

        _engine.apply_status(normal_slot, ignited_status, round_number=1)
        initial_hp = normal_slot.current_hp

        _engine.tick_statuses(normal_slot, round_number=1)
        normal_slot.refresh_from_db()

        assert normal_slot.current_hp < initial_hp


# ===========================================================================
# TestCanAct
# ===========================================================================

@allure.epic("Effects")
@allure.feature("Action Prevention")
class TestCanAct(BaseTest):

    @allure.story("Healthy Pokemon can act")
    @allure.severity(allure.severity_level.NORMAL)
    def test_healthy_can_act(self, normal_slot):
        can_act, reason = _engine.can_act(normal_slot)
        assert can_act is True
        assert reason == ""

    @allure.story("Asleep Pokemon cannot act")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_asleep_cannot_act(self, normal_slot, asleep_status):
        ActiveStatusEffectFactory(slot=normal_slot, status=asleep_status, remaining_turns=3)

        can_act, reason = _engine.can_act(normal_slot)

        assert can_act is False
        assert reason == "asleep"

    @allure.story("Frozen Pokemon cannot act (and has chance to thaw)")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_frozen_prevents_action(self, normal_slot, frozen_status):
        # Force it to never thaw by mocking random
        import unittest.mock as mock
        ActiveStatusEffectFactory(slot=normal_slot, status=frozen_status)

        with mock.patch("apps.effects.engine.random.random", return_value=0.99):
            can_act, reason = _engine.can_act(normal_slot)

        assert can_act is False
        assert reason == "frozen"

    @allure.story("Frozen Pokemon can thaw with 20% chance")
    @allure.severity(allure.severity_level.NORMAL)
    def test_frozen_can_thaw(self, normal_slot, frozen_status):
        import unittest.mock as mock
        ActiveStatusEffectFactory(slot=normal_slot, status=frozen_status)

        # random.random() < 0.20 → thaws
        with mock.patch("apps.effects.engine.random.random", return_value=0.10):
            can_act, reason = _engine.can_act(normal_slot)

        assert can_act is True
        assert not _engine.has_status(normal_slot, StatusName.FROZEN)

    @allure.story("Paralysed Pokemon may lose its turn (25% chance)")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_paralyzed_may_lose_turn(self, normal_slot, paralyzed_status):
        import unittest.mock as mock
        ActiveStatusEffectFactory(slot=normal_slot, status=paralyzed_status)

        # random.random() < 0.25 → loses turn
        with mock.patch("apps.effects.engine.random.random", return_value=0.10):
            can_act, reason = _engine.can_act(normal_slot)

        assert can_act is False
        assert reason == "paralyzed"

    @allure.story("Paralysed Pokemon can still act if roll succeeds")
    @allure.severity(allure.severity_level.NORMAL)
    def test_paralyzed_can_still_act(self, normal_slot, paralyzed_status):
        import unittest.mock as mock
        ActiveStatusEffectFactory(slot=normal_slot, status=paralyzed_status)

        # random.random() >= 0.25 → can act (frozen check runs first but no frozen here)
        with mock.patch("apps.effects.engine.random.random", return_value=0.50):
            can_act, _ = _engine.can_act(normal_slot)

        assert can_act is True

    @allure.story("Immobile Pokemon cannot act")
    @allure.severity(allure.severity_level.NORMAL)
    def test_immobile_cannot_act(self, normal_slot, immobile_status):
        ActiveStatusEffectFactory(slot=normal_slot, status=immobile_status, remaining_turns=1)

        can_act, reason = _engine.can_act(normal_slot)

        assert can_act is False
        assert reason == "immobile"


# ===========================================================================
# TestStatModifiers
# ===========================================================================

@allure.epic("Effects")
@allure.feature("Stat Modifiers")
class TestStatModifiers(BaseTest):

    @allure.story("Burned halves attack stat")
    @allure.severity(allure.severity_level.NORMAL)
    def test_burned_halves_attack(self, normal_slot, burned_status):
        ActiveStatusEffectFactory(slot=normal_slot, status=burned_status)

        mods = _engine.get_stat_modifiers(normal_slot)

        assert mods.get("attack") == pytest.approx(0.5)

    @allure.story("Paralysis halves speed stat")
    @allure.severity(allure.severity_level.NORMAL)
    def test_paralyzed_halves_speed(self, normal_slot, paralyzed_status):
        ActiveStatusEffectFactory(slot=normal_slot, status=paralyzed_status)

        mods = _engine.get_stat_modifiers(normal_slot)

        assert mods.get("speed") == pytest.approx(0.5)

    @allure.story("Enfeebled halves both attack stats")
    @allure.severity(allure.severity_level.NORMAL)
    def test_enfeebled_halves_attack_and_sp_attack(self, normal_slot, enfeebled_status):
        ActiveStatusEffectFactory(slot=normal_slot, status=enfeebled_status)

        mods = _engine.get_stat_modifiers(normal_slot)

        assert mods.get("attack") == pytest.approx(0.5)
        assert mods.get("sp_attack") == pytest.approx(0.5)

    @allure.story("Tagged reduces defense and sp_defense by 30%")
    @allure.severity(allure.severity_level.NORMAL)
    def test_tagged_reduces_defenses(self, normal_slot, tagged_status):
        ActiveStatusEffectFactory(slot=normal_slot, status=tagged_status)

        mods = _engine.get_stat_modifiers(normal_slot)

        assert mods.get("defense") == pytest.approx(0.7)
        assert mods.get("sp_defense") == pytest.approx(0.7)

    @allure.story("No active statuses returns empty modifiers")
    @allure.severity(allure.severity_level.MINOR)
    def test_no_statuses_empty_modifiers(self, normal_slot):
        mods = _engine.get_stat_modifiers(normal_slot)
        assert mods == {}
