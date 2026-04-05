"""Fixtures scoped to the stickers test package."""
import pytest

from apps.stickers.services import StickerService, TradeService

from tests.framework.factories.pokemon_factory import PokemonFactory, PokemonTypeFactory
from tests.framework.factories.sticker_factory import StickerFactory
from tests.framework.factories.user_factory import UserFactory


@pytest.fixture()
def sticker_svc() -> StickerService:
    return StickerService()


@pytest.fixture()
def trade_svc() -> TradeService:
    return TradeService()


@pytest.fixture()
def normal_type():
    return PokemonTypeFactory(name="Normal")


@pytest.fixture()
def player(normal_type):
    user = UserFactory()
    user.battles_won = 0
    user.sticker_dust = 0
    user.save(update_fields=["battles_won", "sticker_dust"])
    return user


@pytest.fixture()
def other_player(normal_type):
    user = UserFactory()
    user.battles_won = 0
    user.sticker_dust = 0
    user.save(update_fields=["battles_won", "sticker_dust"])
    return user


@pytest.fixture()
def bulbasaur(normal_type):
    return PokemonFactory(name="Bulbasaur", primary_type=normal_type, base_hp=45)


@pytest.fixture()
def charmander(normal_type):
    return PokemonFactory(name="Charmander", primary_type=normal_type, base_hp=39)
