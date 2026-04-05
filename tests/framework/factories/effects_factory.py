"""factory_boy factories for StatusEffect and ActiveStatusEffect."""
import factory

from apps.effects.constants import StatusCategory, StatusName
from apps.effects.models import ActiveStatusEffect, StatusEffect


class StatusEffectFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = StatusEffect
        django_get_or_create = ("name",)

    name = StatusName.BURNED
    category = StatusCategory.PERSISTENT
    description = "Test status effect."
    default_duration = None
    damage_per_turn = 0
    prevents_action = False
    modifies_stats = None
    disables_healing = False

    class Params:
        burned = factory.Trait(
            name=StatusName.BURNED,
            category=StatusCategory.PERSISTENT,
            damage_per_turn=1,
            modifies_stats={"attack": 0.5},
        )
        poisoned = factory.Trait(
            name=StatusName.POISONED,
            category=StatusCategory.PERSISTENT,
            damage_per_turn=2,
        )
        badly_poisoned = factory.Trait(
            name=StatusName.BADLY_POISONED,
            category=StatusCategory.PERSISTENT,
            damage_per_turn=1,
        )
        paralyzed = factory.Trait(
            name=StatusName.PARALYZED,
            category=StatusCategory.PERSISTENT,
            modifies_stats={"speed": 0.5},
        )
        frozen = factory.Trait(
            name=StatusName.FROZEN,
            category=StatusCategory.PERSISTENT,
            prevents_action=True,
        )
        asleep = factory.Trait(
            name=StatusName.ASLEEP,
            category=StatusCategory.PERSISTENT,
            prevents_action=True,
        )
        confused = factory.Trait(
            name=StatusName.CONFUSED,
            category=StatusCategory.VOLATILE,
        )
        perish_song = factory.Trait(
            name=StatusName.PERISH_SONG,
            category=StatusCategory.VOLATILE,
            default_duration=3,
        )
        ignited = factory.Trait(
            name=StatusName.IGNITED,
            category=StatusCategory.NARUTO,
            damage_per_turn=1,
            disables_healing=True,
        )
        tagged = factory.Trait(
            name=StatusName.TAGGED,
            category=StatusCategory.NARUTO,
            modifies_stats={"defense": 0.7, "sp_defense": 0.7},
        )
        immobile = factory.Trait(
            name=StatusName.IMMOBILE,
            category=StatusCategory.NARUTO,
            prevents_action=True,
            default_duration=1,
        )
        corroded = factory.Trait(
            name=StatusName.CORRODED,
            category=StatusCategory.NARUTO,
            damage_per_turn=1,
        )
        enfeebled = factory.Trait(
            name=StatusName.ENFEEBLED,
            category=StatusCategory.NARUTO,
            modifies_stats={"attack": 0.5, "sp_attack": 0.5},
        )
        chaos = factory.Trait(
            name=StatusName.CHAOS,
            category=StatusCategory.NARUTO,
            default_duration=1,
        )


class ActiveStatusEffectFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ActiveStatusEffect

    slot = None  # must be provided
    status = factory.SubFactory(StatusEffectFactory)
    remaining_turns = None
    applied_at_round = 1
    turns_active = 0
