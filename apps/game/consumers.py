"""
Django Channels WebSocket consumer for real-time battle state updates.

Each battle has its own channel group: "battle_{battle_pk}".
When a round is executed, the view sends a group message and both
players' browsers receive the updated state without a page reload.
"""
import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class BattleConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for a single battle room.

    URL pattern: ws/battle/<battle_pk>/
    """

    async def connect(self) -> None:
        self.battle_pk = self.scope["url_route"]["kwargs"]["battle_pk"]
        self.group_name = f"battle_{self.battle_pk}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.debug("WS connected to %s", self.group_name)

    async def disconnect(self, code: int) -> None:
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.debug("WS disconnected from %s (code=%s)", self.group_name, code)

    async def receive(self, text_data: str = "", bytes_data: bytes = b"") -> None:  # noqa: ARG002
        """Client messages are not processed — server pushes only."""

    # ------------------------------------------------------------------
    # Group message handlers — called when group_send() is used
    # ------------------------------------------------------------------

    async def battle_update(self, event: dict) -> None:
        """Push a full battle state snapshot to the connected client."""
        await self.send(text_data=json.dumps({
            "type": "battle_update",
            "payload": event["payload"],
        }))

    async def battle_end(self, event: dict) -> None:
        """Notify both clients that the battle has finished."""
        await self.send(text_data=json.dumps({
            "type": "battle_end",
            "winner": event.get("winner"),
            "max_combo_chain": event.get("max_combo_chain", 0),
        }))
