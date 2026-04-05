"""Fixtures scoped to the game test package."""
import pytest

from apps.effects.constants import StatusName
from apps.effects.models import StatusEffect
from apps.game.models import BattleRound, BattleStatus
from apps.game.services import BattleService, ComboChainEngine
from apps.pokemon.models import Move

from tests.framework.factories.battle_factory import (
    BattleFactory,
    BattleSlotFactory,
    BattleTeamFactory,
)
from tests.framework.factories.effects_factory import StatusEffectFactory
from tests.framework.factories.pokemon_factory import (
    MoveFactory,
    PokemonFactory,
    PokemonTypeFactory,
)
from tests.framework.factories.user_factory import UserFactory
from tests.framework.helpers.battle_helpers import build_battle_pair, ensure_round


@pytest.fixture()
def svc() -> BattleService:
    return BattleService()


@pytest.fixture()
def chain_engine() -> ComboChainEngine:
    return ComboChainEngine()


@pytest.fixture()
def normal_type():
    return PokemonTypeFactory(name="Normal")


# ---------------------------------------------------------------------------
# Pre-built status effects
# ---------------------------------------------------------------------------

@pytest.fixture()
def burn_status():
    return StatusEffectFactory(burned=True)


@pytest.fixture()
def poison_status():
    return StatusEffectFactory(poisoned=True)


@pytest.fixture()
def ignited_status():
    return StatusEffectFactory(ignited=True)


@pytest.fixture()
def tagged_status():
    return StatusEffectFactory(tagged=True)


@pytest.fixture()
def enfeebled_status():
    return StatusEffectFactory(enfeebled=True)


@pytest.fixture()
def corroded_status():
    return StatusEffectFactory(corroded=True)


# ---------------------------------------------------------------------------
# Pre-built chain: Move A applies burn, Move B triggers on burn
# ---------------------------------------------------------------------------

@pytest.fixture()
def burn_applies_move(burn_status, normal_type):
    """A move that applies BURNED."""
    return MoveFactory(
        name="BurnApply",
        move_type=normal_type,
        power=60,
        applies_status=burn_status,
        trigger_status=None,
    )


@pytest.fixture()
def burn_trigger_move(burn_status, normal_type):
    """A move that triggers when target has BURNED."""
    return MoveFactory(
        name="BurnTrigger",
        move_type=normal_type,
        power=60,
        applies_status=None,
        trigger_status=burn_status,
    )


@pytest.fixture()
def burn_applies_poison_trigger_move(burn_status, poison_status, normal_type):
    """A move that triggers on BURNED and also applies POISONED (depth-2 chain)."""
    return MoveFactory(
        name="BurnTriggerPoison",
        move_type=normal_type,
        power=60,
        applies_status=poison_status,
        trigger_status=burn_status,
    )


@pytest.fixture()
def poison_trigger_move(poison_status, normal_type):
    """A move that triggers when target has POISONED (depth-3 end)."""
    return MoveFactory(
        name="PoisonTrigger",
        move_type=normal_type,
        power=60,
        applies_status=None,
        trigger_status=poison_status,
    )
