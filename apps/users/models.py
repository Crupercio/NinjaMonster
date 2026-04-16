"""Custom User model for the Pokemon Battle game."""
import logging

from django.contrib.auth.models import AbstractUser
from django.db import models

from .managers import UserManager

logger = logging.getLogger(__name__)


class User(AbstractUser):
    """
    Custom User model.

    Uses email as the unique identifier alongside username.
    All character fields use text (not varchar) per project conventions.
    """

    email = models.EmailField(unique=True)
    display_name = models.TextField(blank=True, default="")
    avatar_url = models.TextField(blank=True, default="")
    sticker_dust = models.PositiveIntegerField(default=0)
    ryo = models.PositiveIntegerField(default=0)
    last_daily_claim = models.DateField(null=True, blank=True)

    # Battle statistics (denormalised for quick profile display)
    battles_won = models.PositiveIntegerField(default=0)
    battles_played = models.PositiveIntegerField(default=0)
    longest_combo_chain = models.PositiveIntegerField(default=0)

    # Sticker pack pity counters — number of packs opened without that rarity tier.
    # Guaranteed pull triggers at: Holographic=10, Full Art=50, Secret Rare=200.
    # Resets to 0 when that rarity (or higher) is pulled.
    pity_holographic = models.PositiveIntegerField(default=0)
    pity_full_art = models.PositiveIntegerField(default=0)
    pity_secret_rare = models.PositiveIntegerField(default=0)

    # Tutorial progress
    tutorial_complete = models.BooleanField(default=False)
    tutorial_starter = models.CharField(max_length=50, blank=True, null=True)

    # ── Bonding candies (expedition consumables) ─────────────────────────────
    # Used during expeditions to boost the bond rate with wild Pokémon.
    # trail_mix: +10% | sweet_berry: +25% | golden_apple: +50%
    candy_trail_mix = models.PositiveIntegerField(default=0)
    candy_sweet_berry = models.PositiveIntegerField(default=0)
    candy_golden_apple = models.PositiveIntegerField(default=0)

    # ── Trainer level (separate from Pokémon levels) ─────────────────────────
    # XP sources: completing daily quests, placing stickers on album pages.
    # Daily XP is capped at TRAINER_DAILY_XP_CAP to prevent runaway leveling.
    trainer_level = models.PositiveIntegerField(default=1)
    trainer_xp = models.PositiveIntegerField(default=0)
    trainer_xp_today = models.PositiveIntegerField(default=0)
    trainer_xp_date = models.DateField(null=True, blank=True)

    # ── Achievement badge tracking (GDD §14.4) ────────────────────────────────
    perfect_victories = models.PositiveIntegerField(default=0)
    hard_ai_wins = models.PositiveIntegerField(default=0)
    daily_claim_streak = models.PositiveIntegerField(default=0)
    max_daily_claim_streak = models.PositiveIntegerField(default=0)
    trades_completed = models.PositiveIntegerField(default=0)

    objects: UserManager = UserManager()  # type: ignore[assignment]

    REQUIRED_FIELDS = ["email"]

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self) -> str:
        return self.display_name or self.username

    @property
    def win_rate(self) -> float:
        """Return win rate as a percentage (0.0–100.0)."""
        if self.battles_played == 0:
            return 0.0
        return round(self.battles_won / self.battles_played * 100, 1)

    @property
    def trainer_xp_to_next_level(self) -> int:
        """XP needed to reach the next trainer level. Scales with current level."""
        lv = self.trainer_level
        if lv <= 10:
            return 100 + lv * 50          # 150–600 XP  (fast early)
        if lv <= 20:
            return 700 + (lv - 10) * 80   # 780–1,500 XP
        return 1600 + (lv - 20) * 150     # slow and steady after 20

    @property
    def trainer_xp_percent(self) -> int:
        """Progress toward next level as integer 0–100."""
        nxt = self.trainer_xp_to_next_level
        if nxt == 0:
            return 100
        return min(100, int(self.trainer_xp / nxt * 100))

    @property
    def max_daily_expeditions(self) -> int:
        """Expedition attempts unlocked per day based on trainer level."""
        return min(6, 2 + self.trainer_level // 5)
