"""Status effect models."""
import logging

from django.db import models

from .constants import StatusCategory, StatusName

logger = logging.getLogger(__name__)


class StatusEffect(models.Model):
    """
    Represents a status condition that can be applied to a Pokemon in battle.

    The name field uses StatusName choices and is the canonical identifier used
    throughout the combo chain system.
    """

    name = models.TextField(unique=True, choices=StatusName.choices)
    category = models.TextField(choices=StatusCategory.choices, db_index=True)
    description = models.TextField(blank=True, default="")
    default_duration = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Default duration in rounds. Null means indefinite.",
    )
    damage_per_turn = models.PositiveIntegerField(
        default=0,
        help_text="Damage dealt each turn as 1/16 fractions of max HP.",
    )
    prevents_action = models.BooleanField(
        default=False,
        help_text="If True, the Pokemon cannot act while this status is active.",
    )
    modifies_stats = models.JSONField(
        null=True,
        blank=True,
        help_text="Dict mapping stat name to float multiplier, e.g. {'attack': 0.5}",
    )
    disables_healing = models.BooleanField(
        default=False,
        help_text="If True, the Pokemon cannot recover HP while this status is active.",
    )

    class Meta:
        ordering = ["category", "name"]
        verbose_name = "status effect"
        verbose_name_plural = "status effects"

    def __str__(self) -> str:
        return self.get_name_display()


class ActiveStatusEffect(models.Model):
    """
    A status effect currently active on a specific BattleSlot.

    Tracks remaining duration and escalating damage for badly_poisoned / corroded.
    """

    slot = models.ForeignKey(
        "game.BattleSlot",
        on_delete=models.CASCADE,
        related_name="active_statuses",
        db_index=True,
    )
    status = models.ForeignKey(
        StatusEffect,
        on_delete=models.CASCADE,
        related_name="active_instances",
        db_index=True,
    )
    remaining_turns = models.IntegerField(
        null=True,
        blank=True,
        help_text="Null means indefinite. Decremented each turn.",
    )
    applied_at_round = models.PositiveIntegerField()
    turns_active = models.PositiveIntegerField(
        default=0,
        help_text="Incremented each turn; used for escalating effects.",
    )
    applied_by_slot = models.ForeignKey(
        "game.BattleSlot",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="seeded_targets",
        help_text="The slot that applied this effect (used for SEEDED drain).",
    )

    class Meta:
        unique_together = [("slot", "status")]
        verbose_name = "active status effect"
        verbose_name_plural = "active status effects"

    def __str__(self) -> str:
        return f"{self.slot} — {self.status}"
