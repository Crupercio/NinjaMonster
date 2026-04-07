"""
P1-3 — Positional damage rule tests.

Covers:
- Front-row target takes full damage (no modifier)
- Back-row target takes 80% damage
- Targeting a back-row slot redirects to front-row when a front-row ally lives
- Back-row can be targeted directly once all front-row allies have fainted
- AI _select_target() prioritises front-row slots
- AI targets back row directly when front row is cleared
"""
import allure
import pytest

from apps.game.models import BattleStatus, GridPosition
from apps.game.services import BattleService, ComboChainEngine

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.battle_factory import (
    BattleFactory,
    BattleSlotFactory,
    BattleTeamFactory,
)
from tests.framework.factories.pokemon_factory import MoveFactory, PokemonFactory, PokemonTypeFactory
from tests.framework.factories.user_factory import UserFactory


def _make_slot(team, position, grid_position, hp=150, fainted=False):
    normal_type = PokemonTypeFactory(name="Normal")
    poke = PokemonFactory(primary_type=normal_type)
    return BattleSlotFactory(
        team=team,
        pokemon=poke,
        position=position,
        grid_position=grid_position,
        current_hp=hp,
        max_hp=hp,
        is_fainted=fainted,
        is_active=grid_position not in (GridPosition.BENCH_1, GridPosition.BENCH_2),
    )


@allure.epic("Battle")
@allure.feature("Positional Damage")
@pytest.mark.django_db
class TestBackRowDamageModifier(BaseTest):

    @allure.story("Front-row target takes full (unmodified) damage")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_front_row_full_damage(self):
        """_calculate_damage() must NOT apply the 0.80 modifier for front-row slots."""
        engine = ComboChainEngine()
        normal_type = PokemonTypeFactory(name="Normal")
        move = MoveFactory(name="Tackle", move_type=normal_type, power=40)

        user = UserFactory()
        battle = BattleFactory(player_one=user, status=BattleStatus.ACTIVE)
        team = BattleTeamFactory(battle=battle, owner=user)

        attacker = _make_slot(team, 1, GridPosition.FRONT_LEFT)
        defender = _make_slot(team, 2, GridPosition.FRONT_RIGHT)

        # Seed the random roll to 100 for determinism
        import random
        random.seed(42)
        damage_front = engine._calculate_damage(attacker, move, defender)

        # Run again with back-row defender
        back_defender = _make_slot(team, 3, GridPosition.BACK_LEFT)
        random.seed(42)
        damage_back = engine._calculate_damage(attacker, move, back_defender)

        # Back row must be strictly less (0.80 applied)
        assert damage_back < damage_front, (
            f"Expected back-row damage ({damage_back}) < front-row damage ({damage_front})"
        )

    @allure.story("Back-row target takes exactly 80% of the equivalent front-row damage")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_back_row_80_percent_damage(self):
        """
        With the random roll seeded identically, back-row damage should equal
        int(front_row_pre_roll * 0.80 * roll / 100).

        We verify by checking the ratio is approximately 0.80 (±5% for int rounding).
        """
        engine = ComboChainEngine()
        normal_type = PokemonTypeFactory(name="Normal")
        move = MoveFactory(name="Tackle", move_type=normal_type, power=40)

        user = UserFactory()
        battle = BattleFactory(player_one=user, status=BattleStatus.ACTIVE)
        team = BattleTeamFactory(battle=battle, owner=user)

        attacker = _make_slot(team, 1, GridPosition.FRONT_LEFT)
        front_def = _make_slot(team, 2, GridPosition.FRONT_RIGHT)
        back_def = _make_slot(team, 3, GridPosition.BACK_LEFT)

        import random
        random.seed(99)
        damage_front = engine._calculate_damage(attacker, move, front_def)
        random.seed(99)
        damage_back = engine._calculate_damage(attacker, move, back_def)

        # Allow ±1 for integer truncation
        expected = int(damage_front * 0.80)
        assert abs(damage_back - expected) <= 1, (
            f"Expected back damage ≈ {expected}, got {damage_back}"
        )


@allure.epic("Battle")
@allure.feature("Positional Damage")
@pytest.mark.django_db
class TestFrontRowFirstTargeting(BaseTest):

    @allure.story("Targeting back-row redirects to front-row when front row is alive")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_back_row_target_redirected_to_front_row(self, svc):
        """
        When a player selects a back-row enemy, _validate_target must redirect
        to the lowest-HP living front-row enemy.
        """
        user = UserFactory()
        battle = BattleFactory(player_one=user, status=BattleStatus.ACTIVE)
        team = BattleTeamFactory(battle=battle, owner=user)

        front_slot = _make_slot(team, 1, GridPosition.FRONT_LEFT, hp=80)
        back_slot = _make_slot(team, 3, GridPosition.BACK_LEFT, hp=150)

        alive_enemies = [front_slot, back_slot]
        result = svc._validate_target(back_slot.pk, alive_enemies)

        assert result is not None
        assert result.pk == front_slot.pk, "Should redirect to living front-row slot"

    @allure.story("Back-row can be targeted once all front-row are fainted")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_back_row_targetable_when_front_row_cleared(self, svc):
        """
        If all front-row slots are fainted, back-row slots can be targeted directly.
        (alive_enemies only includes non-fainted slots, so no front-row will appear.)
        """
        user = UserFactory()
        battle = BattleFactory(player_one=user, status=BattleStatus.ACTIVE)
        team = BattleTeamFactory(battle=battle, owner=user)

        back_left = _make_slot(team, 3, GridPosition.BACK_LEFT, hp=100)
        back_right = _make_slot(team, 4, GridPosition.BACK_RIGHT, hp=120)

        # alive_enemies contains only back-row (front row is dead / not included)
        alive_enemies = [back_left, back_right]
        result = svc._validate_target(back_left.pk, alive_enemies)

        assert result is not None
        assert result.pk == back_left.pk

    @allure.story("Redirect selects the lowest-HP front-row target")
    @allure.severity(allure.severity_level.NORMAL)
    def test_redirect_picks_lowest_hp_front_row(self, svc):
        """When redirected, picks the front-row slot with the least HP."""
        user = UserFactory()
        battle = BattleFactory(player_one=user, status=BattleStatus.ACTIVE)
        team = BattleTeamFactory(battle=battle, owner=user)

        front_left = _make_slot(team, 1, GridPosition.FRONT_LEFT, hp=120)
        front_right = _make_slot(team, 2, GridPosition.FRONT_RIGHT, hp=50)
        back_slot = _make_slot(team, 3, GridPosition.BACK_LEFT, hp=150)

        alive_enemies = [front_left, front_right, back_slot]
        result = svc._validate_target(back_slot.pk, alive_enemies)

        assert result is not None
        assert result.pk == front_right.pk, "Should pick front_right (lower HP)"

    @allure.story("Front-row target is accepted directly")
    @allure.severity(allure.severity_level.NORMAL)
    def test_front_row_target_accepted_directly(self, svc):
        """When targeting a front-row slot, no redirect occurs."""
        user = UserFactory()
        battle = BattleFactory(player_one=user, status=BattleStatus.ACTIVE)
        team = BattleTeamFactory(battle=battle, owner=user)

        front_slot = _make_slot(team, 1, GridPosition.FRONT_LEFT, hp=100)
        back_slot = _make_slot(team, 3, GridPosition.BACK_LEFT, hp=150)

        alive_enemies = [front_slot, back_slot]
        result = svc._validate_target(front_slot.pk, alive_enemies)

        assert result is not None
        assert result.pk == front_slot.pk


@allure.epic("Battle")
@allure.feature("Positional Damage")
@pytest.mark.django_db
class TestAIPositionalTargeting(BaseTest):

    @allure.story("AI targets lowest-HP front-row slot when front row is alive")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_ai_targets_front_row(self):
        """ComboChainEngine._select_target() must pick a front-row slot."""
        from apps.game.services import ComboChainEngine
        engine = ComboChainEngine()
        normal_type = PokemonTypeFactory(name="Normal")
        move = MoveFactory(name="Tackle", move_type=normal_type, power=40)

        user = UserFactory()
        battle = BattleFactory(player_one=user, status=BattleStatus.ACTIVE)
        team = BattleTeamFactory(battle=battle, owner=user)

        front_low_hp = _make_slot(team, 1, GridPosition.FRONT_LEFT, hp=30)
        front_high_hp = _make_slot(team, 2, GridPosition.FRONT_RIGHT, hp=120)
        back_slot = _make_slot(team, 3, GridPosition.BACK_LEFT, hp=10)

        result = engine._select_target(team, move)
        assert result is not None
        assert result.pk == front_low_hp.pk, "AI must target lowest-HP front-row slot"

    @allure.story("AI targets back row when front row is cleared")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_ai_targets_back_row_when_front_cleared(self):
        """Once front row is fainted, AI picks from back row."""
        from apps.game.services import ComboChainEngine
        engine = ComboChainEngine()
        normal_type = PokemonTypeFactory(name="Normal")
        move = MoveFactory(name="Tackle", move_type=normal_type, power=40)

        user = UserFactory()
        battle = BattleFactory(player_one=user, status=BattleStatus.ACTIVE)
        team = BattleTeamFactory(battle=battle, owner=user)

        # Front row fainted
        _make_slot(team, 1, GridPosition.FRONT_LEFT, hp=0, fainted=True)
        _make_slot(team, 2, GridPosition.FRONT_RIGHT, hp=0, fainted=True)
        back_slot = _make_slot(team, 3, GridPosition.BACK_LEFT, hp=80)

        result = engine._select_target(team, move)
        assert result is not None
        assert result.pk == back_slot.pk
