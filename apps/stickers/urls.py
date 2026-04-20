"""URL patterns for the stickers app."""
from django.urls import path
from django.views.generic import RedirectView

from .views import (
    AlbumPageIndexView,
    AlbumScenePageView,
    AlbumView,
    BuyMultiPackView,
    BuyPackView,
    ClaimPageRewardView,
    DustWorkshopView,
    MyPacksView,
    PackOpenView,
    PlaceStickerView,
    PokemonAlbumDetailView,
    RegionalAlbumDetailView,
    RegionalAlbumIndexView,
    RemoveStickerView,
    StickerDetailView,
    StickerGeneratorView,
    TradeCreateView,
    TradeDetailView,
    TradeListView,
)

app_name = "stickers"

urlpatterns = [
    # Classic album
    path("album/", AlbumView.as_view(), name="album"),
    path("album/<int:pokemon_pk>/", PokemonAlbumDetailView.as_view(), name="pokemon_album"),
    path("sticker/<int:pokemon_pk>/<str:rarity>/<str:variant>/", StickerDetailView.as_view(), name="sticker_detail"),
    # Regional album (backend intact, no longer in main nav)
    path("album/regional/", RegionalAlbumIndexView.as_view(), name="regional_album_index"),
    path("album/regional/<str:region>/<str:rarity>/", RegionalAlbumDetailView.as_view(), name="regional_album_detail"),
    path("album/regional/place/", PlaceStickerView.as_view(), name="place_sticker"),
    path("album/regional/remove/", RemoveStickerView.as_view(), name="remove_sticker"),
    path("album/regional/claim/", ClaimPageRewardView.as_view(), name="claim_page_reward"),
    # Pokédex Pages (formerly "Scene Album")
    path("album/pages/<str:region>/", AlbumPageIndexView.as_view(), name="album_scene_index"),
    path("album/pages/<str:region>/<int:page_number>/<str:rarity>/", AlbumScenePageView.as_view(), name="album_scene_page"),
    # Shop & packs
    path("shop/buy/", BuyPackView.as_view(), name="buy_pack"),
    path("shop/buy/10/", BuyMultiPackView.as_view(), name="buy_10_packs"),
    path("packs/", MyPacksView.as_view(), name="my_packs"),
    path("pack/<int:pk>/open/", PackOpenView.as_view(), name="pack_open"),
    # Trading
    path("trade/", TradeListView.as_view(), name="trade_list"),
    path("trade/create/", TradeCreateView.as_view(), name="trade_create"),
    path("trade/<int:pk>/", TradeDetailView.as_view(), name="trade_detail"),
    # Dust Workshop (unified economy hub — replaces separate dust/craft/dismantle pages)
    path("workshop/", DustWorkshopView.as_view(), name="workshop"),
    # AI Sticker Generator
    path("generator/", StickerGeneratorView.as_view(), name="generator"),
    # Legacy redirects so old bookmarks still work
    path("dust/", RedirectView.as_view(url="/stickers/workshop/?tab=convert"), name="dust_convert"),
    path("craft/", RedirectView.as_view(url="/stickers/workshop/?tab=craft"), name="craft"),
]
