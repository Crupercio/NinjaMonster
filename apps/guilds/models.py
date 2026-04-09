"""Guild / clan system models (GDD Phase 4 — Social Retention)."""
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


class Guild(models.Model):
    """
    A player-created guild (clan).

    name  — unique, shown in full on the guild page.
    tag   — 2–4 uppercase letters/digits, shown in brackets next to usernames.
    """

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

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "guild"
        verbose_name_plural = "guilds"

    def __str__(self) -> str:
        return f"[{self.tag}] {self.name}"

    def clean(self) -> None:
        if self.tag and not _TAG_PATTERN.match(self.tag.upper()):
            raise ValidationError({"tag": "Tag must be 2–4 uppercase letters or digits."})

    @property
    def member_count(self) -> int:
        return self.memberships.count()

    @property
    def is_full(self) -> bool:
        return self.member_count >= GUILD_MAX_MEMBERS


class GuildMembership(models.Model):
    """
    A user's membership in a guild.  One user ↔ one guild at a time.
    """

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

    class Meta:
        ordering = ["joined_at"]
        verbose_name = "guild membership"
        verbose_name_plural = "guild memberships"

    def __str__(self) -> str:
        return f"{self.user} in {self.guild} ({self.role})"
