"""factory_boy factories for Sticker, StickerAlbum, StickerPack, TradeOffer."""
import factory

from apps.stickers.models import (
    Sticker,
    StickerAlbum,
    StickerPack,
    StickerRarity,
    StickerVariant,
    TradeOffer,
)

from .pokemon_factory import PokemonFactory
from .user_factory import UserFactory


class StickerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Sticker

    pokemon = factory.SubFactory(PokemonFactory)
    owner = factory.SubFactory(UserFactory)
    rarity = StickerRarity.COMMON
    variant = StickerVariant.BASE
    is_trading = False
    is_favorite = False
    is_showcase = False
    awarded_from = "catch"

    class Params:
        rare = factory.Trait(rarity=StickerRarity.RARE)
        epic = factory.Trait(rarity=StickerRarity.EPIC)
        holographic = factory.Trait(rarity=StickerRarity.HOLOGRAPHIC)
        full_art = factory.Trait(rarity=StickerRarity.FULL_ART)
        secret_rare = factory.Trait(rarity=StickerRarity.SECRET_RARE)
        shiny = factory.Trait(variant=StickerVariant.SHINY)


class StickerAlbumFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = StickerAlbum
        django_get_or_create = ("owner",)

    owner = factory.SubFactory(UserFactory)


class StickerPackFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = StickerPack

    owner = factory.SubFactory(UserFactory)
    opened = False
    opened_at = None


class TradeOfferFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TradeOffer

    offered_sticker = factory.SubFactory(StickerFactory)
    offered_by = factory.SelfAttribute("offered_sticker.owner")
    status = TradeOffer.Status.PENDING
    offered_to = None
    requested_sticker = None
    requested_pokemon = None
    looking_for_note = ""
