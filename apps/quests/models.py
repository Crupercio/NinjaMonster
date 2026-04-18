"""Quest & Mission System models (GDD Section 14)."""
import logging

from django.conf import settings
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


class QuestType(models.TextChoices):
    DAILY = "daily", "Daily Mission"
    WEEKLY = "weekly", "Weekly Challenge"
    STORY = "story", "Story Quest"


class QuestCondition(models.TextChoices):
    WIN_BATTLES = "win_battles", "Win N Battles"
    ACHIEVE_COMBO = "achieve_combo", "Achieve N-Link Combo Chain"
    OPEN_PACKS = "open_packs", "Open N Sticker Packs"
    COMPLETE_EXPEDITIONS = "complete_expeditions", "Complete N Expeditions"
    BOND_POKEMON = "bond_pokemon", "Bond N Pokémon on Expeditions"


class RewardType(models.TextChoices):
    RYO = "ryo", "Ryo"
    STICKER_DUST = "sticker_dust", "Sticker Dust"
    STICKER_PACK = "sticker_pack", "Sticker Pack"


class QuestTemplate(models.Model):
    """
    A reusable quest definition.

    Daily and Weekly templates are randomly assigned each period.
    Story templates are assigned once per user and never expire.
    """

    name = models.TextField()
    description = models.TextField(blank=True, default="")
    quest_type = models.TextField(choices=QuestType.choices, db_index=True)
    condition = models.TextField(choices=QuestCondition.choices)
    condition_value = models.PositiveIntegerField(
        help_text="Target count or threshold to satisfy the condition."
    )
    reward_type = models.TextField(choices=RewardType.choices)
    reward_value = models.PositiveIntegerField(
        help_text="Primary reward amount (Ryo / Dust / Pack count)."
    )
    reward_dust = models.PositiveIntegerField(
        default=0,
        help_text="Secondary Sticker Dust reward (additive, may be 0).",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    order = models.PositiveSmallIntegerField(
        default=0,
        help_text="Display order (used for story quests to show unlock sequence).",
    )
    chapter = models.CharField(
        max_length=50,
        blank=True,
        default="",
        db_index=True,
        help_text="Act/chapter grouping for story quests (e.g. 'prologue', 'act_1').",
    )
    narrative_text = models.TextField(
        blank=True,
        default="",
        help_text="In-world dialogue or lore text shown alongside this quest.",
    )
    condition_meta = models.JSONField(
        blank=True,
        default=dict,
        help_text=(
            "Optional extra constraints for the condition. "
            "For achieve_combo: {'min_type_count': 3, 'type_names': ['Fire']} "
            "or {'mono_type': true} or {'all_chakra_elements': true}."
        ),
    )

    class Meta:
        ordering = ["quest_type", "order", "pk"]
        verbose_name = "quest template"
        verbose_name_plural = "quest templates"

    def __str__(self) -> str:
        return f"[{self.get_quest_type_display()}] {self.name}"

    @property
    def reward_summary(self) -> str:
        parts = []
        if self.reward_type == RewardType.RYO:
            parts.append(f"{self.reward_value} Ryo")
        elif self.reward_type == RewardType.STICKER_DUST:
            parts.append(f"{self.reward_value} Dust")
        elif self.reward_type == RewardType.STICKER_PACK:
            parts.append("1 Sticker Pack")
        if self.reward_dust:
            parts.append(f"{self.reward_dust} Dust")
        return " + ".join(parts) if parts else "—"


class UserQuest(models.Model):
    """
    A quest instance assigned to a specific user for a specific period.

    period_key encodes when the quest was assigned:
      - Daily:  "daily:2026-04-07"
      - Weekly: "weekly:2026-W15"
      - Story:  "story"  (permanent, never expires)
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quests",
        db_index=True,
    )
    template = models.ForeignKey(
        QuestTemplate,
        on_delete=models.CASCADE,
        related_name="user_quests",
        db_index=True,
    )
    period_key = models.CharField(max_length=30, db_index=True)
    progress = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False, db_index=True)
    rewarded = models.BooleanField(default=False)
    assigned_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        # Prevent duplicate assignments for the same quest in the same period
        unique_together = [("user", "template", "period_key")]
        ordering = ["template__order", "assigned_at"]
        verbose_name = "user quest"
        verbose_name_plural = "user quests"

    def __str__(self) -> str:
        return f"{self.user} — {self.template.name} ({self.period_key})"

    @property
    def progress_percent(self) -> int:
        if self.template.condition_value == 0:
            return 100
        return min(100, round(self.progress / self.template.condition_value * 100))
