"""
Django Channels WebSocket consumers for real-time battle and Loteria state updates.

BattleConsumer        — used by the two players; same channel group receives all
                        battle_update / battle_end broadcasts.
SpectatorConsumer     — read-only; joins the same group but never sends actions.
                        Any number of spectators can watch a battle simultaneously.
LoteriaRoomConsumer   — real-time Loteria room state pushed to all connected players.
                        Replaces 4-second HTTP polling with push-on-draw updates.

Each battle has its own channel group: "battle_{battle_pk}".
Each Loteria room has its own channel group: "loteria_{room_id}".
"""
import json
import logging

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.urls import reverse

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


class LoteriaRoomConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for a live Loteria room.

    URL pattern: ws/loteria/<room_id>/

    On connect  — joins the room's channel group and sends the current state.
    On message  — client sends {"type": "sync"} to request a state push;
                  the server calls advance_loteria_room() (which is idempotent
                  between ticks) then broadcasts the new state to ALL members
                  of the group so every player updates at the same moment.
    On push     — "loteria_state" group messages forwarded to the client.
    On redirect — "loteria_redirect" group messages tell clients to navigate.

    The client still owns the draw timer locally (nextTickEpochMs) and sends a
    sync message ~180 ms after that epoch.  One request does the advance; the
    group push updates everyone.  No more per-client HTTP polling.
    """

    async def connect(self) -> None:
        self.room_id: int = self.scope["url_route"]["kwargs"]["room_id"]
        self.group_name: str = f"loteria_{self.room_id}"
        self.user = self.scope["user"]

        if not self.user or not self.user.is_authenticated:
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.debug("Loteria WS connected: room=%s user=%s", self.room_id, self.user)

        # Send the current state immediately on connect so the client doesn't
        # have to wait for its first scheduled sync.
        await self._push_state()

    async def disconnect(self, code: int) -> None:
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.debug("Loteria WS disconnected: room=%s code=%s", self.room_id, code)

    async def receive(self, text_data: str = "", bytes_data: bytes = b"") -> None:  # noqa: ARG002
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, TypeError):
            return

        if data.get("type") == "sync":
            # Advance the room (idempotent between ticks) then broadcast to group
            await self._advance_and_broadcast()

    # ------------------------------------------------------------------
    # Group message handlers
    # ------------------------------------------------------------------

    async def loteria_state(self, event: dict) -> None:
        """Forward a pre-built state payload to this client."""
        await self.send(text_data=json.dumps({
            "type": "state",
            "payload": event["payload"],
        }))

    async def loteria_redirect(self, event: dict) -> None:
        """Tell the client to navigate to a new URL (room finished/lobby)."""
        await self.send(text_data=json.dumps({
            "type": "redirect",
            "url": event["url"],
        }))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _advance_and_broadcast(self) -> None:
        """Advance room state then push to every connected client in the group."""
        payload, redirect_url = await sync_to_async(self._build_state)()
        if redirect_url:
            await self.channel_layer.group_send(self.group_name, {
                "type": "loteria_redirect",
                "url": redirect_url,
            })
        else:
            await self.channel_layer.group_send(self.group_name, {
                "type": "loteria_state",
                "payload": payload,
            })

    async def _push_state(self) -> None:
        """Send current state to this client only (no group broadcast)."""
        payload, redirect_url = await sync_to_async(self._build_state)()
        if redirect_url:
            await self.send(text_data=json.dumps({"type": "redirect", "url": redirect_url}))
        else:
            await self.send(text_data=json.dumps({"type": "state", "payload": payload}))

    def _build_state(self) -> tuple[dict | None, str | None]:
        """
        Synchronous: advance the room, serialize state, return (payload, redirect_url).
        Called via sync_to_async so ORM access is safe.
        """
        from .fun import (
            advance_loteria_room,
            ensure_default_loteria_board,
            get_loteria_deck_config,
        )
        from .fun_views import (
            _get_accessible_loteria_room_or_404,
            _serialize_loteria_room_state,
        )
        from apps.stickers.models import LoteriaStatus

        try:
            deck_config = get_loteria_deck_config("kanto")
            ensure_default_loteria_board(self.user, deck_config)
            room = _get_accessible_loteria_room_or_404(self.user, self.room_id, deck_config)
        except Exception:
            return None, None

        if room.status in [LoteriaStatus.DRAFT, LoteriaStatus.LOBBY]:
            return None, reverse("game:loteria_lobby", kwargs={"room_id": room.pk})

        room = advance_loteria_room(room, deck_config)
        if room.status == LoteriaStatus.FINISHED:
            return None, reverse("game:loteria_results", kwargs={"room_id": room.pk})

        state = _serialize_loteria_room_state(self.user, room, deck_config)
        latest_called = state["latest_called"]

        payload = {
            "room": {
                "title": room.title,
                "round_number": room.round_number,
                "prize_pool_ryo": room.prize_pool_ryo,
                "called_count": state["called_count"],
                "status": room.status,
                "is_paused": state["is_paused"],
                "pause_remaining_seconds": state["pause_remaining_seconds"],
                "pause_expires_epoch_ms": state["pause_expires_epoch_ms"],
            },
            "latest_called": {
                "id": latest_called.id,
                "name": latest_called.name,
                "pokedex_number": latest_called.pokedex_number,
                "image_url": state["latest_called_image_url"],
            } if latest_called else None,
            "called_history": state["called_history"],
            "player_boards": state["player_boards"],
            "player_board_count": state["player_board_count"],
            "seat_entries": state["seat_entries"],
            "human_player_count": state["human_player_count"],
            "npc_entries": state["npc_entries"],
            "pattern_prizes": state["pattern_prizes"],
            "next_tick_epoch_ms": state["next_tick_epoch_ms"],
            "seconds_until_next": state["seconds_until_next"],
            "server_now_ms": state["server_now_ms"],
        }
        return payload, None
