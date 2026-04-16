"""factory_boy factories for PokemonType, Move, Pokemon, and OwnedPokemon."""
import factory

from apps.pokemon.models import Move, OwnedPokemon, Pokemon, PokemonType


class PokemonTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PokemonType
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"Type{n}")


class MoveFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Move

    name = factory.Sequence(lambda n: f"Move{n}")
    move_type = factory.SubFactory(PokemonTypeFactory)
    power = 60
    accuracy = 100
    pp = 15
    applies_status = None
    trigger_status = None
    description = ""

    class Params:
        # Trait: creates a move that applies the given status
        with_applies = factory.Trait(
            applies_status=factory.SubFactory(
                "tests.framework.factories.effects_factory.StatusEffectFactory"
            )
        )
        # Trait: creates a move that triggers on the given status
        with_trigger = factory.Trait(
            trigger_status=factory.SubFactory(
                "tests.framework.factories.effects_factory.StatusEffectFactory"
            )
        )


class PokemonFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Pokemon
        skip_postgeneration_save = True

    name = factory.Sequence(lambda n: f"Pokemon{n}")
    primary_type = factory.SubFactory(PokemonTypeFactory)
    secondary_type = None
    base_hp = 80
    base_attack = 80
    base_defense = 80
    base_ninjutsu = 80
    base_sp_defense = 80
    base_initiative = 80
    sprite_url = ""
    pokedex_number = factory.Sequence(lambda n: 900 + n)

    @factory.post_generation
    def moves(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for move in extracted:
                self.moves.add(move)


class OwnedPokemonFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OwnedPokemon

    owner = factory.SubFactory(
        "tests.framework.factories.user_factory.UserFactory"
    )
    species = factory.SubFactory(PokemonFactory)
    level = 1
    experience = 0
    is_training = False
