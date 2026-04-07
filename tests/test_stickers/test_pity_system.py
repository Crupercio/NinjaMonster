"""
P1-2 — Pity system tests.

Covers:
- Pity counter increments on each pack opened without that rarity
- Counter resets when the rarity is pulled naturally
- Guaranteed Holographic at pity_holographic == 10
- Guaranteed Full Art at pity_full_art == 50
- Guaranteed Secret Rare at pity_secret_rare == 200
- Higher rarity resets lower-threshold counters (e.g. Full Art resets pity_holographic)
- Pity override fires for the highest triggered threshold only
"""
import allure
import pytest

from apps.stickers.models import StickerPack, StickerRarity
from apps.stickers.services import (
    StickerService,
    _PITY_FULL_ART,
    _PITY_HOLOGRAPHIC,
    _PITY_SECRET_RARE,
)

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.pokemon_factory import PokemonFactory, PokemonTypeFactory
from tests.framework.factories.sticker_factory import StickerPackFactory
from tests.framework.factories.user_factory import UserFactory


def _pack_for(user) -> StickerPack:
    return StickerPackFactory(owner=user, opened=False)


def _ensure_pokemon(count: int = 5):
    """Ensure at least `count` Pokemon exist so open_pack() can sample."""
    normal = PokemonTypeFactory(name="Normal")
    existing = PokemonFactory._meta.model.objects.count()
    for i in range(max(0, count - existing)):
        PokemonFactory(name=f"TestMon{i}", primary_type=normal)


@allure.epic("Stickers")
@allure.feature("Pity System")
@pytest.mark.django_db
class TestPityCounterIncrement(BaseTest):

    @allure.story("Counter increments when no premium rarity pulled")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_holographic_counter_increments_without_pull(self, sticker_svc, player, monkeypatch):
        """Opening a pack that yields only Common/Uncommon/Rare increments pity_holographic."""
        _ensure_pokemon()
        # Force a rarity that does NOT trigger any reset
        monkeypatch.setattr(
            "apps.stickers.services._weighted_choice",
            lambda weights: StickerRarity.COMMON,
        )
        # Slot 4 uses _GUARANTEED_RARE_WEIGHTS — override to return RARE (not premium)
        original_choice = __import__("apps.stickers.services", fromlist=["_weighted_choice"])._weighted_choice  # noqa

        def _fixed_choice(weights):
            # Return RARE for slot 4 (guaranteed rare+), COMMON for everything else
            if StickerRarity.RARE in weights and weights.get(StickerRarity.RARE, 0) > 0:
                return StickerRarity.RARE
            return StickerRarity.COMMON

        monkeypatch.setattr("apps.stickers.services._weighted_choice", _fixed_choice)

        player.pity_holographic = 3
        player.save(update_fields=["pity_holographic"])

        pack = _pack_for(player)
        sticker_svc.open_pack(player, pack)

        player.refresh_from_db()
        assert player.pity_holographic == 4

    @allure.story("Counter resets when rarity pulled naturally")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_holographic_counter_resets_on_natural_pull(self, sticker_svc, player, monkeypatch):
        """Getting a Holographic naturally resets pity_holographic to 0."""
        _ensure_pokemon()

        def _fixed_choice(weights):
            if StickerRarity.HOLOGRAPHIC in weights:
                return StickerRarity.HOLOGRAPHIC
            return StickerRarity.COMMON

        monkeypatch.setattr("apps.stickers.services._weighted_choice", _fixed_choice)

        player.pity_holographic = 7
        player.save(update_fields=["pity_holographic"])

        pack = _pack_for(player)
        sticker_svc.open_pack(player, pack)

        player.refresh_from_db()
        assert player.pity_holographic == 0


@allure.epic("Stickers")
@allure.feature("Pity System")
@pytest.mark.django_db
class TestPityGuarantee(BaseTest):

    @allure.story("Holographic guaranteed at threshold (10)")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_holographic_guaranteed_at_threshold(self, sticker_svc, player, monkeypatch):
        """When pity_holographic >= 10, slot 4 must be exactly Holographic."""
        _ensure_pokemon()

        # Make all random rolls return COMMON so only pity override matters
        monkeypatch.setattr(
            "apps.stickers.services._weighted_choice",
            lambda weights: StickerRarity.COMMON,
        )

        player.pity_holographic = _PITY_HOLOGRAPHIC
        player.save(update_fields=["pity_holographic"])

        pack = _pack_for(player)
        stickers = sticker_svc.open_pack(player, pack)

        rarities = [s.rarity for s in stickers]
        assert StickerRarity.HOLOGRAPHIC in rarities, f"Expected Holographic in {rarities}"

        player.refresh_from_db()
        assert player.pity_holographic == 0

    @allure.story("Full Art guaranteed at threshold (50)")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_full_art_guaranteed_at_threshold(self, sticker_svc, player, monkeypatch):
        """When pity_full_art >= 50, slot 4 must be exactly Full Art."""
        _ensure_pokemon()

        monkeypatch.setattr(
            "apps.stickers.services._weighted_choice",
            lambda weights: StickerRarity.COMMON,
        )

        player.pity_full_art = _PITY_FULL_ART
        player.save(update_fields=["pity_full_art"])

        pack = _pack_for(player)
        stickers = sticker_svc.open_pack(player, pack)

        rarities = [s.rarity for s in stickers]
        assert StickerRarity.FULL_ART in rarities, f"Expected Full Art in {rarities}"

        player.refresh_from_db()
        assert player.pity_full_art == 0

    @allure.story("Secret Rare guaranteed at threshold (200)")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_secret_rare_guaranteed_at_threshold(self, sticker_svc, player, monkeypatch):
        """When pity_secret_rare >= 200, slot 4 must be exactly Secret Rare."""
        _ensure_pokemon()

        monkeypatch.setattr(
            "apps.stickers.services._weighted_choice",
            lambda weights: StickerRarity.COMMON,
        )

        player.pity_secret_rare = _PITY_SECRET_RARE
        player.save(update_fields=["pity_secret_rare"])

        pack = _pack_for(player)
        stickers = sticker_svc.open_pack(player, pack)

        rarities = [s.rarity for s in stickers]
        assert StickerRarity.SECRET_RARE in rarities, f"Expected Secret Rare in {rarities}"

        player.refresh_from_db()
        assert player.pity_secret_rare == 0

    @allure.story("Secret Rare threshold takes priority over lower thresholds")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_secret_rare_takes_priority_when_multiple_thresholds_reached(self, sticker_svc, player, monkeypatch):
        """When multiple pity thresholds are met, the highest rarity wins."""
        _ensure_pokemon()

        monkeypatch.setattr(
            "apps.stickers.services._weighted_choice",
            lambda weights: StickerRarity.COMMON,
        )

        player.pity_holographic = _PITY_HOLOGRAPHIC
        player.pity_full_art = _PITY_FULL_ART
        player.pity_secret_rare = _PITY_SECRET_RARE
        player.save(update_fields=["pity_holographic", "pity_full_art", "pity_secret_rare"])

        pack = _pack_for(player)
        stickers = sticker_svc.open_pack(player, pack)

        rarities = [s.rarity for s in stickers]
        assert StickerRarity.SECRET_RARE in rarities, f"Expected Secret Rare in {rarities}"

        player.refresh_from_db()
        # All three counters reset because Secret Rare satisfies all lower thresholds
        assert player.pity_secret_rare == 0
        assert player.pity_full_art == 0
        assert player.pity_holographic == 0

    @allure.story("Full Art pull resets Holographic counter")
    @allure.severity(allure.severity_level.NORMAL)
    def test_full_art_resets_holographic_counter(self, sticker_svc, player, monkeypatch):
        """Pulling Full Art satisfies the Holographic threshold too."""
        _ensure_pokemon()

        def _fixed_choice(weights):
            if StickerRarity.FULL_ART in weights:
                return StickerRarity.FULL_ART
            return StickerRarity.COMMON

        monkeypatch.setattr("apps.stickers.services._weighted_choice", _fixed_choice)

        player.pity_holographic = 5
        player.pity_full_art = 3
        player.save(update_fields=["pity_holographic", "pity_full_art"])

        pack = _pack_for(player)
        sticker_svc.open_pack(player, pack)

        player.refresh_from_db()
        assert player.pity_holographic == 0
        assert player.pity_full_art == 0
        # Secret rare counter should still increment (no Secret Rare pulled)
        assert player.pity_secret_rare == 1
