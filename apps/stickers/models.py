"""
Sticker collectible system models.

Inspired by Pokemon TCG Pocket, Marvel Snap, Disney Lorcana, and One Piece TCG.
7 rarity tiers × 6 art variants per Pokemon.
"""
import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

logger = logging.getLogger(__name__)


class StickerRarity(models.TextChoices):
    COMMON = "common", "Common"
    UNCOMMON = "uncommon", "Uncommon"
    RARE = "rare", "Rare"
    EPIC = "epic", "Epic"
    HOLOGRAPHIC = "holographic", "Holographic"
    FULL_ART = "full_art", "Full Art"
    SECRET_RARE = "secret_rare", "Secret Rare"


class StickerVariant(models.TextChoices):
    BASE = "base", "Base"
    SHINY = "shiny", "Shiny"
    BATTLE_SCENE = "battle_scene", "Battle Scene"
    CHIBI = "chibi", "Chibi"
    MANGA_PANEL = "manga_panel", "Manga Panel"
    FULL_ILLUSTRATION = "full_illustration", "Full Illustration"
    ANIME = "anime", "Anime"


# Craft cost in sticker dust per rarity tier
CRAFT_COSTS: dict[str, int] = {
    StickerRarity.COMMON: 10,
    StickerRarity.UNCOMMON: 25,
    StickerRarity.RARE: 75,
    StickerRarity.EPIC: 150,
    StickerRarity.HOLOGRAPHIC: 300,
    StickerRarity.FULL_ART: 500,
    StickerRarity.SECRET_RARE: 1000,
}

# Dust gained when converting a duplicate
DUST_VALUES: dict[str, int] = {
    StickerRarity.COMMON: 5,
    StickerRarity.UNCOMMON: 10,
    StickerRarity.RARE: 25,
    StickerRarity.EPIC: 50,
    StickerRarity.HOLOGRAPHIC: 100,
    StickerRarity.FULL_ART: 200,
    StickerRarity.SECRET_RARE: 400,
}

# Dust gained when dismantling (any copy, not just duplicates)
DISMANTLE_VALUES: dict[str, int] = {
    StickerRarity.COMMON: 5,
    StickerRarity.UNCOMMON: 10,
    StickerRarity.RARE: 25,
    StickerRarity.EPIC: 60,
    StickerRarity.HOLOGRAPHIC: 120,
    StickerRarity.FULL_ART: 200,
    StickerRarity.SECRET_RARE: 300,
}


class Sticker(models.Model):
    """
    A collectible sticker owned by a player.

    Each sticker is a specific (Pokemon, rarity, variant) combination.
    Multiple copies of the same combination can exist — duplicates can be
    converted to sticker dust.
    """

    pokemon = models.ForeignKey(
        "pokemon.Pokemon",
        on_delete=models.CASCADE,
        related_name="stickers",
        db_index=True,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="stickers",
        db_index=True,
    )
    rarity = models.TextField(choices=StickerRarity.choices, default=StickerRarity.COMMON, db_index=True)
    variant = models.TextField(choices=StickerVariant.choices, default=StickerVariant.BASE, db_index=True)
    is_trading = models.BooleanField(default=False, db_index=True)
    is_favorite = models.BooleanField(default=False)
    is_showcase = models.BooleanField(
        default=False,
        help_text="Pinned to the player's profile showcase (max 6).",
    )

    # Source tracking (for analytics / unlock criteria)
    awarded_from = models.TextField(
        blank=True,
        default="",
        help_text="How this sticker was obtained: catch, level_up, combo_win, pack, craft",
    )
    date_caught = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_caught"]
        verbose_name = "sticker"
        verbose_name_plural = "stickers"
        indexes = [
            models.Index(fields=["owner", "pokemon", "rarity", "variant"]),
        ]

    def clean(self) -> None:
        if self.variant == StickerVariant.ANIME and self.rarity != StickerRarity.SECRET_RARE:
            raise ValidationError(
                {"variant": "Anime variant is only available on Secret Rare stickers."}
            )

    def __str__(self) -> str:
        return f"{self.pokemon.name} [{self.rarity}] {self.variant} (owned by {self.owner})"


class StickerAlbum(models.Model):
    """
    Album metadata for a user's sticker collection.

    The actual stickers are queried via Sticker.objects.filter(owner=user).
    This model stores album-level settings like showcase slots.
    """

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sticker_album",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Showcase: up to 6 sticker PKs pinned to the profile
    showcase_stickers = models.ManyToManyField(
        Sticker,
        related_name="showcased_in_albums",
        blank=True,
    )

    class Meta:
        verbose_name = "sticker album"
        verbose_name_plural = "sticker albums"

    def __str__(self) -> str:
        return f"{self.owner}'s sticker album"


class StickerPack(models.Model):
    """
    A pack of 5 stickers earned every 10 battle wins.

    Inspired by Pokemon TCG Pocket pack-opening mechanics.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sticker_packs",
        db_index=True,
    )
    opened = models.BooleanField(default=False)
    opened_at = models.DateTimeField(null=True, blank=True)
    stickers = models.ManyToManyField(
        Sticker,
        related_name="from_pack",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "sticker pack"
        verbose_name_plural = "sticker packs"

    def __str__(self) -> str:
        state = "opened" if self.opened else "unopened"
        return f"{self.owner}'s sticker pack ({state})"


class TradeOffer(models.Model):
    """
    A peer-to-peer sticker trade offer.

    Inspired by Pokemon TCG Pocket trading with atomic ownership swap.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    offered_sticker = models.ForeignKey(
        Sticker,
        on_delete=models.CASCADE,
        related_name="offered_in_trades",
        db_index=True,
    )
    # What the offerer is looking for (either a specific sticker or any of a Pokemon)
    requested_sticker = models.ForeignKey(
        Sticker,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="requested_in_trades",
        db_index=True,
    )
    requested_pokemon = models.ForeignKey(
        "pokemon.Pokemon",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="requested_in_trades",
        db_index=True,
    )
    looking_for_note = models.TextField(
        blank=True,
        default="",
        help_text="Free-text note describing what the offerer is looking for.",
    )
    offered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="trade_offers_sent",
        db_index=True,
    )
    offered_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="trade_offers_received",
        db_index=True,
    )
    status = models.TextField(choices=Status.choices, default=Status.PENDING, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "trade offer"
        verbose_name_plural = "trade offers"

    def __str__(self) -> str:
        return f"Trade #{self.pk}: {self.offered_by} offers {self.offered_sticker} ({self.status})"


class AlbumRewardType(models.TextChoices):
    POKEMON_COMPLETE = "pokemon_complete", "Pokemon Collection Complete"
    FULL_DEX = "full_dex", "Full Pokedex Complete"


class AlbumCompletionReward(models.Model):
    """
    Records a completion reward that was automatically granted to a player.

    Prevents duplicate awards: unique_together on (user, reward_type, pokemon).
    pokemon is NULL for the FULL_DEX reward.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="album_completion_rewards",
        db_index=True,
    )
    reward_type = models.TextField(choices=AlbumRewardType.choices, db_index=True)
    pokemon = models.ForeignKey(
        "pokemon.Pokemon",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="completion_rewards",
        db_index=True,
    )
    dust_awarded = models.PositiveIntegerField(default=0)
    ryo_awarded = models.PositiveIntegerField(default=0)
    packs_awarded = models.PositiveIntegerField(default=0)
    claimed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "reward_type", "pokemon")]
        ordering = ["-claimed_at"]
        verbose_name = "album completion reward"
        verbose_name_plural = "album completion rewards"

    def __str__(self) -> str:
        label = self.pokemon.name if self.pokemon else "Full Dex"
        return f"{self.user} — {label} ({self.reward_type})"


class TradeHistory(models.Model):
    """Immutable record of a completed trade."""

    offer = models.OneToOneField(
        TradeOffer,
        on_delete=models.PROTECT,
        related_name="history",
    )
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="trades_initiated",
        db_index=True,
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="trades_received",
        db_index=True,
    )
    sticker_given = models.ForeignKey(
        Sticker,
        on_delete=models.PROTECT,
        related_name="given_in_trade_history",
        db_index=True,
    )
    sticker_received = models.ForeignKey(
        Sticker,
        on_delete=models.PROTECT,
        related_name="received_in_trade_history",
        db_index=True,
    )
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-completed_at"]
        verbose_name = "trade history"
        verbose_name_plural = "trade histories"

    def __str__(self) -> str:
        return f"Trade #{self.offer_id} completed at {self.completed_at}"
