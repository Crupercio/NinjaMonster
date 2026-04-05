"""
Shared helpers for constructing battle fixtures in tests.

build_battle_pair — creates two opposing BattleTeams with BattleSlots
                    wired to a single Battle, ready for engine calls.
"""
from apps.game.models import Battle, BattleRound, BattleSlot, BattleStatus, BattleTeam
from apps.pokemon.models import Move, Pokemon

from tests.framework.factories.battle_factory import (
    BattleFactory,
    BattleSlotFactory,
    BattleTeamFactory,
)
from tests.framework.factories.pokemon_factory import MoveFactory, PokemonFactory, PokemonTypeFactory
from tests.framework.factories.user_factory import UserFactory


def build_battle_pair(
    p1_moves: list[Move] | None = None,
    p2_moves: list[Move] | None = None,
    slots_per_team: int = 6,
) -> tuple[Battle, BattleTeam, BattleTeam, list[BattleSlot], list[BattleSlot]]:
    """
    Create a battle with two teams of `slots_per_team` slots each.

    Returns (battle, team1, team2, slots1, slots2).
    All Pokemon share the same type unless moves require otherwise.
    """
    user1 = UserFactory()
    user2 = UserFactory()
    battle = BattleFactory(player_one=user1, player_two=user2, status=BattleStatus.ACTIVE)

    team1 = BattleTeamFactory(battle=battle, owner=user1)
    team2 = BattleTeamFactory(battle=battle, owner=user2)

    normal_type = PokemonTypeFactory(name="Normal")

    def _make_slots(team: BattleTeam, moves: list[Move] | None) -> list[BattleSlot]:
        slots = []
        for pos in range(1, slots_per_team + 1):
            poke = PokemonFactory(primary_type=normal_type)
            if moves:
                for m in moves:
                    poke.moves.add(m)
            slot = BattleSlotFactory(team=team, pokemon=poke, position=pos)
            slots.append(slot)
        return slots

    slots1 = _make_slots(team1, p1_moves)
    slots2 = _make_slots(team2, p2_moves)

    return battle, team1, team2, slots1, slots2


def ensure_round(battle: Battle, round_number: int | None = None) -> BattleRound:
    """Get or create a BattleRound for the given round number."""
    rn = round_number if round_number is not None else battle.current_round
    round_obj, _ = BattleRound.objects.get_or_create(battle=battle, round_number=rn)
    return round_obj
