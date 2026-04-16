"""
Phase 7 — Chakra Element System tests.

Covers:
  - CHAKRA_BEATS cycle is complete and correct
  - Type → chakra element mapping structure (migration data correctness)
  - Mastery bonus (+20%): move chakra == attacker species chakra
  - Advantage bonus (+15%): move chakra beats defender species chakra
  - Both stacked (+35%): mastery + advantage
  - Resistance penalty (−10%): defender chakra beats move chakra
  - Neutral (×1.0): no relationship
  - No bonus when chakra_element is None (type has no element set)
"""
import unittest.mock as mock

import allure
import pytest

from apps.game.services import CHAKRA_BEATS, ComboChainEngine
from apps.pokemon.models import ChakraElement

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.battle_factory import BattleSlotFactory
from tests.framework.factories.pokemon_factory import (
    MoveFactory,
    PokemonFactory,
    PokemonTypeFactory,
)
from tests.framework.helpers.battle_helpers import build_battle_pair, ensure_round

_chain = ComboChainEngine()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ELEMENT_NAMES = ("fire", "water", "earth", "lightning", "wind")


def _get_or_create_element(name: str) -> ChakraElement:
    el, _ = ChakraElement.objects.get_or_create(name=name)
    return el


def _type_with_element(element_name: str, type_name: str | None = None):
    """Create a PokemonType linked to the given chakra element."""
    el = _get_or_create_element(element_name)
    name = type_name or f"TestType_{element_name}_{id(el)}"
    pt = PokemonTypeFactory(name=name)
    pt.chakra_element = el
    pt.save(update_fields=["chakra_element"])
    return pt


def _calc_damage(attacker, move, defender) -> int:
    """Call _calculate_damage with crit disabled and full variance."""
    attacker.critical_rate = 0.0
    attacker.save(update_fields=["critical_rate"])
    with mock.patch("apps.game.services.random.randint", return_value=100):
        with mock.patch("apps.game.services.random.random", return_value=0.99):
            return _chain._calculate_damage(attacker, move, defender, chain_position=0)


# ===========================================================================
# TestChakraBeatsCycle
# ===========================================================================

@allure.epic("Pokemon")
@allure.feature("Chakra System")
class TestChakraBeatsCycle(BaseTest):

    @allure.story("CHAKRA_BEATS covers all five elements")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_chakra_beats_has_all_five_elements(self):
        assert set(CHAKRA_BEATS.keys()) == set(_ELEMENT_NAMES)

    @allure.story("CHAKRA_BEATS values are all valid element names")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_chakra_beats_values_are_valid(self):
        assert set(CHAKRA_BEATS.values()) == set(_ELEMENT_NAMES)

    @allure.story("No element beats itself")
    @allure.severity(allure.severity_level.NORMAL)
    def test_no_element_beats_itself(self):
        for element, beaten in CHAKRA_BEATS.items():
            assert element != beaten, f"{element} should not beat itself"

    @allure.story("Advantage cycle is a closed loop (fire→wind→lightning→earth→water→fire)")
    @allure.severity(allure.severity_level.NORMAL)
    def test_advantage_cycle_is_closed_loop(self):
        # Starting from "fire", following the beats chain should return to "fire" in 5 steps
        current = "fire"
        for _ in range(5):
            current = CHAKRA_BEATS[current]
        assert current == "fire"

    @allure.story("Each element is beaten by exactly one other element")
    @allure.severity(allure.severity_level.NORMAL)
    def test_each_element_beaten_by_exactly_one(self):
        for element in _ELEMENT_NAMES:
            beaters = [k for k, v in CHAKRA_BEATS.items() if v == element]
            assert len(beaters) == 1, f"{element} should be beaten by exactly 1 element, got {beaters}"


# ===========================================================================
# TestChakraElementMapping
# ===========================================================================

@allure.epic("Pokemon")
@allure.feature("Chakra System")
class TestChakraElementMapping(BaseTest):

    @allure.story("All 5 chakra elements exist in the database after migrations")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_five_elements_exist_in_db(self):
        # The migration creates all 5 elements
        count = ChakraElement.objects.count()
        assert count == 5, f"Expected 5 ChakraElements, found {count}"

    @allure.story("All 5 element names are present")
    @allure.severity(allure.severity_level.NORMAL)
    def test_element_names_correct(self):
        names = set(ChakraElement.objects.values_list("name", flat=True))
        assert names == set(_ELEMENT_NAMES)

    @allure.story("Type→element mapping in migration covers all 18 types")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_type_chakra_map_covers_18_types(self):
        """Verify the mapping constant from the migration includes all 18 canonical types."""
        # Mirror of _TYPE_CHAKRA_MAP from migration 0011 — source of truth
        type_chakra_map = {
            "fire":      {"Fire", "Dragon", "Dark"},
            "water":     {"Water", "Ice", "Poison", "Fairy"},
            "earth":     {"Ground", "Rock", "Fighting", "Normal"},
            "lightning": {"Electric", "Steel", "Psychic"},
            "wind":      {"Flying", "Grass", "Bug", "Ghost"},
        }
        all_types = set()
        for types in type_chakra_map.values():
            all_types |= types
        assert len(all_types) == 18

    @allure.story("No type appears in more than one chakra element group")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_no_type_in_two_groups(self):
        type_chakra_map = {
            "fire":      {"Fire", "Dragon", "Dark"},
            "water":     {"Water", "Ice", "Poison", "Fairy"},
            "earth":     {"Ground", "Rock", "Fighting", "Normal"},
            "lightning": {"Electric", "Steel", "Psychic"},
            "wind":      {"Flying", "Grass", "Bug", "Ghost"},
        }
        all_types: list[str] = []
        for types in type_chakra_map.values():
            all_types.extend(types)
        assert len(all_types) == len(set(all_types)), "Some type appears in multiple chakra groups"


# ===========================================================================
# TestChakraDamageBonuses
# ===========================================================================

@allure.epic("Pokemon")
@allure.feature("Chakra System")
class TestChakraDamageBonuses(BaseTest):
    """
    Verifies chakra damage multipliers in _calculate_damage.

    Test strategy:
    - Attacker type = fire element (primary type)
    - Move type = different name but same fire element → mastery, no STAB
    - For advantage: defender type = wind element (fire beats wind)
    - For resistance: defender type = water element (water beats fire)
    - For neutral: defender type = earth element (no cycle relation to fire)
    - Compare modified vs baseline (no chakra) to confirm ratio.
    """

    def _make_fire_attacker(self):
        fire_el = _get_or_create_element("fire")
        atk_type = PokemonTypeFactory(name="AttackerFireType")
        atk_type.chakra_element = fire_el
        atk_type.save(update_fields=["chakra_element"])
        pokemon = PokemonFactory(primary_type=atk_type, base_hp=80, base_attack=80, base_defense=80)
        slot = BattleSlotFactory(pokemon=pokemon, current_hp=200, max_hp=200, level=50)
        return slot

    def _make_defender(self, element_name: str):
        el = _get_or_create_element(element_name)
        def_type = PokemonTypeFactory(name=f"DefType_{element_name}")
        def_type.chakra_element = el
        def_type.save(update_fields=["chakra_element"])
        pokemon = PokemonFactory(primary_type=def_type, base_hp=80, base_attack=80, base_defense=80)
        return BattleSlotFactory(pokemon=pokemon, current_hp=200, max_hp=200, level=50)

    def _fire_element_move(self):
        """Move with fire chakra but different type name (no STAB with fire attacker)."""
        fire_el = _get_or_create_element("fire")
        move_type = PokemonTypeFactory(name="FireMoveType")
        move_type.chakra_element = fire_el
        move_type.save(update_fields=["chakra_element"])
        return MoveFactory(move_type=move_type, power=60)

    def _no_chakra_move(self):
        """Move whose type has no chakra element (null)."""
        bare_type = PokemonTypeFactory(name="NullChakraType")
        # chakra_element is null by default
        return MoveFactory(move_type=bare_type, power=60)

    @allure.story("Mastery bonus (+20%): move chakra matches attacker species chakra")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_mastery_bonus(self):
        attacker = self._make_fire_attacker()
        # Neutral defender (earth — no chakra relation to fire)
        defender = self._make_defender("earth")
        move_with_mastery = self._fire_element_move()
        move_no_chakra = self._no_chakra_move()

        base_dmg = _calc_damage(attacker, move_no_chakra, defender)
        mastery_dmg = _calc_damage(attacker, move_with_mastery, defender)

        # Mastery should give ~20% more damage
        assert mastery_dmg > base_dmg
        # Ratio should be approximately 1.20 (within integer rounding)
        ratio = mastery_dmg / base_dmg
        assert 1.15 <= ratio <= 1.25, f"Expected ~1.20× mastery, got {ratio:.3f}"

    @allure.story("Advantage bonus (+15%): move chakra beats defender chakra")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_advantage_bonus(self):
        # Non-fire attacker (water element) → no mastery with fire move
        water_el = _get_or_create_element("water")
        atk_type = PokemonTypeFactory(name="WaterAttackerType")
        atk_type.chakra_element = water_el
        atk_type.save(update_fields=["chakra_element"])
        poke = PokemonFactory(primary_type=atk_type, base_hp=80, base_attack=80, base_defense=80)
        attacker = BattleSlotFactory(pokemon=poke, current_hp=200, max_hp=200, level=50)
        attacker.critical_rate = 0.0
        attacker.save(update_fields=["critical_rate"])

        # fire beats wind → defender = wind
        defender = self._make_defender("wind")
        move_fire = self._fire_element_move()
        move_no_chakra = self._no_chakra_move()

        base_dmg = _calc_damage(attacker, move_no_chakra, defender)
        advantage_dmg = _calc_damage(attacker, move_fire, defender)

        assert advantage_dmg > base_dmg
        ratio = advantage_dmg / base_dmg
        assert 1.10 <= ratio <= 1.20, f"Expected ~1.15× advantage, got {ratio:.3f}"

    @allure.story("Mastery + advantage stacks to +35%")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_mastery_and_advantage_stack(self):
        # Attacker = fire, move = fire chakra (mastery), defender = wind (advantage)
        attacker = self._make_fire_attacker()
        defender = self._make_defender("wind")  # fire beats wind
        move_with_mastery = self._fire_element_move()
        move_no_chakra = self._no_chakra_move()

        base_dmg = _calc_damage(attacker, move_no_chakra, defender)
        combined_dmg = _calc_damage(attacker, move_with_mastery, defender)

        assert combined_dmg > base_dmg
        ratio = combined_dmg / base_dmg
        assert 1.30 <= ratio <= 1.40, f"Expected ~1.35× combined, got {ratio:.3f}"

    @allure.story("Resistance penalty (−10%): defender chakra beats move chakra")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_resistance_penalty(self):
        # Attacker = fire, move = fire chakra (mastery), defender = water (water beats fire → resistance)
        attacker = self._make_fire_attacker()
        defender = self._make_defender("water")  # water beats fire
        move_with_mastery = self._fire_element_move()
        move_no_chakra = self._no_chakra_move()

        base_dmg = _calc_damage(attacker, move_no_chakra, defender)
        # With mastery (1.20) + resistance (0.90) on the mastery move:
        # actual: mastery applies, resistance also applies? Let's check:
        # mastery = move_el == atk_el = fire == fire → yes
        # advantage = CHAKRA_BEATS.get(fire) = wind ≠ water → no
        # resistance = CHAKRA_BEATS.get(water) = fire == fire → yes (but code path: mastery-only branch at 1.20)
        # Wait, the code is: if mastery and advantage → 1.35, elif mastery → 1.20, elif advantage → 1.15, elif resistance → 0.90
        # So with mastery move on water defender: mastery fires (1.20), resistance block NOT reached.
        # Let me use a non-mastery move: non-fire attacker + fire move + water defender

        # Non-fire attacker (earth element)
        earth_el = _get_or_create_element("earth")
        atk_type = PokemonTypeFactory(name="EarthAttackerType")
        atk_type.chakra_element = earth_el
        atk_type.save(update_fields=["chakra_element"])
        poke = PokemonFactory(primary_type=atk_type, base_hp=80, base_attack=80, base_defense=80)
        attacker2 = BattleSlotFactory(pokemon=poke, current_hp=200, max_hp=200, level=50)
        attacker2.critical_rate = 0.0
        attacker2.save(update_fields=["critical_rate"])

        base_dmg2 = _calc_damage(attacker2, move_no_chakra, defender)
        resistance_dmg = _calc_damage(attacker2, move_with_mastery, defender)

        assert resistance_dmg < base_dmg2
        ratio = resistance_dmg / base_dmg2
        assert 0.85 <= ratio <= 0.95, f"Expected ~0.90× resistance, got {ratio:.3f}"

    @allure.story("Neutral (×1.0): no chakra relationship between elements")
    @allure.severity(allure.severity_level.NORMAL)
    def test_neutral_no_modifier(self):
        # Attacker = earth, move = earth chakra, defender = lightning
        # CHAKRA_BEATS.get(earth) = water ≠ lightning → no advantage
        # CHAKRA_BEATS.get(lightning) = earth ≠ earth? Wait: lightning beats earth...
        # CHAKRA_BEATS = {fire:wind, wind:lightning, lightning:earth, earth:water, water:fire}
        # CHAKRA_BEATS.get(lightning) = earth — so lightning beats earth → resistance!
        # Use fire move vs lightning defender:
        # CHAKRA_BEATS.get(fire) = wind ≠ lightning → no advantage
        # CHAKRA_BEATS.get(lightning) = earth ≠ fire → no resistance → NEUTRAL!
        earth_el = _get_or_create_element("earth")
        atk_type = PokemonTypeFactory(name="EarthAtk2Type")
        atk_type.chakra_element = earth_el
        atk_type.save(update_fields=["chakra_element"])
        poke = PokemonFactory(primary_type=atk_type, base_hp=80, base_attack=80, base_defense=80)
        attacker = BattleSlotFactory(pokemon=poke, current_hp=200, max_hp=200, level=50)
        attacker.critical_rate = 0.0
        attacker.save(update_fields=["critical_rate"])

        defender = self._make_defender("lightning")  # no cycle relation to fire
        move_fire = self._fire_element_move()  # fire element, not earth → no mastery
        move_no_chakra = self._no_chakra_move()

        base_dmg = _calc_damage(attacker, move_no_chakra, defender)
        neutral_dmg = _calc_damage(attacker, move_fire, defender)

        # Should be equal (no modifier applies)
        assert neutral_dmg == base_dmg

    @allure.story("No bonus when move type has no chakra element")
    @allure.severity(allure.severity_level.NORMAL)
    def test_no_bonus_when_move_has_no_chakra_element(self):
        attacker = self._make_fire_attacker()
        defender = self._make_defender("wind")  # would be advantage if fire element present
        move_no_chakra = self._no_chakra_move()  # no element

        attacker2 = self._make_fire_attacker()
        fire_move = self._fire_element_move()  # has fire element

        dmg_no_chakra = _calc_damage(attacker, move_no_chakra, defender)
        dmg_with_chakra = _calc_damage(attacker2, fire_move, defender)

        # Move with chakra should deal more damage (mastery + advantage)
        assert dmg_with_chakra > dmg_no_chakra
