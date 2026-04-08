"""
Management command: seed_seasonal_events

Seeds the SeasonalEvent table with example Act 1 thematic events.
Safe to re-run — uses get_or_create on the name field.

Usage:
    python manage.py seed_seasonal_events
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.events.models import EventBonusType, SeasonalEvent

# All durations relative to the moment the command is run so the demo data
# is always "live" when seeded on a fresh install.
_EVENTS = [
    {
        "name": "Festival of Kizuna",
        "description": "Celebrate the bond between trainer and Pokemon with bonus Sticker Dust on every win.",
        "flavor_text": (
            "Sensei Kira: \"The Kizuna Festival honours the bonds forged in battle. "
            "Every trainer who wins this week carries the spirit of the festival forward.\""
        ),
        "event_type": EventBonusType.BONUS_DUST,
        "bonus_value": 50,
        "days_from_now_start": 0,
        "days_from_now_end": 7,
    },
    {
        "name": "Ryo Rush Weekend",
        "description": "Double your post-battle earnings this weekend — every win pays extra Ryo.",
        "flavor_text": (
            "Shin: \"Even I won't turn down free Ryo. "
            "Win your battles and claim what's yours.\""
        ),
        "event_type": EventBonusType.BONUS_RYO,
        "bonus_value": 300,
        "days_from_now_start": 10,
        "days_from_now_end": 12,
    },
    {
        "name": "Chain Masters' Cup",
        "description": "Execute combo chains of 3+ to earn bonus Sticker Dust. The longer the chain, the richer the reward.",
        "flavor_text": (
            "Sensei Kira: \"A true Kizuna master does not merely win — they create something beautiful "
            "in the process. Chain your bonds and let the dust fall where it may.\""
        ),
        "event_type": EventBonusType.DOUBLE_COMBO_DUST,
        "bonus_value": 75,
        "days_from_now_start": 20,
        "days_from_now_end": 27,
    },
]


class Command(BaseCommand):
    help = "Seed SeasonalEvent data. Safe to re-run."

    def handle(self, *args, **options):
        now = timezone.now()
        created_count = 0

        for data in _EVENTS:
            start = now + timedelta(days=data["days_from_now_start"])
            end = now + timedelta(days=data["days_from_now_end"])

            obj, created = SeasonalEvent.objects.get_or_create(
                name=data["name"],
                defaults={
                    "description": data["description"],
                    "flavor_text": data["flavor_text"],
                    "event_type": data["event_type"],
                    "bonus_value": data["bonus_value"],
                    "start_at": start,
                    "end_at": end,
                },
            )
            if created:
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seasonal events seeded: {created_count} created."
            )
        )
