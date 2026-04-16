"""
Tests for SceneAlbumService: get_region_pages, get_scene_page, get_all_pages_summary.
"""
import pytest

from apps.stickers.models import AlbumPage, StickerRarity
from apps.stickers.services import SceneAlbumService, _COMPLETION_VARIANTS

from tests.framework.factories.pokemon_factory import PokemonFactory, PokemonTypeFactory
from tests.framework.factories.sticker_factory import StickerFactory
from tests.framework.factories.user_factory import UserFactory


pytestmark = pytest.mark.django_db


class TestSceneAlbumServiceGetRegionPages:
    """Tests for get_region_pages."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.svc = SceneAlbumService()
        AlbumPage.objects.create(
            region="kanto", page_number=1,
            dex_start=1, dex_end=15,
            location_name="Pallet Town", bg_image_name="kanto_pallet",
        )
        AlbumPage.objects.create(
            region="kanto", page_number=2,
            dex_start=16, dex_end=30,
            location_name="Viridian Forest", bg_image_name="kanto_viridian",
        )

    def test_returns_pages_for_region(self):
        pages = self.svc.get_region_pages("kanto")
        assert len(pages) == 2

    def test_pages_ordered_by_page_number(self):
        pages = self.svc.get_region_pages("kanto")
        assert pages[0].page_number == 1
        assert pages[1].page_number == 2

    def test_empty_for_unknown_region(self):
        pages = self.svc.get_region_pages("narnia")
        assert pages == []


class TestSceneAlbumServiceGetScenePage:
    """Tests for get_scene_page."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.svc = SceneAlbumService()
        self.ptype = PokemonTypeFactory(name="Fire")
        self.player = UserFactory()
        self.album_page = AlbumPage.objects.create(
            region="kanto", page_number=1,
            dex_start=1, dex_end=15,
            location_name="Pallet Town", bg_image_name="kanto_pallet",
        )
        self.bulbasaur = PokemonFactory(
            name="Bulbasaur", primary_type=self.ptype, pokedex_number=1
        )

    def test_invalid_rarity_raises(self):
        with pytest.raises(ValueError, match="Unknown rarity"):
            self.svc.get_scene_page(self.player, self.album_page, "legendary")

    def test_returns_expected_keys(self):
        data = self.svc.get_scene_page(self.player, self.album_page, StickerRarity.COMMON)
        assert "album_page" in data
        assert "rarity" in data
        assert "pokemon_cards" in data
        assert "page_placed_count" in data
        assert "page_total_count" in data
        assert "page_complete" in data
        assert "reward_claimed" in data
        assert "prev_page" in data
        assert "next_page" in data

    def test_pokemon_in_dex_range_included(self):
        data = self.svc.get_scene_page(self.player, self.album_page, StickerRarity.COMMON)
        poke_ids = [c["pokemon"].pk for c in data["pokemon_cards"]]
        assert self.bulbasaur.pk in poke_ids

    def test_pokemon_outside_dex_range_excluded(self):
        outside = PokemonFactory(name="Pikachu", primary_type=self.ptype, pokedex_number=25)
        data = self.svc.get_scene_page(self.player, self.album_page, StickerRarity.COMMON)
        poke_ids = [c["pokemon"].pk for c in data["pokemon_cards"]]
        assert outside.pk not in poke_ids

    def test_each_card_has_six_variant_slots(self):
        data = self.svc.get_scene_page(self.player, self.album_page, StickerRarity.COMMON)
        card = next(c for c in data["pokemon_cards"] if c["pokemon"].pk == self.bulbasaur.pk)
        assert len(card["variant_slots"]) == len(_COMPLETION_VARIANTS)

    def test_placed_sticker_appears_in_variant_slot(self):
        sticker = StickerFactory(
            pokemon=self.bulbasaur, owner=self.player,
            rarity=StickerRarity.COMMON, variant="base", is_album_placed=True,
        )
        data = self.svc.get_scene_page(self.player, self.album_page, StickerRarity.COMMON)
        card = next(c for c in data["pokemon_cards"] if c["pokemon"].pk == self.bulbasaur.pk)
        base_slot = next(vs for vs in card["variant_slots"] if vs["variant"] == "base")
        assert base_slot["placed_sticker"] is not None
        assert base_slot["placed_sticker"].pk == sticker.pk

    def test_unplaced_sticker_appears_in_available(self):
        sticker = StickerFactory(
            pokemon=self.bulbasaur, owner=self.player,
            rarity=StickerRarity.COMMON, variant="shiny", is_album_placed=False,
        )
        data = self.svc.get_scene_page(self.player, self.album_page, StickerRarity.COMMON)
        card = next(c for c in data["pokemon_cards"] if c["pokemon"].pk == self.bulbasaur.pk)
        shiny_slot = next(vs for vs in card["variant_slots"] if vs["variant"] == "shiny")
        assert sticker in shiny_slot["available_stickers"]

    def test_placed_count_increments_per_placed_variant(self):
        for variant in _COMPLETION_VARIANTS[:3]:
            StickerFactory(
                pokemon=self.bulbasaur, owner=self.player,
                rarity=StickerRarity.COMMON, variant=variant, is_album_placed=True,
            )
        data = self.svc.get_scene_page(self.player, self.album_page, StickerRarity.COMMON)
        card = next(c for c in data["pokemon_cards"] if c["pokemon"].pk == self.bulbasaur.pk)
        assert card["placed_count"] == 3
        assert card["all_placed"] is False

    def test_all_placed_true_when_all_six_variants_placed(self):
        for variant in _COMPLETION_VARIANTS:
            StickerFactory(
                pokemon=self.bulbasaur, owner=self.player,
                rarity=StickerRarity.COMMON, variant=variant, is_album_placed=True,
            )
        data = self.svc.get_scene_page(self.player, self.album_page, StickerRarity.COMMON)
        card = next(c for c in data["pokemon_cards"] if c["pokemon"].pk == self.bulbasaur.pk)
        assert card["all_placed"] is True

    def test_page_complete_when_all_placed(self):
        for variant in _COMPLETION_VARIANTS:
            StickerFactory(
                pokemon=self.bulbasaur, owner=self.player,
                rarity=StickerRarity.COMMON, variant=variant, is_album_placed=True,
            )
        data = self.svc.get_scene_page(self.player, self.album_page, StickerRarity.COMMON)
        assert data["page_complete"] is True

    def test_page_not_complete_when_partial(self):
        StickerFactory(
            pokemon=self.bulbasaur, owner=self.player,
            rarity=StickerRarity.COMMON, variant="base", is_album_placed=True,
        )
        data = self.svc.get_scene_page(self.player, self.album_page, StickerRarity.COMMON)
        assert data["page_complete"] is False

    def test_no_pokemon_in_page_total_count_is_zero(self):
        empty_page = AlbumPage.objects.create(
            region="kanto", page_number=99,
            dex_start=500, dex_end=510,
            location_name="Empty Town", bg_image_name="empty",
        )
        data = self.svc.get_scene_page(self.player, empty_page, StickerRarity.COMMON)
        assert data["page_total_count"] == 0
        assert data["page_complete"] is False

    def test_prev_next_page_navigation(self):
        page2 = AlbumPage.objects.create(
            region="kanto", page_number=2,
            dex_start=16, dex_end=30,
            location_name="Viridian", bg_image_name="kanto_viridian",
        )
        data = self.svc.get_scene_page(self.player, self.album_page, StickerRarity.COMMON)
        assert data["prev_page"] is None
        assert data["next_page"].pk == page2.pk

        data2 = self.svc.get_scene_page(self.player, page2, StickerRarity.COMMON)
        assert data2["prev_page"].pk == self.album_page.pk
        assert data2["next_page"] is None


class TestSceneAlbumServiceGetAllPagesSummary:
    """Tests for get_all_pages_summary."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.svc = SceneAlbumService()
        self.ptype = PokemonTypeFactory(name="Water")
        self.player = UserFactory()
        self.page1 = AlbumPage.objects.create(
            region="kanto", page_number=1,
            dex_start=1, dex_end=15,
            location_name="Pallet Town", bg_image_name="kanto_pallet",
        )
        self.page2 = AlbumPage.objects.create(
            region="kanto", page_number=2,
            dex_start=16, dex_end=30,
            location_name="Viridian Forest", bg_image_name="kanto_viridian",
        )

    def test_returns_entry_per_page(self):
        result = self.svc.get_all_pages_summary(self.player, "kanto")
        assert len(result) == 2

    def test_empty_region_returns_empty(self):
        result = self.svc.get_all_pages_summary(self.player, "johto")
        assert result == []

    def test_each_entry_has_expected_keys(self):
        result = self.svc.get_all_pages_summary(self.player, "kanto")
        entry = result[0]
        assert "album_page" in entry
        assert "rarity_progress" in entry
        assert "overall_placed" in entry
        assert "overall_total" in entry

    def test_rarity_progress_has_all_rarities(self):
        result = self.svc.get_all_pages_summary(self.player, "kanto")
        rarity_keys = [rp["rarity"] for rp in result[0]["rarity_progress"]]
        for r in StickerRarity.values:
            assert r in rarity_keys

    def test_overall_placed_increases_with_placed_stickers(self):
        poke = PokemonFactory(name="Bulbasaur", primary_type=self.ptype, pokedex_number=1)
        StickerFactory(
            pokemon=poke, owner=self.player,
            rarity=StickerRarity.COMMON, variant="base", is_album_placed=True,
        )
        result = self.svc.get_all_pages_summary(self.player, "kanto")
        page1_entry = next(e for e in result if e["album_page"].pk == self.page1.pk)
        assert page1_entry["overall_placed"] > 0
