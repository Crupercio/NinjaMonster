"""Ranked season, profile, and matchmaking queue models."""
import logging

from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tier definitions matching GDD §15.3
# ---------------------------------------------------------------------------

class RankedTier(models.TextChoices):
    BRONZE = "bronze", "Bronze"
    SILVER = "silver", "Silver"
    GOLD = "gold", "Gold"
    PLATINUM = "platinum", "Platinum"
    DIAMOND = "diamond", "Diamond"
    CHAMPION = "champion", "Champion"


# Minimum rank points required to enter each tier (GDD §15.3).
TIER_FLOORS: dict[str, int] = {
    RankedTier.BRONZE: 0,
    RankedTier.SILVER: 300,
    RankedTier.GOLD: 800,
    RankedTier.PLATINUM: 1_500,
    RankedTier.DIAMOND: 2_500,
    RankedTier.CHAMPION: 4_000,  # numeric floor; top-100 rule enforced by service
}

# Ordered list for promotion/demotion logic.
TIER_ORDER: list[str] = [
    RankedTier.BRONZE,
    RankedTier.SILVER,
    RankedTier.GOLD,
    RankedTier.PLATINUM,
    RankedTier.DIAMOND,
    RankedTier.CHAMPION,
]

# Extra Ryo awarded per ranked win by tier (GDD §15.3).
TIER_WIN_BONUS_RYO: dict[str, int] = {
    RankedTier.BRONZE: 0,
    RankedTier.SILVER: 50,
    RankedTier.GOLD: 100,
    RankedTier.PLATINUM: 150,
    RankedTier.DIAMOND: 200,
    RankedTier.CHAMPION: 300,
}

# Ranked point changes per outcome.
POINTS_WIN = 20
POINTS_LOSS = -10
STREAK_BONUS = 5        # added per win when win_streak >= 3
STREAK_THRESHOLD = 3    # minimum consecutive wins to earn streak bonus


class MatchmakingStatus(models.TextChoices):
    WAITING = "waiting", "Waiting"
    MATCHED = "matched", "Matched"
    CANCELLED = "cancelled", "Cancelled"


# ---------------------------------------------------------------------------
# RankedSeason
# ---------------------------------------------------------------------------

class RankedSeason(models.Model):
    """Represents a 90-day competitive season (GDD §15.3)."""

    number = models.PositiveIntegerField(unique=True, help_text="Season number (1, 2, 3, …)")
    name = models.CharField(max_length=120, help_text='e.g. "Season of Kizuna"')
    theme = models.CharField(max_length=120, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Only one season should be active at a time.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-number"]
        verbose_name = "ranked season"
        verbose_name_plural = "ranked seasons"

    def __str__(self) -> str:
        status = "ACTIVE" if self.is_active else "ended"
        return f"Season {self.number}: {self.name} ({status})"


# ---------------------------------------------------------------------------
# RankedProfile
# ---------------------------------------------------------------------------

class RankedProfile(models.Model):
    """
    Per-season ranked state for a player.

    Created lazily on first ranked queue join.  One profile per user per season;
    a new profile is created at the start of each season.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ranked_profiles",
        db_index=True,
    )
    season = models.ForeignKey(
        RankedSeason,
        on_delete=models.CASCADE,
        related_name="profiles",
        db_index=True,
    )
    rank_points = models.PositiveIntegerField(default=0)
    tier = models.TextField(choices=RankedTier.choices, default=RankedTier.BRONZE, db_index=True)
    sub_tier = models.PositiveSmallIntegerField(
        default=3,
        help_text="Sub-division within a tier: 1 = highest, 3 = lowest.",
    )
    win_streak = models.PositiveSmallIntegerField(default=0)
    season_wins = models.PositiveIntegerField(default=0)
    season_losses = models.PositiveIntegerField(default=0)
    reward_claimed = models.BooleanField(default=False)

    class Meta:
        unique_together = [("user", "season")]
        ordering = ["-rank_points"]
        verbose_name = "ranked profile"
        verbose_name_plural = "ranked profiles"

    def __str__(self) -> str:
        return (
            f"{self.user} — {self.get_tier_display()} {self.sub_tier} "
            f"({self.rank_points} pts) S{self.season.number}"
        )

    @property
    def tier_floor(self) -> int:
        """Minimum rank_points for the current tier (cannot drop below this)."""
        return TIER_FLOORS.get(self.tier, 0)


# ---------------------------------------------------------------------------
# MatchmakingEntry
# ---------------------------------------------------------------------------

class MatchmakingEntry(models.Model):
    """
    A player's position in the PvP matchmaking queue.

    At most one active (waiting) entry per user at any time.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="queue_entries",
        db_index=True,
    )
    rank_points = models.PositiveIntegerField(
        default=0,
        help_text="Snapshot of the player's rank_points at queue join time.",
    )
    status = models.TextField(
        choices=MatchmakingStatus.choices,
        default=MatchmakingStatus.WAITING,
        db_index=True,
    )
    battle = models.ForeignKey(
        "game.Battle",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="matchmaking_entries",
        help_text="Set when this entry has been matched into a battle.",
    )
    entered_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["entered_at"]
        verbose_name = "matchmaking entry"
        verbose_name_plural = "matchmaking entries"

    def __str__(self) -> str:
        return f"{self.user} in queue ({self.status}) — {self.rank_points} pts"
