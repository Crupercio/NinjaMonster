"""
Tests for AlbumService: placement, removal, completion detection, and reward claiming.
"""
import pytest

from apps.stickers.models import RegionalAlbumPage, StickerRarity
from apps.stickers.services import AlbumService, _COMPLETION_VARIANTS

from tests.framework.factories.pokemon_factory import PokemonFactory, PokemonTypeFactory
from tests.framework.factories.sticker_factory import StickerFactory
from tests.framework.factories.user_factory import UserFactory


pytestmark = pytest.mark.django_db


class TestAlbumServicePlacement:
    """Tests for place_sticker and remove_sticker."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.svc = AlbumService()
        self.ptype = PokemonTypeFactory(name="Fire")
        # Kanto Pokémon (dex 1–151)
        self.player = UserFactory()
        self.player.sticker_dust = 0
        self.player.ryo = 0
        self.player.save(update_fields=["sticker_dust", "ryo"])
        self.pikachu = PokemonFactory(
            name="Pikachu", primary_type=self.ptype, pokedex_number=25
        )

    def test_place_sticker_success(self):
        # Can place even if it's your only copy — it becomes soul-bound
        sticker = StickerFactory(pokemon=self.pikachu, owner=self.player, rarity=StickerRarity.COMMON)

        result = self.svc.place_sticker(self.player, sticker.pk)

        sticker.refresh_from_db()
        assert sticker.is_album_placed is True
        assert result.pk == sticker.pk

    def test_place_only_copy_succeeds(self):
        """Placing your only copy is allowed — it becomes soul-bound (protected)."""
        sticker = StickerFactory(pokemon=self.pikachu, owner=self.player, rarity=StickerRarity.COMMON)
        self.svc.place_sticker(self.player, sticker.pk)
        sticker.refresh_from_db()
        assert sticker.is_album_placed is True

    def test_place_sticker_wrong_owner_raises(self):
        other = UserFactory()
        sticker = StickerFactory(pokemon=self.pikachu, owner=other, rarity=StickerRarity.COMMON)
        StickerFactory(pokemon=self.pikachu, owner=other, rarity=StickerRarity.COMMON)

        with pytest.raises(ValueError, match="not found"):
            self.svc.place_sticker(self.player, sticker.pk)

    def test_place_sticker_already_placed_raises(self):
        # s1 already placed; s2 is same (pokemon, rarity, variant) → slot is taken
        from apps.stickers.models import StickerVariant
        StickerFactory(
            pokemon=self.pikachu, owner=self.player,
            rarity=StickerRarity.COMMON, variant=StickerVariant.BASE,
            is_album_placed=True,
        )
        duplicate = StickerFactory(
            pokemon=self.pikachu, owner=self.player,
            rarity=StickerRarity.COMMON, variant=StickerVariant.BASE,
        )

        with pytest.raises(ValueError, match="already have a"):
            self.svc.place_sticker(self.player, duplicate.pk)

    def test_place_sticker_in_trade_raises(self):
        sticker = StickerFactory(
            pokemon=self.pikachu, owner=self.player,
            rarity=StickerRarity.COMMON, is_trading=True,
        )
        StickerFactory(pokemon=self.pikachu, owner=self.player, rarity=StickerRarity.COMMON)

        with pytest.raises(ValueError, match="currently in a trade"):
            self.svc.place_sticker(self.player, sticker.pk)

    def test_place_sticker_no_pokedex_number_raises(self):
        headless = PokemonFactory(name="Mystery", primary_type=self.ptype, pokedex_number=None)
        s1 = StickerFactory(pokemon=headless, owner=self.player, rarity=StickerRarity.COMMON)
        StickerFactory(pokemon=headless, owner=self.player, rarity=StickerRarity.COMMON)

        with pytest.raises(ValueError, match="valid Pokédex number"):
            self.svc.place_sticker(self.player, s1.pk)

    def test_remove_sticker_success(self):
        sticker = StickerFactory(
            pokemon=self.pikachu, owner=self.player,
            rarity=StickerRarity.COMMON, is_album_placed=True,
        )
        result = self.svc.remove_sticker(self.player, sticker.pk)

        sticker.refresh_from_db()
        assert sticker.is_album_placed is False
        assert result.pk == sticker.pk

    def test_remove_sticker_not_placed_raises(self):
        sticker = StickerFactory(pokemon=self.pikachu, owner=self.player, rarity=StickerRarity.COMMON)

        with pytest.raises(ValueError, match="not placed"):
            self.svc.remove_sticker(self.player, sticker.pk)

    def test_remove_sticker_clears_page_completion(self):
        from datetime import datetime, timezone
        # Create a page marked complete, then remove a placed sticker — completed_at clears
        page = RegionalAlbumPage.objects.create(
            user=self.player, region="kanto", rarity=StickerRarity.COMMON,
            completed_at=datetime.now(tz=timezone.utc), reward_claimed=False,
        )
        sticker = StickerFactory(
            pokemon=self.pikachu, owner=self.player,
            rarity=StickerRarity.COMMON, is_album_placed=True,
        )
        self.svc.remove_sticker(self.player, sticker.pk)

        page.refresh_from_db()
        assert page.completed_at is None


class TestAlbumServicePageDetail:
    """Tests for get_page_detail."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.svc = AlbumService()
        self.ptype = PokemonTypeFactory(name="Water")
        self.player = UserFactory()
        self.squirtle = PokemonFactory(
            name="Squirtle", primary_type=self.ptype, pokedex_number=7
        )

    def test_page_detail_returns_correct_structure(self):
        StickerFactory(
            pokemon=self.squirtle, owner=self.player,
            rarity=StickerRarity.RARE, is_album_placed=False
        )
        data = self.svc.get_page_detail(self.player, "kanto", StickerRarity.RARE)

        assert data["region"] == "kanto"
        assert data["rarity"] == StickerRarity.RARE
        assert data["total_count"] >= 1
        slot = next(s for s in data["slots"] if s["pokemon"].pk == self.squirtle.pk)
        assert slot["placed_sticker"] is None
        assert len(slot["available_stickers"]) == 1

    def test_page_detail_invalid_region_raises(self):
        with pytest.raises(ValueError, match="Unknown region"):
            self.svc.get_page_detail(self.player, "narnia", StickerRarity.COMMON)

    def test_page_detail_invalid_rarity_raises(self):
        with pytest.raises(ValueError, match="Unknown rarity"):
            self.svc.get_page_detail(self.player, "kanto", "legendary")

    def test_page_not_complete_when_missing_slots(self):
        data = self.svc.get_page_detail(self.player, "kanto", StickerRarity.EPIC)
        assert data["page_complete"] is False

    def test_placement_slots_expose_compact_metadata(self):
        StickerFactory(
            pokemon=self.squirtle,
            owner=self.player,
            rarity=StickerRarity.RARE,
            variant="base",
            is_album_placed=False,
        )

        data = self.svc.get_placement_slots(self.player, "kanto", StickerRarity.RARE)

        slot = next(
            entry for entry in data["placement_slots"]
            if entry["pokemon"].pk == self.squirtle.pk and entry["variant"] == "base"
        )
        assert slot["is_placeable"] is True
        assert slot["first_available_sticker_id"] is not None
        assert slot["regional_page_number"] == 1
        assert data["slot_totals"]["placeable"] >= 1

    def test_place_many_places_each_valid_sticker_once(self):
        base = StickerFactory(
            pokemon=self.squirtle,
            owner=self.player,
            rarity=StickerRarity.RARE,
            variant="base",
        )
        shiny = StickerFactory(
            pokemon=self.squirtle,
            owner=self.player,
            rarity=StickerRarity.RARE,
            variant="shiny",
        )

        placed_count = self.svc.place_many(self.player, [base.pk, shiny.pk, 999999])

        assert placed_count == 2
        base.refresh_from_db()
        shiny.refresh_from_db()
        assert base.is_album_placed is True
        assert shiny.is_album_placed is True


class TestAlbumServiceCompletion:
    """Tests for page completion detection and reward claiming."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.svc = AlbumService()
        self.ptype = PokemonTypeFactory(name="Grass")
        self.player = UserFactory()
        self.player.sticker_dust = 0
        self.player.ryo = 0
        self.player.save(update_fields=["sticker_dust", "ryo"])

    # Completion variants (mirrors _COMPLETION_VARIANTS in services)
    _VARIANTS = list(_COMPLETION_VARIANTS)

    def _place_all_variants(self, poke, rarity: str) -> None:
        """Place one sticker of each variant for the given pokemon+rarity."""
        for variant in self._VARIANTS:
            sticker = StickerFactory(
                pokemon=poke, owner=self.player, rarity=rarity, variant=variant
            )
            self.svc.place_sticker(self.player, sticker.pk)

    def test_page_complete_when_all_variants_placed(self):
        # Use galar region (dex 810-905) with a single test Pokémon
        poke = PokemonFactory(name="TestMon", primary_type=self.ptype, pokedex_number=900)
        self._place_all_variants(poke, StickerRarity.COMMON)

        page_data = self.svc.get_page_detail(self.player, "galar", StickerRarity.COMMON)
        assert page_data["page_complete"] is True

    def test_page_not_complete_with_partial_variants(self):
        poke = PokemonFactory(name="PartialMon", primary_type=self.ptype, pokedex_number=903)
        # Only place 3 of 6 variants
        for variant in self._VARIANTS[:3]:
            s = StickerFactory(pokemon=poke, owner=self.player, rarity=StickerRarity.COMMON, variant=variant)
            self.svc.place_sticker(self.player, s.pk)

        page_data = self.svc.get_page_detail(self.player, "galar", StickerRarity.COMMON)
        assert page_data["page_complete"] is False

    def test_claim_reward_success(self):
        poke = PokemonFactory(name="ClaimMon", primary_type=self.ptype, pokedex_number=901)
        self._place_all_variants(poke, StickerRarity.COMMON)

        reward = self.svc.claim_page_reward(self.player, "galar", StickerRarity.COMMON)

        assert reward["dust"] > 0
        self.player.refresh_from_db()
        assert self.player.sticker_dust == reward["dust"]
        page = RegionalAlbumPage.objects.get(user=self.player, region="galar", rarity=StickerRarity.COMMON)
        assert page.reward_claimed is True

    def test_claim_reward_not_complete_raises(self):
        with pytest.raises(ValueError, match="not yet complete"):
            self.svc.claim_page_reward(self.player, "kanto", StickerRarity.SECRET_RARE)

    def test_claim_reward_already_claimed_raises(self):
        poke = PokemonFactory(name="DupeMon", primary_type=self.ptype, pokedex_number=902)
        self._place_all_variants(poke, StickerRarity.COMMON)
        self.svc.claim_page_reward(self.player, "galar", StickerRarity.COMMON)

        with pytest.raises(ValueError, match="already been claimed"):
            self.svc.claim_page_reward(self.player, "galar", StickerRarity.COMMON)


class TestAlbumServiceRegionIndex:
    """Tests for get_region_index."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.svc = AlbumService()
        self.ptype = PokemonTypeFactory(name="Psychic")
        self.player = UserFactory()

    def test_region_index_returns_all_nine_regions(self):
        result = self.svc.get_region_index(self.player)
        region_names = [r["region"] for r in result]
        assert "kanto" in region_names
        assert "johto" in region_names
        assert "paldea" in region_names
        assert len(result) == 9

    def test_region_with_no_pokemon_is_locked(self):
        result = self.svc.get_region_index(self.player)
        # Johto has no Pokémon in the test DB
        johto = next(r for r in result if r["region"] == "johto")
        assert johto["locked"] is True

    def test_region_with_pokemon_is_not_locked(self):
        PokemonFactory(name="Mew", primary_type=self.ptype, pokedex_number=151)
        result = self.svc.get_region_index(self.player)
        kanto = next(r for r in result if r["region"] == "kanto")
        assert kanto["locked"] is False
        assert kanto["total_pokemon"] >= 1
