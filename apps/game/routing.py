"""WebSocket URL routing for the game app."""
from django.urls import path

from .consumers import BattleConsumer

websocket_urlpatterns = [
    path("ws/battle/<int:battle_pk>/", BattleConsumer.as_asgi()),
]
