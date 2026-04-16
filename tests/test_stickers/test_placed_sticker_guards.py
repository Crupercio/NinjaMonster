"""
Tests that placed stickers (is_album_placed=True) are blocked from
dismantle, convert, and trade operations.
"""
import pytest

from apps.stickers.models import StickerRarity, StickerVariant
from apps.stickers.services import StickerService, TradeService

from tests.framework.factories.pokemon_factory import PokemonFactory, PokemonTypeFactory
from tests.framework.factories.sticker_factory import StickerFactory
from tests.framework.factories.user_factory import UserFactory


pytestmark = pytest.mark.django_db


class TestPlacedStickerGuards:
    """Placed stickers must be blocked from all destructive operations."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.sticker_svc = StickerService()
        self.trade_svc = TradeService()
        self.ptype = PokemonTypeFactory(name="Normal")
        self.player = UserFactory()
        self.player.sticker_dust = 0
        self.player.save(update_fields=["sticker_dust"])
        self.pikachu = PokemonFactory(
            name="Pikachu", primary_type=self.ptype, pokedex_number=25
        )

    def test_dismantle_placed_sticker_raises(self):
        sticker = StickerFactory(
            pokemon=self.pikachu, owner=self.player,
            rarity=StickerRarity.COMMON, is_album_placed=True,
        )
        with pytest.raises(ValueError, match="placed in your album"):
            self.sticker_svc.dismantle_sticker(self.player, sticker.pk)

    def test_dismantle_non_placed_sticker_succeeds(self):
        sticker = StickerFactory(
            pokemon=self.pikachu, owner=self.player,
            rarity=StickerRarity.COMMON, is_album_placed=False,
        )
        dust = self.sticker_svc.dismantle_sticker(self.player, sticker.pk)
        assert dust > 0

    def test_convert_placed_sticker_raises(self):
        # placed guard fires before duplicate check
        placed = StickerFactory(
            pokemon=self.pikachu, owner=self.player,
            rarity=StickerRarity.COMMON, is_album_placed=True,
        )
        StickerFactory(pokemon=self.pikachu, owner=self.player, rarity=StickerRarity.COMMON)
        with pytest.raises(ValueError, match="placed in your album"):
            self.sticker_svc.convert_duplicate(self.player, placed)

    def test_convert_non_placed_duplicate_succeeds(self):
        free1 = StickerFactory(pokemon=self.pikachu, owner=self.player, rarity=StickerRarity.COMMON)
        StickerFactory(pokemon=self.pikachu, owner=self.player, rarity=StickerRarity.COMMON)
        dust = self.sticker_svc.convert_duplicate(self.player, free1)
        assert dust > 0

    def test_trade_placed_sticker_raises(self):
        # placed guard fires before last-copy check
        placed = StickerFactory(
            pokemon=self.pikachu, owner=self.player,
            rarity=StickerRarity.COMMON, is_album_placed=True,
        )
        StickerFactory(pokemon=self.pikachu, owner=self.player, rarity=StickerRarity.COMMON)
        with pytest.raises(ValueError, match="placed in your album"):
            self.trade_svc.create_trade_offer(sender=self.player, sticker=placed)

    def test_trade_non_placed_sticker_with_extra_copy_succeeds(self):
        free1 = StickerFactory(pokemon=self.pikachu, owner=self.player, rarity=StickerRarity.COMMON)
        StickerFactory(pokemon=self.pikachu, owner=self.player, rarity=StickerRarity.COMMON)
        offer = self.trade_svc.create_trade_offer(sender=self.player, sticker=free1)
        assert offer.pk is not None
