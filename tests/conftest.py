"""
Root pytest conftest.

Provides session-scoped and function-scoped fixtures used across all test modules.
"""
import pytest

from apps.effects.engine import StatusEffectEngine
from apps.game.services import BattleService, ComboChainEngine


@pytest.fixture(scope="session")
def effect_engine() -> StatusEffectEngine:
    """Shared StatusEffectEngine instance (stateless — safe to reuse)."""
    return StatusEffectEngine()


@pytest.fixture(scope="session")
def combo_engine() -> ComboChainEngine:
    """Shared ComboChainEngine instance."""
    return ComboChainEngine()


@pytest.fixture(scope="session")
def battle_service() -> BattleService:
    """Shared BattleService instance."""
    return BattleService()
