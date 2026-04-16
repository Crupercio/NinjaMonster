"""
Phase 7 — BattleValidator and 6-slot battle setup tests.

Covers:
  - BattleValidator accepts a valid 6-slot AI team
  - BattleValidator rejects team with < 6 active slots
  - BattleValidator rejects OwnedPokemon slot missing move assignments
  - set_team creates exactly 6 slots mapped to correct grid positions
  - start_battle requires 2 teams
  - start_battle transitions battle to ACTIVE
  - POSITION_TO_GRID maps positions 1-6 to all 6 grid cells
  - All 6 grid positions are in ACTIVE_GRID_POSITIONS
"""
import allure
import pytest

from apps.game.models import (
    ACTIVE_GRID_POSITIONS,
    POSITION_TO_GRID,
    BattleLog,
    BattleSlot,
    BattleStatus,
    BattleTeam,
    GridPosition,
    LogType,
)
from apps.game.services import BattleService, BattleValidator

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.battle_factory import (
    BattleFactory,
    BattleSlotFactory,
    BattleTeamFactory,
)
from tests.framework.factories.pokemon_factory import (
    MoveFactory,
    PokemonFactory,
    PokemonTypeFactory,
)
from tests.framework.factories.user_factory import UserFactory

_svc = BattleService()
_validator = BattleValidator()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pokemon_with_move():
    """Create a Pokemon species with at least one move in its pool."""
    ptype = PokemonTypeFactory(name="Normal")
    move = MoveFactory(name=f"BasicMove_{id(ptype)}", move_type=ptype, power=50)
    pokemon = PokemonFactory(primary_type=ptype)
    pokemon.moves.add(move)
    return pokemon


def _make_6slot_ai_team(battle, user) -> BattleTeam:
    """Build a BattleTeam with 6 AI slots (no owned_pokemon), all with species moves."""
    team = BattleTeamFactory(battle=battle, owner=user)
    for pos in range(1, 7):
        poke = _make_pokemon_with_move()
        grid_pos = POSITION_TO_GRID[pos]
        BattleSlotFactory(
            team=team,
            pokemon=poke,
            position=pos,
            grid_position=grid_pos,
            is_active=True,
        )
    return team


# ===========================================================================
# TestGridPositionMapping
# ===========================================================================

@allure.epic("Battle")
@allure.feature("6v6 Setup")
class TestGridPositionMapping(BaseTest):

    @allure.story("POSITION_TO_GRID maps all 6 positions to named grid cells")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_six_positions_mapped(self):
        assert set(POSITION_TO_GRID.keys()) == {1, 2, 3, 4, 5, 6}

    @allure.story("Positions 1-3 map to front row")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_front_row_positions(self):
        front_positions = {GridPosition.FRONT_LEFT, GridPosition.FRONT_CENTER, GridPosition.FRONT_RIGHT}
        for pos in (1, 2, 3):
            assert POSITION_TO_GRID[pos] in front_positions, f"Position {pos} should be front row"

    @allure.story("Positions 4-6 map to back row")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_back_row_positions(self):
        back_positions = {GridPosition.BACK_LEFT, GridPosition.BACK_CENTER, GridPosition.BACK_RIGHT}
        for pos in (4, 5, 6):
            assert POSITION_TO_GRID[pos] in back_positions, f"Position {pos} should be back row"

    @allure.story("All 6 grid positions are in ACTIVE_GRID_POSITIONS")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_all_positions_active(self):
        for pos, grid_pos in POSITION_TO_GRID.items():
            assert grid_pos in ACTIVE_GRID_POSITIONS, f"Position {pos} ({grid_pos}) should be active"

    @allure.story("ACTIVE_GRID_POSITIONS contains exactly 6 positions")
    @allure.severity(allure.severity_level.NORMAL)
    def test_active_grid_has_six_slots(self):
        assert len(ACTIVE_GRID_POSITIONS) == 6


# ===========================================================================
# TestBattleValidator
# ===========================================================================

@allure.epic("Battle")
@allure.feature("6v6 Setup")
class TestBattleValidator(BaseTest):

    @allure.story("Valid 6-slot AI battle passes validation")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_valid_battle_passes(self):
        user1, user2 = UserFactory(), UserFactory()
        battle = BattleFactory(player_one=user1, player_two=user2, status=BattleStatus.SETUP)
        _make_6slot_ai_team(battle, user1)
        _make_6slot_ai_team(battle, user2)

        # Should not raise
        _validator.validate(battle)

    @allure.story("Team with fewer than 6 active slots fails validation")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_insufficient_slots_fails(self):
        user1, user2 = UserFactory(), UserFactory()
        battle = BattleFactory(player_one=user1, player_two=user2, status=BattleStatus.SETUP)

        # Team 1: only 4 slots
        team1 = BattleTeamFactory(battle=battle, owner=user1)
        for pos in range(1, 5):
            poke = _make_pokemon_with_move()
            BattleSlotFactory(team=team1, pokemon=poke, position=pos, is_active=True)

        # Team 2: full 6 slots
        _make_6slot_ai_team(battle, user2)

        with pytest.raises(ValueError, match="expected 6"):
            _validator.validate(battle)

    @allure.story("AI slot with no species moves fails validation")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_ai_slot_no_moves_fails(self):
        user1, user2 = UserFactory(), UserFactory()
        battle = BattleFactory(player_one=user1, player_two=user2, status=BattleStatus.SETUP)

        # Team 1: slots with no moves in species pool
        team1 = BattleTeamFactory(battle=battle, owner=user1)
        ptype = PokemonTypeFactory(name="TypeNoMove")
        for pos in range(1, 7):
            poke = PokemonFactory(primary_type=ptype)  # no moves added
            BattleSlotFactory(team=team1, pokemon=poke, position=pos, is_active=True)

        _make_6slot_ai_team(battle, user2)

        with pytest.raises(ValueError, match="no moves"):
            _validator.validate(battle)

    @allure.story("start_battle requires exactly 2 teams")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_start_battle_requires_two_teams(self):
        user1 = UserFactory()
        battle = BattleFactory(player_one=user1, status=BattleStatus.SETUP)
        # Only 1 team
        _make_6slot_ai_team(battle, user1)

        with pytest.raises(ValueError, match="2 teams"):
            _svc.start_battle(battle)

    @allure.story("start_battle transitions battle to ACTIVE")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_start_battle_transitions_to_active(self):
        user1, user2 = UserFactory(), UserFactory()
        battle = BattleFactory(player_one=user1, player_two=user2, status=BattleStatus.SETUP)
        _make_6slot_ai_team(battle, user1)
        _make_6slot_ai_team(battle, user2)

        result = _svc.start_battle(battle)

        assert result.status == BattleStatus.ACTIVE

    @allure.story("start_battle creates BattleLog INFO entry")
    @allure.severity(allure.severity_level.NORMAL)
    def test_start_battle_creates_log_entry(self):
        user1, user2 = UserFactory(), UserFactory()
        battle = BattleFactory(player_one=user1, player_two=user2, status=BattleStatus.SETUP)
        _make_6slot_ai_team(battle, user1)
        _make_6slot_ai_team(battle, user2)

        _svc.start_battle(battle)

        assert BattleLog.objects.filter(battle=battle, log_type=LogType.INFO).exists()

    @allure.story("set_team creates exactly 6 BattleSlots for valid Pokemon list")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_set_team_creates_six_slots(self):
        user = UserFactory()
        battle = BattleFactory(player_one=user, status=BattleStatus.SETUP)

        pokemon_list = [_make_pokemon_with_move() for _ in range(6)]
        pokemon_ids = [p.pk for p in pokemon_list]

        _svc.set_team(battle, user, pokemon_ids)

        team = BattleTeam.objects.get(battle=battle, owner=user)
        assert BattleSlot.objects.filter(team=team).count() == 6

    @allure.story("set_team rejects list with wrong number of Pokemon")
    @allure.severity(allure.severity_level.NORMAL)
    def test_set_team_rejects_wrong_count(self):
        user = UserFactory()
        battle = BattleFactory(player_one=user, status=BattleStatus.SETUP)

        pokemon_ids = [_make_pokemon_with_move().pk for _ in range(4)]

        with pytest.raises(ValueError, match="exactly 6"):
            _svc.set_team(battle, user, pokemon_ids)

    @allure.story("set_team cannot be called after battle starts")
    @allure.severity(allure.severity_level.NORMAL)
    def test_set_team_rejected_after_start(self):
        user = UserFactory()
        battle = BattleFactory(player_one=user, status=BattleStatus.ACTIVE)
        pokemon_ids = [_make_pokemon_with_move().pk for _ in range(6)]

        with pytest.raises(ValueError, match="after the battle"):
            _svc.set_team(battle, user, pokemon_ids)

    @allure.story("set_team assigns correct grid positions (positions 1-6 → front/back row)")
    @allure.severity(allure.severity_level.NORMAL)
    def test_set_team_assigns_grid_positions(self):
        user = UserFactory()
        battle = BattleFactory(player_one=user, status=BattleStatus.SETUP)
        pokemon_ids = [_make_pokemon_with_move().pk for _ in range(6)]

        _svc.set_team(battle, user, pokemon_ids)

        team = BattleTeam.objects.get(battle=battle, owner=user)
        slots = list(BattleSlot.objects.filter(team=team).order_by("position"))

        front_positions = {GridPosition.FRONT_LEFT, GridPosition.FRONT_CENTER, GridPosition.FRONT_RIGHT}
        back_positions = {GridPosition.BACK_LEFT, GridPosition.BACK_CENTER, GridPosition.BACK_RIGHT}

        for slot in slots[:3]:
            assert slot.grid_position in front_positions
        for slot in slots[3:]:
            assert slot.grid_position in back_positions
