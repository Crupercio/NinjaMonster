"""Fixtures scoped to the effects test package."""
import pytest

from apps.effects.models import StatusEffect
from apps.effects.constants import StatusName

from tests.framework.factories.effects_factory import StatusEffectFactory
from tests.framework.factories.battle_factory import BattleSlotFactory
from tests.framework.factories.pokemon_factory import PokemonFactory, PokemonTypeFactory


@pytest.fixture()
def fire_type():
    return PokemonTypeFactory(name="Fire")


@pytest.fixture()
def normal_type():
    return PokemonTypeFactory(name="Normal")


@pytest.fixture()
def electric_type():
    return PokemonTypeFactory(name="Electric")


@pytest.fixture()
def ice_type():
    return PokemonTypeFactory(name="Ice")


@pytest.fixture()
def poison_type():
    return PokemonTypeFactory(name="Poison")


@pytest.fixture()
def burned_status():
    return StatusEffectFactory(burned=True)


@pytest.fixture()
def poisoned_status():
    return StatusEffectFactory(poisoned=True)


@pytest.fixture()
def badly_poisoned_status():
    return StatusEffectFactory(badly_poisoned=True)


@pytest.fixture()
def paralyzed_status():
    return StatusEffectFactory(paralyzed=True)


@pytest.fixture()
def frozen_status():
    return StatusEffectFactory(frozen=True)


@pytest.fixture()
def asleep_status():
    return StatusEffectFactory(asleep=True)


@pytest.fixture()
def confused_status():
    return StatusEffectFactory(confused=True)


@pytest.fixture()
def perish_song_status():
    return StatusEffectFactory(perish_song=True)


@pytest.fixture()
def ignited_status():
    return StatusEffectFactory(ignited=True)


@pytest.fixture()
def immobile_status():
    return StatusEffectFactory(immobile=True)


@pytest.fixture()
def corroded_status():
    return StatusEffectFactory(corroded=True)


@pytest.fixture()
def enfeebled_status():
    return StatusEffectFactory(enfeebled=True)


@pytest.fixture()
def tagged_status():
    return StatusEffectFactory(tagged=True)


@pytest.fixture()
def normal_slot(normal_type):
    pokemon = PokemonFactory(primary_type=normal_type, base_hp=100)
    return BattleSlotFactory(pokemon=pokemon, current_hp=150, max_hp=150)


@pytest.fixture()
def fire_slot(fire_type):
    pokemon = PokemonFactory(primary_type=fire_type, base_hp=100)
    return BattleSlotFactory(pokemon=pokemon, current_hp=150, max_hp=150)


@pytest.fixture()
def electric_slot(electric_type):
    pokemon = PokemonFactory(primary_type=electric_type, base_hp=100)
    return BattleSlotFactory(pokemon=pokemon, current_hp=150, max_hp=150)


@pytest.fixture()
def ice_slot(ice_type):
    pokemon = PokemonFactory(primary_type=ice_type, base_hp=100)
    return BattleSlotFactory(pokemon=pokemon, current_hp=150, max_hp=150)


@pytest.fixture()
def poison_slot(poison_type):
    pokemon = PokemonFactory(primary_type=poison_type, base_hp=100)
    return BattleSlotFactory(pokemon=pokemon, current_hp=150, max_hp=150)
