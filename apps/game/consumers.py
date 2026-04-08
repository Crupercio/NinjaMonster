"""
Django Channels WebSocket consumers for real-time battle state updates.

BattleConsumer   — used by the two players; same channel group receives all
                   battle_update / battle_end broadcasts.
SpectatorConsumer — read-only; joins the same group but never sends actions.
                   Any number of spectators can watch a battle simultaneously.

Each battle has its own channel group: "battle_{battle_pk}".
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


class SpectatorConsumer(AsyncWebsocketConsumer):
    """
    Read-only WebSocket consumer for spectating an ongoing battle.

    URL pattern: ws/battle/<battle_pk>/spectate/

    Joins the same channel group as the players so it receives all
    battle_update and battle_end messages automatically.  Client messages
    are silently discarded — spectators cannot influence the battle.
    """

    async def connect(self) -> None:
        self.battle_pk = self.scope["url_route"]["kwargs"]["battle_pk"]
        self.group_name = f"battle_{self.battle_pk}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.debug("Spectator connected to %s", self.group_name)

    async def disconnect(self, code: int) -> None:
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.debug("Spectator disconnected from %s (code=%s)", self.group_name, code)

    async def receive(self, text_data: str = "", bytes_data: bytes = b"") -> None:  # noqa: ARG002
        """Spectator messages are ignored — read-only view."""

    # ------------------------------------------------------------------
    # Same group-message handlers as BattleConsumer — forwards to client
    # ------------------------------------------------------------------

    async def battle_update(self, event: dict) -> None:
        await self.send(text_data=json.dumps({
            "type": "battle_update",
            "payload": event["payload"],
        }))

    async def battle_end(self, event: dict) -> None:
        await self.send(text_data=json.dumps({
            "type": "battle_end",
            "winner": event.get("winner"),
            "max_combo_chain": event.get("max_combo_chain", 0),
        }))
