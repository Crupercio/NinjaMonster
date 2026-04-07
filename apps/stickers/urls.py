"""URL patterns for the stickers app."""
from django.urls import path

from .views import (
    AlbumView,
    BuyPackView,
    CraftView,
    DismantleView,
    DustConvertView,
    PackOpenView,
    TradeCreateView,
    TradeDetailView,
    TradeListView,
)

app_name = "stickers"

urlpatterns = [
    path("album/", AlbumView.as_view(), name="album"),
    path("shop/buy/", BuyPackView.as_view(), name="buy_pack"),
    path("pack/<int:pk>/open/", PackOpenView.as_view(), name="pack_open"),
    path("trade/", TradeListView.as_view(), name="trade_list"),
    path("trade/create/", TradeCreateView.as_view(), name="trade_create"),
    path("trade/<int:pk>/", TradeDetailView.as_view(), name="trade_detail"),
    path("dismantle/", DismantleView.as_view(), name="dismantle"),
    path("dust/", DustConvertView.as_view(), name="dust_convert"),
    path("craft/", CraftView.as_view(), name="craft"),
]
