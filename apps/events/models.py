"""Seasonal Events models (GDD Section 20.11 / Phase 4)."""
import logging

from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


class EventBonusType(models.TextChoices):
    BONUS_RYO = "bonus_ryo", "Bonus Ryo on Win"
    BONUS_DUST = "bonus_dust", "Bonus Sticker Dust on Win"
    DOUBLE_COMBO_DUST = "double_combo_dust", "Double Dust for Combo Wins"
    BONUS_PACK_CHANCE = "bonus_pack_chance", "Reduced Pack Win Threshold"


class SeasonalEvent(models.Model):
    """
    A time-limited in-game event that applies bonus rewards during its window.

    Events stack: if two events are active simultaneously, both bonuses apply.
    """

    name = models.TextField()
    description = models.TextField(blank=True, default="")
    flavor_text = models.TextField(
        blank=True,
        default="",
        help_text="Narrative / lore blurb shown on the event banner.",
    )
    event_type = models.TextField(choices=EventBonusType.choices, db_index=True)
    bonus_value = models.PositiveIntegerField(
        help_text="Bonus Ryo or Sticker Dust awarded per qualifying win. Ignored for BONUS_PACK_CHANCE.",
    )
    start_at = models.DateTimeField(db_index=True)
    end_at = models.DateTimeField(db_index=True)
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Master on/off switch — set False to disable without deleting.",
    )

    class Meta:
        ordering = ["-start_at"]
        verbose_name = "seasonal event"
        verbose_name_plural = "seasonal events"

    def __str__(self) -> str:
        return f"{self.name} ({self.start_at.date()} → {self.end_at.date()})"

    @property
    def is_running(self) -> bool:
        """True if the event is active and within its time window right now."""
        now = timezone.now()
        return bool(self.is_active and self.start_at <= now <= self.end_at)

    @property
    def status_label(self) -> str:
        if not self.is_active:
            return "disabled"
        now = timezone.now()
        if now < self.start_at:
            return "upcoming"
        if now > self.end_at:
            return "ended"
        return "active"
