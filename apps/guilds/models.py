"""Guild and guild album models."""

import logging
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)

GUILD_CREATE_COST_RYO: int = 1_000
GUILD_MAX_MEMBERS: int = 20
_TAG_PATTERN = re.compile(r"^[A-Z0-9]{2,4}$")


class GuildRole(models.TextChoices):
    OWNER = "owner", "Owner"
    OFFICER = "officer", "Officer"
    MEMBER = "member", "Member"


class GuildQuestPeriod(models.TextChoices):
    DAILY = "daily", "Daily"
    WEEKLY = "weekly", "Weekly"


class Guild(models.Model):
    """A player-created guild."""

    name = models.TextField(unique=True)
    tag = models.CharField(
        max_length=4,
        unique=True,
        help_text="2–4 uppercase letters/digits shown next to member names.",
    )
    description = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="guilds_founded",
        db_index=True,
    )
    created_at = models.DateTimeField(default=timezone.now)
    is_recruiting = models.BooleanField(
        default=True,
        help_text="When False, no new members can join via the public join button.",
    )
    level = models.PositiveIntegerField(default=1)
    xp = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "guild"
        verbose_name_plural = "guilds"

    def __str__(self) -> str:
        return f"[{self.tag}] {self.name}"

    def clean(self) -> None:
        if self.tag and not _TAG_PATTERN.match(self.tag.upper()):
            raise ValidationError({"tag": "Tag must be 2-4 uppercase letters or digits."})

    @property
    def member_count(self) -> int:
        return self.memberships.count()

    @property
    def is_full(self) -> bool:
        return self.member_count >= GUILD_MAX_MEMBERS


class GuildMembership(models.Model):
    """A user's membership in a guild. One user belongs to one guild at a time."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="guild_membership",
        db_index=True,
    )
    guild = models.ForeignKey(
        Guild,
        on_delete=models.CASCADE,
        related_name="memberships",
        db_index=True,
    )
    role = models.TextField(
        choices=GuildRole.choices,
        default=GuildRole.MEMBER,
        db_index=True,
    )
    joined_at = models.DateTimeField(default=timezone.now)
    contribution_points = models.PositiveIntegerField(default=0)
    donated_stickers = models.PositiveIntegerField(default=0)
    guild_quests_completed = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["joined_at"]
        verbose_name = "guild membership"
        verbose_name_plural = "guild memberships"

    def __str__(self) -> str:
        return f"{self.user} in {self.guild} ({self.role})"


class GuildAlbumEntry(models.Model):
    """A sticker donated into a guild album and permanently soul-bound there."""

    guild = models.ForeignKey(
        Guild,
        on_delete=models.CASCADE,
        related_name="album_entries",
        db_index=True,
    )
    sticker = models.OneToOneField(
        "stickers.Sticker",
        on_delete=models.CASCADE,
        related_name="guild_album_entry",
        db_index=True,
    )
    donated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="guild_album_donations",
        db_index=True,
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "guild album entry"
        verbose_name_plural = "guild album entries"

    def __str__(self) -> str:
        return f"{self.guild} <- {self.sticker}"


class GuildQuestClaim(models.Model):
    """Tracks claimed daily and weekly guild contribution quests."""

    guild = models.ForeignKey(
        Guild,
        on_delete=models.CASCADE,
        related_name="quest_claims",
        db_index=True,
    )
    membership = models.ForeignKey(
        GuildMembership,
        on_delete=models.CASCADE,
        related_name="quest_claims",
        db_index=True,
    )
    quest_key = models.CharField(max_length=32)
    period = models.CharField(max_length=16, choices=GuildQuestPeriod.choices)
    period_start = models.DateField(db_index=True)
    claimed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("membership", "quest_key", "period", "period_start")]
        ordering = ["-claimed_at"]
        verbose_name = "guild quest claim"
        verbose_name_plural = "guild quest claims"

    def __str__(self) -> str:
        return f"{self.membership} claimed {self.quest_key} ({self.period})"
