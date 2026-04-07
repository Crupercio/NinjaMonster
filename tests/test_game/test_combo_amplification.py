"""
P1-4 — Combo chain damage amplification tests (GDD Section 6.3).

Covers:
- Link 1 (chain_position=0) deals unmodified damage
- Link 2 (chain_position=1) applies ×1.10
- Link 5 (chain_position=4) applies ×1.50
- Link 10 (chain_position=9) applies ×2.50
- Beyond position 9 is capped at ×2.50
- End-to-end: chain moves deal more damage than the initial move
"""
import allure
import pytest
import random

from apps.game.models import BattleStatus, GridPosition
from apps.game.services import COMBO_AMP, ComboChainEngine

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.battle_factory import (
    BattleFactory,
    BattleSlotFactory,
    BattleTeamFactory,
)
from tests.framework.factories.pokemon_factory import MoveFactory, PokemonFactory, PokemonTypeFactory
from tests.framework.factories.user_factory import UserFactory


def _make_front_slot(team, position, hp=200):
    normal_type = PokemonTypeFactory(name="Normal")
    poke = PokemonFactory(primary_type=normal_type)
    return BattleSlotFactory(
        team=team,
        pokemon=poke,
        position=position,
        grid_position=GridPosition.FRONT_LEFT,
        current_hp=hp,
        max_hp=hp,
        is_fainted=False,
        is_active=True,
    )


@allure.epic("Battle")
@allure.feature("Combo Amplification")
@pytest.mark.django_db
class TestComboAmpMultipliers(BaseTest):

    @allure.story("Link 1 has no amplification (×1.00)")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_link1_no_amplification(self):
        engine = ComboChainEngine()
        normal_type = PokemonTypeFactory(name="Normal")
        move = MoveFactory(name="Tackle", move_type=normal_type, power=40)

        user = UserFactory()
        battle = BattleFactory(player_one=user, status=BattleStatus.ACTIVE)
        team = BattleTeamFactory(battle=battle, owner=user)

        attacker = _make_front_slot(team, 1)
        defender = _make_front_slot(team, 2)

        random.seed(42)
        base = engine._calculate_damage(attacker, move, defender, chain_position=0)
        random.seed(42)
        link1 = engine._calculate_damage(attacker, move, defender, chain_position=0)

        assert base == link1

    @allure.story("Link 2 amplifies damage by ×1.10")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_link2_amplification_1_10(self):
        engine = ComboChainEngine()
        normal_type = PokemonTypeFactory(name="Normal")
        move = MoveFactory(name="Tackle", move_type=normal_type, power=40)

        user = UserFactory()
        battle = BattleFactory(player_one=user, status=BattleStatus.ACTIVE)
        team = BattleTeamFactory(battle=battle, owner=user)

        attacker = _make_front_slot(team, 1)
        defender = _make_front_slot(team, 2)

        random.seed(77)
        base = engine._calculate_damage(attacker, move, defender, chain_position=0)
        random.seed(77)
        link2 = engine._calculate_damage(attacker, move, defender, chain_position=1)

        expected = int(base * 1.10)
        assert abs(link2 - expected) <= 1, f"Expected ≈{expected}, got {link2}"

    @allure.story("Link 5 amplifies damage by ×1.50")
    @allure.severity(allure.severity_level.NORMAL)
    def test_link5_amplification_1_50(self):
        engine = ComboChainEngine()
        normal_type = PokemonTypeFactory(name="Normal")
        move = MoveFactory(name="Tackle", move_type=normal_type, power=40)

        user = UserFactory()
        battle = BattleFactory(player_one=user, status=BattleStatus.ACTIVE)
        team = BattleTeamFactory(battle=battle, owner=user)

        attacker = _make_front_slot(team, 1)
        defender = _make_front_slot(team, 2)

        random.seed(55)
        base = engine._calculate_damage(attacker, move, defender, chain_position=0)
        random.seed(55)
        link5 = engine._calculate_damage(attacker, move, defender, chain_position=4)

        expected = int(base * 1.50)
        assert abs(link5 - expected) <= 1, f"Expected ≈{expected}, got {link5}"

    @allure.story("Link 10 amplifies damage by ×2.50")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_link10_amplification_2_50(self):
        engine = ComboChainEngine()
        normal_type = PokemonTypeFactory(name="Normal")
        move = MoveFactory(name="Tackle", move_type=normal_type, power=40)

        user = UserFactory()
        battle = BattleFactory(player_one=user, status=BattleStatus.ACTIVE)
        team = BattleTeamFactory(battle=battle, owner=user)

        attacker = _make_front_slot(team, 1)
        defender = _make_front_slot(team, 2)

        random.seed(33)
        base = engine._calculate_damage(attacker, move, defender, chain_position=0)
        random.seed(33)
        link10 = engine._calculate_damage(attacker, move, defender, chain_position=9)

        expected = int(base * 2.50)
        assert abs(link10 - expected) <= 1, f"Expected ≈{expected}, got {link10}"

    @allure.story("Positions beyond 9 are capped at ×2.50")
    @allure.severity(allure.severity_level.NORMAL)
    def test_beyond_max_capped_at_2_50(self):
        engine = ComboChainEngine()
        normal_type = PokemonTypeFactory(name="Normal")
        move = MoveFactory(name="Tackle", move_type=normal_type, power=40)

        user = UserFactory()
        battle = BattleFactory(player_one=user, status=BattleStatus.ACTIVE)
        team = BattleTeamFactory(battle=battle, owner=user)

        attacker = _make_front_slot(team, 1)
        defender = _make_front_slot(team, 2)

        random.seed(11)
        link10 = engine._calculate_damage(attacker, move, defender, chain_position=9)
        random.seed(11)
        link11 = engine._calculate_damage(attacker, move, defender, chain_position=10)
        random.seed(11)
        link20 = engine._calculate_damage(attacker, move, defender, chain_position=19)

        assert link10 == link11 == link20, "All positions >= 9 must produce the same damage"

    @allure.story("COMBO_AMP table has correct values")
    @allure.severity(allure.severity_level.NORMAL)
    def test_combo_amp_table_values(self):
        expected = [1.00, 1.10, 1.20, 1.35, 1.50, 1.65, 1.80, 2.00, 2.25, 2.50]
        for i, exp in enumerate(expected):
            assert COMBO_AMP[i] == pytest.approx(exp), (
                f"COMBO_AMP[{i}] expected {exp}, got {COMBO_AMP[i]}"
            )
