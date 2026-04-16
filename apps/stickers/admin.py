"""Admin registrations for the stickers app."""
from django.contrib import admin

from .models import (
    Badge,
    OwnedBadge,
    RegionalAlbumPage,
    Sticker,
    StickerAlbum,
    StickerPack,
    TradeHistory,
    TradeOffer,
)


@admin.register(Sticker)
class StickerAdmin(admin.ModelAdmin):
    list_display = (
        "pk", "pokemon", "owner", "rarity", "variant",
        "is_trading", "is_favorite", "is_album_placed", "date_caught",
    )
    list_filter = ("rarity", "variant", "is_trading", "is_favorite", "is_album_placed")
    search_fields = ("pokemon__name", "owner__username")
    raw_id_fields = ("pokemon", "owner")


@admin.register(StickerAlbum)
class StickerAlbumAdmin(admin.ModelAdmin):
    list_display = ("owner", "created_at")
    filter_horizontal = ("showcase_stickers",)


@admin.register(StickerPack)
class StickerPackAdmin(admin.ModelAdmin):
    list_display = ("pk", "owner", "opened", "opened_at", "created_at")
    list_filter = ("opened",)
    raw_id_fields = ("owner",)


@admin.register(TradeOffer)
class TradeOfferAdmin(admin.ModelAdmin):
    list_display = ("pk", "offered_by", "offered_sticker", "status", "created_at", "resolved_at")
    list_filter = ("status",)
    raw_id_fields = ("offered_sticker", "requested_sticker", "offered_by", "offered_to")


@admin.register(TradeHistory)
class TradeHistoryAdmin(admin.ModelAdmin):
    list_display = ("pk", "from_user", "to_user", "sticker_given", "sticker_received", "completed_at")
    raw_id_fields = ("offer", "from_user", "to_user", "sticker_given", "sticker_received")


@admin.register(RegionalAlbumPage)
class RegionalAlbumPageAdmin(admin.ModelAdmin):
    list_display = ("pk", "user", "region", "rarity", "completed_at", "reward_claimed")
    list_filter = ("region", "rarity", "reward_claimed")
    search_fields = ("user__username",)
    raw_id_fields = ("user",)


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ("pk", "name", "pokemon", "tier", "effect_category")
    list_filter = ("tier", "effect_category")
    search_fields = ("name", "pokemon__name")
    raw_id_fields = ("pokemon",)


@admin.register(OwnedBadge)
class OwnedBadgeAdmin(admin.ModelAdmin):
    list_display = ("pk", "user", "badge", "equipped_slot", "crafted_at")
    list_filter = ("equipped_slot",)
    search_fields = ("user__username", "badge__name")
    raw_id_fields = ("user", "badge")
