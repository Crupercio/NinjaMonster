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
