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
    is_album_placed = models.BooleanField(
        default=False,
        db_index=True,
        help_text="True when this sticker is placed in a regional album page (soul-bound).",
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


class PackType(models.TextChoices):
    STANDARD = "standard", "Standard Pack"
    BUNDLE = "bundle", "Bundle Pack"
    # Generation-specific packs — pool limited to that gen's Pokémon
    GEN1 = "gen1", "Kanto Pack (Gen 1)"
    GEN2 = "gen2", "Johto Pack (Gen 2)"
    GEN3 = "gen3", "Hoenn Pack (Gen 3)"
    GEN4 = "gen4", "Sinnoh Pack (Gen 4)"
    GEN5 = "gen5", "Unova Pack (Gen 5)"
    GEN6 = "gen6", "Kalos Pack (Gen 6)"
    GEN7 = "gen7", "Alola Pack (Gen 7)"
    GEN8 = "gen8", "Galar Pack (Gen 8)"


# Maps gen pack type values to generation numbers for pool filtering
GEN_PACK_GEN_NUMBER: dict[str, int] = {
    "gen1": 1, "gen2": 2, "gen3": 3, "gen4": 4,
    "gen5": 5, "gen6": 6, "gen7": 7, "gen8": 8,
}


class StickerPack(models.Model):
    """
    A pack of stickers.

    Standard: 5 stickers with normal rarity odds.
    Bundle:   10 stickers with improved rarity odds (weekly login reward).
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sticker_packs",
        db_index=True,
    )
    pack_type = models.TextField(
        choices=PackType.choices,
        default=PackType.STANDARD,
        db_index=True,
        help_text="standard = 5 stickers; bundle = 10 stickers with improved rarity odds.",
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
        label = PackType(self.pack_type).label if self.pack_type in PackType.values else self.pack_type
        return f"{self.owner}'s {label} ({state})"

    @property
    def is_bundle(self) -> bool:
        return self.pack_type == PackType.BUNDLE

    @property
    def is_gen_pack(self) -> bool:
        return self.pack_type in GEN_PACK_GEN_NUMBER


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


# ---------------------------------------------------------------------------
# Album Page — groups Pokémon into scene-based pages (15 per page)
# ---------------------------------------------------------------------------

# Kanto Gen 1 page definitions: (page_number, dex_start, dex_end, location_name, bg_image_name)
KANTO_PAGES: list[tuple[int, int, int, str, str]] = [
    (1,  1,   15,  "Pallet Town at Dusk",         "kanto_page_1.jpg"),
    (2,  16,  30,  "Viridian Forest",              "kanto_page_2.jpg"),
    (3,  31,  45,  "Mt. Moon Caverns",             "kanto_page_3.jpg"),
    (4,  46,  60,  "Cerulean Cape at Dawn",        "kanto_page_4.jpg"),
    (5,  61,  75,  "Vermillion Harbor",            "kanto_page_5.jpg"),
    (6,  76,  90,  "Lavender Ghost Tower",         "kanto_page_6.jpg"),
    (7,  91,  105, "Celadon Rooftop Garden",       "kanto_page_7.jpg"),
    (8,  106, 120, "Fuchsia Safari Zone",          "kanto_page_8.jpg"),
    (9,  121, 135, "Cinnabar Volcanic Coast",      "kanto_page_9.jpg"),
    (10, 136, 151, "Cerulean Cave — Legendary",    "kanto_page_10.jpg"),
]


class AlbumPage(models.Model):
    """
    A named scene page grouping ~15 Pokémon for display in the scene album.

    Each region has multiple pages (e.g. Kanto has 10, pages of 15 Pokémon each).
    The page defines which Pokémon appear in the scene via dex_start/dex_end.
    bg_image_name is the filename under static/img/albums/ — falls back to a
    CSS gradient class when the file doesn't exist yet.
    """

    region = models.TextField(db_index=True)
    page_number = models.PositiveSmallIntegerField()
    dex_start = models.PositiveIntegerField()
    dex_end = models.PositiveIntegerField()
    location_name = models.TextField()
    bg_image_name = models.TextField(
        blank=True,
        default="",
        help_text="Filename under static/img/albums/. Empty = use CSS gradient fallback.",
    )

    class Meta:
        unique_together = [("region", "page_number")]
        ordering = ["region", "page_number"]
        verbose_name = "album page"
        verbose_name_plural = "album pages"

    def __str__(self) -> str:
        return f"{self.region.title()} p{self.page_number}: {self.location_name}"

    @property
    def bg_css_class(self) -> str:
        """CSS gradient fallback class used until the real image is provided."""
        return f"apbg-{self.region}-{self.page_number}"

    @property
    def bg_style(self) -> str:
        """
        Inline style string for the scene background.
        Uses the real image if available, otherwise the CSS gradient class handles it.
        """
        if self.bg_image_name:
            return f"background-image:url('/static/img/albums/{self.bg_image_name}');"
        return ""


# ---------------------------------------------------------------------------
# Regional Album system
# ---------------------------------------------------------------------------

# Pokedex number ranges per region — designed to expand to all generations.
REGION_RANGES: dict[str, tuple[int, int]] = {
    "kanto": (1, 151),
    "johto": (152, 251),
    "hoenn": (252, 386),
    "sinnoh": (387, 493),
    "unova": (494, 649),
    "kalos": (650, 721),
    "alola": (722, 809),
    "galar": (810, 905),
    "paldea": (906, 99999),
}

REGION_LABELS: dict[str, str] = {
    "kanto": "Kanto",
    "johto": "Johto",
    "hoenn": "Hoenn",
    "sinnoh": "Sinnoh",
    "unova": "Unova",
    "kalos": "Kalos",
    "alola": "Alola",
    "galar": "Galar",
    "paldea": "Paldea",
}

# Rewards when a regional album page is completed (all Pokémon in region at that rarity placed)
PAGE_REWARDS: dict[str, dict[str, int]] = {
    StickerRarity.COMMON:      {"dust": 200,  "ryo": 0,     "packs": 0},
    StickerRarity.UNCOMMON:    {"dust": 400,  "ryo": 0,     "packs": 0},
    StickerRarity.RARE:        {"dust": 150,  "ryo": 0,     "packs": 1},
    StickerRarity.EPIC:        {"dust": 300,  "ryo": 0,     "packs": 2},
    StickerRarity.HOLOGRAPHIC: {"dust": 600,  "ryo": 1000,  "packs": 3},
    StickerRarity.FULL_ART:    {"dust": 1000, "ryo": 2500,  "packs": 5},
    StickerRarity.SECRET_RARE: {"dust": 2000, "ryo": 5000,  "packs": 10},
}


class RegionalAlbumPage(models.Model):
    """
    Tracks a player's completion of one (region × rarity) album page.

    A page is complete when the player has placed one sticker for every
    Pokémon in that region at that rarity tier.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="regional_album_pages",
        db_index=True,
    )
    region = models.TextField(db_index=True)
    rarity = models.TextField(choices=StickerRarity.choices, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    reward_claimed = models.BooleanField(default=False)

    class Meta:
        unique_together = [("user", "region", "rarity")]
        verbose_name = "regional album page"
        verbose_name_plural = "regional album pages"

    def __str__(self) -> str:
        return f"{self.user} — {self.region} [{self.rarity}]"


# ---------------------------------------------------------------------------
# Badge system (Phase 3 — models created now, battle logic wired later)
# ---------------------------------------------------------------------------

class BadgeTier(models.TextChoices):
    BRONZE = "bronze", "Bronze"
    SILVER = "silver", "Silver"
    GOLD = "gold", "Gold"
    HOLOGRAPHIC = "holographic", "Holographic"
    PRISMATIC = "prismatic", "Prismatic"


# How many stickers of the required rarity are consumed to craft each badge tier
BADGE_CRAFT_REQUIREMENTS: dict[str, dict[str, int | str]] = {
    BadgeTier.BRONZE:      {"rarity": StickerRarity.COMMON,      "copies": 3, "dust": 50},
    BadgeTier.SILVER:      {"rarity": StickerRarity.RARE,        "copies": 2, "dust": 150},
    BadgeTier.GOLD:        {"rarity": StickerRarity.EPIC,        "copies": 2, "dust": 300},
    BadgeTier.HOLOGRAPHIC: {"rarity": StickerRarity.HOLOGRAPHIC, "copies": 1, "dust": 600},
    BadgeTier.PRISMATIC:   {"rarity": StickerRarity.SECRET_RARE, "copies": 1, "dust": 1000},
}


class Badge(models.Model):
    """
    A battle-passive badge tied to a specific Pokémon.

    One badge definition exists per (pokemon, tier) — different tiers yield
    progressively stronger effects of the same category.
    Badges are soul-bound to the player who crafts them.
    """

    pokemon = models.ForeignKey(
        "pokemon.Pokemon",
        on_delete=models.CASCADE,
        related_name="badges",
        db_index=True,
    )
    tier = models.TextField(choices=BadgeTier.choices, db_index=True)
    effect_category = models.TextField(
        blank=True,
        default="",
        help_text=(
            "trigger_amplifier | chakra_engine | cooldown_reducer | "
            "threshold_heal | combo_extender | type_burst | status_chain"
        ),
    )
    effect_params = models.JSONField(
        default=dict,
        help_text="Serialised effect parameters (value, condition, target, etc.)",
    )
    name = models.TextField()
    description = models.TextField(blank=True, default="")

    class Meta:
        unique_together = [("pokemon", "tier")]
        verbose_name = "badge"
        verbose_name_plural = "badges"

    def __str__(self) -> str:
        return f"{self.name} ({self.tier})"


class OwnedBadge(models.Model):
    """
    A badge owned by a player.

    Soul-bound: cannot be traded or transferred.
    Up to 3 badges can be equipped simultaneously (equipped_slot 1/2/3).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_badges",
        db_index=True,
    )
    badge = models.ForeignKey(
        Badge,
        on_delete=models.CASCADE,
        related_name="owners",
        db_index=True,
    )
    equipped_slot = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Active badge slot (1, 2, or 3). Null means unequipped.",
    )
    crafted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "badge")]
        verbose_name = "owned badge"
        verbose_name_plural = "owned badges"

    def __str__(self) -> str:
        slot = f"slot {self.equipped_slot}" if self.equipped_slot else "unequipped"
        return f"{self.user} — {self.badge.name} ({slot})"
