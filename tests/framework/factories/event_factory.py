"""factory_boy factory for SeasonalEvent."""
from datetime import timedelta

import factory
from django.utils import timezone

from apps.events.models import EventBonusType, SeasonalEvent


class SeasonalEventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SeasonalEvent

    name = factory.Sequence(lambda n: f"Test Event {n}")
    description = "A test seasonal event."
    flavor_text = ""
    event_type = EventBonusType.BONUS_DUST
    bonus_value = 50
    start_at = factory.LazyFunction(lambda: timezone.now() - timedelta(hours=1))
    end_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=7))
    is_active = True

    class Params:
        active = factory.Trait(
            start_at=factory.LazyFunction(lambda: timezone.now() - timedelta(hours=1)),
            end_at=factory.LazyFunction(lambda: timezone.now() + timedelta(days=7)),
        )
        upcoming = factory.Trait(
            start_at=factory.LazyFunction(lambda: timezone.now() + timedelta(days=3)),
            end_at=factory.LazyFunction(lambda: timezone.now() + timedelta(days=10)),
        )
        ended = factory.Trait(
            start_at=factory.LazyFunction(lambda: timezone.now() - timedelta(days=10)),
            end_at=factory.LazyFunction(lambda: timezone.now() - timedelta(days=3)),
        )
        bonus_ryo = factory.Trait(event_type=EventBonusType.BONUS_RYO)
        bonus_dust = factory.Trait(event_type=EventBonusType.BONUS_DUST)
        double_combo_dust = factory.Trait(event_type=EventBonusType.DOUBLE_COMBO_DUST)
