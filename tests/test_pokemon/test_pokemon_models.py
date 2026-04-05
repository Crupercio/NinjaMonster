"""Tests for Pokemon domain models: PokemonType, Move, Pokemon."""
import pytest
import allure

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.pokemon_factory import (
    MoveFactory,
    PokemonFactory,
    PokemonTypeFactory,
)
from tests.framework.factories.effects_factory import StatusEffectFactory


# ===========================================================================
# PokemonType
# ===========================================================================

@allure.epic("Pokemon")
@allure.feature("PokemonType")
class TestPokemonType(BaseTest):

    @allure.story("Type name is stored and retrieved correctly")
    @allure.severity(allure.severity_level.NORMAL)
    def test_type_str(self):
        # Arrange / Act
        ptype = PokemonTypeFactory(name="Fire")

        # Assert
        assert str(ptype) == "Fire"

    @allure.story("Types are unique by name")
    @allure.severity(allure.severity_level.NORMAL)
    def test_type_uniqueness(self):
        PokemonTypeFactory(name="Water")
        # django_get_or_create means a second call returns the same object
        second = PokemonTypeFactory(name="Water")
        from apps.pokemon.models import PokemonType
        assert PokemonType.objects.filter(name="Water").count() == 1
        assert second.name == "Water"


# ===========================================================================
# Move
# ===========================================================================

@allure.epic("Pokemon")
@allure.feature("Move")
class TestMove(BaseTest):

    @allure.story("Move with no status has is_combo_trigger=False")
    @allure.severity(allure.severity_level.NORMAL)
    def test_move_no_status(self):
        # Arrange
        move = MoveFactory(applies_status=None, trigger_status=None)

        # Assert
        assert move.is_combo_trigger is False
        assert move.is_status_applier is False

    @allure.story("Move with applies_status has is_status_applier=True")
    @allure.severity(allure.severity_level.NORMAL)
    def test_move_applies_status(self):
        # Arrange
        status = StatusEffectFactory(burned=True)
        move = MoveFactory(applies_status=status, trigger_status=None)

        # Assert
        assert move.is_status_applier is True
        assert move.is_combo_trigger is False

    @allure.story("Move with trigger_status has is_combo_trigger=True")
    @allure.severity(allure.severity_level.NORMAL)
    def test_move_trigger_status(self):
        # Arrange
        status = StatusEffectFactory(burned=True)
        move = MoveFactory(applies_status=None, trigger_status=status)

        # Assert
        assert move.is_combo_trigger is True
        assert move.is_status_applier is False

    @allure.story("Move that both applies and triggers is both applier and trigger")
    @allure.severity(allure.severity_level.NORMAL)
    def test_move_combo_bridge(self):
        # Arrange
        burn = StatusEffectFactory(burned=True)
        poison = StatusEffectFactory(poisoned=True)
        move = MoveFactory(applies_status=poison, trigger_status=burn)

        # Assert
        assert move.is_status_applier is True
        assert move.is_combo_trigger is True

    @allure.story("Move __str__ returns its name")
    @allure.severity(allure.severity_level.TRIVIAL)
    def test_move_str(self):
        move = MoveFactory(name="Flamethrower")
        assert str(move) == "Flamethrower"


# ===========================================================================
# Pokemon stat calculations
# ===========================================================================

@allure.epic("Pokemon")
@allure.feature("Pokemon Stats")
class TestPokemonModel(BaseTest):

    @allure.story("calculate_max_hp formula: (2*base*level)/100 + level + 10")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.parametrize("base_hp,level,expected", [
        (100, 50, 160),   # (2*100*50)/100 + 50 + 10 = 160
        (45, 1,    11),   # (2*45*1)/100 + 1 + 10 = 11
        (255, 100, 620),  # (2*255*100)/100 + 100 + 10 = 620
        (80, 100, 270),   # (2*80*100)/100 + 100 + 10 = 270
    ])
    def test_calculate_max_hp(self, base_hp, level, expected):
        # Arrange
        pokemon = PokemonFactory(base_hp=base_hp)

        # Act
        result = pokemon.calculate_max_hp(level)

        # Assert
        assert result == expected

    @allure.story("calculate_stat formula: (2*base*level)/100 + 5")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.parametrize("base_stat,level,expected", [
        (80, 50, 85),    # (2*80*50)/100 + 5 = 85
        (45, 1,   5),    # (2*45*1)/100 + 5 = 5 (int floors to 0, +5=5)
        (130, 100, 265), # (2*130*100)/100 + 5 = 265
    ])
    def test_calculate_stat(self, base_stat, level, expected):
        # Arrange
        pokemon = PokemonFactory()

        # Act
        result = pokemon.calculate_stat(base_stat, level)

        # Assert
        assert result == expected

    @allure.story("Pokemon __str__ returns its name")
    @allure.severity(allure.severity_level.TRIVIAL)
    def test_pokemon_str(self):
        pokemon = PokemonFactory(name="Pikachu")
        assert str(pokemon) == "Pikachu"

    @allure.story("Pokemon with moves M2M association")
    @allure.severity(allure.severity_level.NORMAL)
    def test_pokemon_moves_m2m(self):
        # Arrange
        normal_type = PokemonTypeFactory(name="Normal")
        move1 = MoveFactory(name="Tackle", move_type=normal_type)
        move2 = MoveFactory(name="Scratch", move_type=normal_type)
        pokemon = PokemonFactory(moves=[move1, move2])

        # Act
        pokemon.refresh_from_db()
        move_names = set(pokemon.moves.values_list("name", flat=True))

        # Assert
        assert move_names == {"Tackle", "Scratch"}

    @allure.story("Secondary type is optional")
    @allure.severity(allure.severity_level.NORMAL)
    def test_pokemon_no_secondary_type(self):
        pokemon = PokemonFactory(secondary_type=None)
        assert pokemon.secondary_type is None
