"""SeasonalEventService — applies active event bonuses to battle rewards."""
import logging
from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from django.utils import timezone

from .models import EventBonusType, SeasonalEvent

if TYPE_CHECKING:
    from apps.game.models import Battle

User = get_user_model()
logger = logging.getLogger(__name__)


class SeasonalEventService:
    """Orchestrates seasonal event querying and reward bonus application."""

    def get_active_events(self) -> QuerySet[SeasonalEvent]:
        """Return all events currently within their time window."""
        now = timezone.now()
        return SeasonalEvent.objects.filter(
            is_active=True,
            start_at__lte=now,
            end_at__gte=now,
        )

    def get_upcoming_events(self) -> QuerySet[SeasonalEvent]:
        """Return events scheduled to start in the future."""
        now = timezone.now()
        return SeasonalEvent.objects.filter(is_active=True, start_at__gt=now)

    def get_recent_ended_events(self) -> QuerySet[SeasonalEvent]:
        """Return the 5 most recently ended events (for event history display)."""
        now = timezone.now()
        return SeasonalEvent.objects.filter(
            is_active=True, end_at__lt=now
        ).order_by("-end_at")[:5]

    def apply_battle_win_bonus(
        self, winner: User, battle: "Battle"
    ) -> dict[str, int]:
        """
        Apply all active event bonuses to the winner after a battle.

        Returns a dict of what was granted, e.g. {"ryo": 200, "sticker_dust": 100}.
        Awards are applied directly to the user model (atomic per field save).
        """
        active = list(self.get_active_events())
        if not active:
            return {}

        ryo_bonus = 0
        dust_bonus = 0

        for event in active:
            if event.event_type == EventBonusType.BONUS_RYO:
                ryo_bonus += event.bonus_value
            elif event.event_type == EventBonusType.BONUS_DUST:
                dust_bonus += event.bonus_value
            elif event.event_type == EventBonusType.DOUBLE_COMBO_DUST:
                # Double dust only if the battle had a combo chain of 3+
                if battle.max_combo_chain >= 3:
                    dust_bonus += event.bonus_value

        summary: dict[str, int] = {}
        fields_to_save: list[str] = []

        if ryo_bonus > 0:
            winner.ryo += ryo_bonus
            fields_to_save.append("ryo")
            summary["ryo"] = ryo_bonus

        if dust_bonus > 0:
            winner.sticker_dust += dust_bonus
            fields_to_save.append("sticker_dust")
            summary["sticker_dust"] = dust_bonus

        if fields_to_save:
            winner.save(update_fields=fields_to_save)
            logger.info(
                "Event bonus applied to %s (battle #%d): %s",
                winner,
                battle.pk,
                summary,
            )

        return summary
