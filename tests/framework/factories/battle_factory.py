"""factory_boy factories for Battle, BattleTeam, BattleSlot."""
import factory

from apps.game.models import AIDifficulty, Battle, BattleSlot, BattleStatus, BattleTeam

from .pokemon_factory import PokemonFactory
from .user_factory import UserFactory


class BattleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Battle

    player_one = factory.SubFactory(UserFactory)
    player_two = factory.SubFactory(UserFactory)
    status = BattleStatus.ACTIVE
    current_round = 1
    winner = None
    max_combo_chain = 0
    is_ai_battle = False
    ai_difficulty = AIDifficulty.MEDIUM


class BattleTeamFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BattleTeam

    battle = factory.SubFactory(BattleFactory)
    owner = factory.SubFactory(UserFactory)


class BattleSlotFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BattleSlot

    team = factory.SubFactory(BattleTeamFactory)
    pokemon = factory.SubFactory(PokemonFactory)
    position = factory.Sequence(lambda n: (n % 6) + 1)
    level = 50
    current_hp = 150
    max_hp = 150
    is_fainted = False
    last_move_used = None
