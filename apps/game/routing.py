"""WebSocket URL routing for the game app."""
from django.urls import path

from .consumers import BattleConsumer, SpectatorConsumer

websocket_urlpatterns = [
    path("ws/battle/<int:battle_pk>/", BattleConsumer.as_asgi()),
    path("ws/battle/<int:battle_pk>/spectate/", SpectatorConsumer.as_asgi()),
]
