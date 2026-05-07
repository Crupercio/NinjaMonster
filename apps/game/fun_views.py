"""Views for collector arcade experiences under the Fun hub."""
from __future__ import annotations

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView
from django.utils import timezone

from apps.game.models import LoteriaMode, LoteriaRoom, LoteriaStatus
from apps.quests.services import QuestService
from apps.users.services import get_candy_inventory, record_arcade_daily_progress

_quest_service = QuestService()

from .fun import (
    abandon_memory_run,
    abandon_loteria_room,
    advance_silhouette_run,
    answer_silhouette_question,
    cash_out_silhouette_run,
    build_loteria_pattern_tracker,
    clear_memory_result_state,
    clear_silhouette_reveal_state,
    clear_silhouette_run_state,
    claim_all_loteria_prizes,
    claim_loteria_prize,
    complete_memory_run,
    create_private_loteria_room,
    create_quick_loteria_room,
    ensure_default_loteria_board,
    ensure_loteria_host_participant,
    get_allowed_loteria_npc_counts,
    get_loteria_deck_config,
    get_loteria_board_label,
    get_user_pending_loteria_claims,
    get_loteria_room_participants,
    LOTERIA_NPC_NAMES,
    get_loteria_species_map,
    get_loteria_starter_board_slot,
    get_random_memory_species,
    get_user_open_loteria_room,
    get_user_loteria_boards,
    get_user_owned_loteria_species,
    get_user_recent_finished_loteria_room,
    get_user_loteria_starter_board,
    get_loteria_entry_display_name,
    join_private_loteria_room,
    save_loteria_room_boards,
    save_loteria_board_template,
    serialize_loteria_board,
    set_loteria_room_participant_ready,
    start_loteria_room,
    toggle_loteria_pause,
    advance_loteria_room,
    get_memory_board_catalog,
    get_memory_board_config,
    get_memory_result_state,
    get_memory_run_state,
    get_silhouette_reveal_state,
    get_silhouette_run_state,
    get_silhouette_tower_catalog,
    get_silhouette_tower_config,
    get_tower_species_map,
    start_memory_run,
    start_silhouette_run,
    get_random_silhouette_species,
)


def _pokemon_image_url(pokemon) -> str:
    """Best-effort artwork URL for silhouette and option previews."""
    if pokemon.sprite_url:
        return pokemon.sprite_url
    if pokemon.pokedex_number:
        return f"/media/pokemon/sprites/{pokemon.pokedex_number:03d}.png"
    return ""


class ComingSoonGameView(LoginRequiredMixin, TemplateView):
    """Placeholder collector arcade page for upcoming games."""

    template_name = "game/coming_soon_game.html"
    game_title = "Coming Soon"
    game_subtitle = "Collector arcade cabinet"
    game_logo = ""
    game_copy = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "game_title": self.game_title,
                "game_subtitle": self.game_subtitle,
                "game_logo": self.game_logo,
                "game_copy": self.game_copy,
                "candy_inventory": get_candy_inventory(self.request.user),
            }
        )
        return context


class MemoryMatchView(ComingSoonGameView):
    """Focused play page for one memory board."""

    template_name = "game/memory_game.html"
    board_mascots = {
        "rookie_3x4": "images/games/memory_board_rookie.gif",
        "standard_4x4": "images/games/memory_board_standard.gif",
        "collector_4x5": "images/games/memory_board_collector.gif",
        "master_6x4": "images/games/memory_board_master.gif",
    }

    def dispatch(self, request, *args, **kwargs):
        self.board_config = get_memory_board_config(kwargs["board_key"])
        if not self.board_config.enabled:
            messages.info(request, f"{self.board_config.title} is not open yet.")
            return redirect("game:memory_game")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        run_state = get_memory_run_state(self.request.session)
        board_run = run_state if run_state and run_state.get("board_key") == self.board_config.key else None
        result_state = get_memory_result_state(self.request.session)
        board_result = result_state if result_state and result_state.get("board_key") == self.board_config.key else None

        context.update(
            {
                "board": self.board_config,
                "board_run": board_run,
                "board_result": board_result,
                "candy_inventory": get_candy_inventory(self.request.user),
                "board_mascot": self.board_mascots.get(self.board_config.key, ""),
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action", "")
        run_state = get_memory_run_state(request.session)
        board_run = run_state if run_state and run_state.get("board_key") == self.board_config.key else None
        return_url = reverse("game:memory_board", kwargs={"board_key": self.board_config.key})

        if action == "start_run":
            try:
                start_memory_run(request.user, request.session, self.board_config)
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(
                    request,
                    f"{self.board_config.title} opened. {self.board_config.entry_qty} {self.board_config.entry_label} spent.",
                )
            return redirect(return_url)

        if action == "abandon":
            abandon_memory_run(request.session)
            clear_memory_result_state(request.session)
            messages.info(request, "The current memory board was cleared without claiming rewards.")
            return redirect(return_url)

        if action == "dismiss_result":
            clear_memory_result_state(request.session)
            return redirect(return_url)

        if action == "complete_run":
            if not board_run:
                messages.error(request, "Start a memory board before claiming rewards.")
                return redirect(return_url)
            try:
                turns = int(request.POST.get("turns", "0"))
                elapsed_seconds = int(request.POST.get("elapsed_seconds", "0"))
                best_streak = int(request.POST.get("best_streak", "0"))
            except ValueError:
                messages.error(request, "The memory board result could not be scored.")
                return redirect(return_url)

            result = complete_memory_run(
                request.user,
                request.session,
                self.board_config,
                board_run,
                turns=turns,
                elapsed_seconds=elapsed_seconds,
                best_streak=best_streak,
            )
            messages.success(
                request,
                f"{result['grade']} clear! You earned {result['reward_ryo']} Ryo and {result['reward_dust']} Dust.",
            )
            record_arcade_daily_progress(
                request.user,
                memory_clear=True,
                memory_elapsed_seconds=elapsed_seconds,
                memory_master_clear=self.board_config.key == "master_6x4",
            )
            _quest_service.on_memory_completed(request.user)
            from apps.users.achievement_service import AchievementService
            AchievementService().on_memory_complete(request.user, self.board_config.key, result["grade"])
            return redirect(return_url)

        messages.error(request, "Unknown memory board action.")
        return redirect(return_url)


class MemoryHubView(LoginRequiredMixin, TemplateView):
    """Board selection hub for the memory arcade."""

    template_name = "game/memory_hub.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        candy_inventory = get_candy_inventory(self.request.user)
        run_state = get_memory_run_state(self.request.session)
        result_state = get_memory_result_state(self.request.session)
        current_key = None
        if result_state and result_state.get("board_key"):
            current_key = result_state["board_key"]
        elif run_state and run_state.get("board_key"):
            current_key = run_state["board_key"]

        board_cards = []
        for board in get_memory_board_catalog():
            count = candy_inventory.get(board.entry_candy_type, {}).get("count", 0)
            board_cards.append(
                {
                    "config": board,
                    "entry_count": count,
                    "can_enter": count >= board.entry_qty,
                    "is_current": board.key == current_key,
                }
            )

        active_board = get_memory_board_config(current_key) if current_key else None
        context.update(
            {
                "candy_inventory": candy_inventory,
                "board_cards": board_cards,
                "active_memory_board": active_board,
            }
        )
        return context


def _get_accessible_loteria_room_or_404(user, room_id: int, config):
    """Return a room the current user hosts or participates in."""
    room = (
        LoteriaRoom.objects.select_related("created_by", "guild")
        .filter(pk=room_id, deck_key=config.key)
        .filter(created_by=user)
        .first()
    )
    if room is None:
        room = (
            LoteriaRoom.objects.select_related("created_by", "guild")
            .filter(pk=room_id, deck_key=config.key, participants__user=user)
            .distinct()
            .first()
        )
    if room is None:
        raise Http404("Loteria room not found.")
    ensure_loteria_host_participant(room)
    return room


def _build_loteria_board_cards(user, config, called_set: set[int] | None = None, include_empty_slots: bool = False):
    """Serialize saved boards and optionally expose empty board slots for the hub."""
    species_map = get_loteria_species_map(config)
    active_calls = called_set or set()
    saved_boards = get_user_loteria_boards(user, config)
    saved_by_slot = {}
    board_cards = []
    for board in saved_boards:
        card = serialize_loteria_board(board, species_map, active_calls)
        card["template"] = board
        card["is_saved"] = True
        saved_by_slot[board.board_slot] = card
        board_cards.append(card)
    if include_empty_slots:
        board_cards = []
        for slot in range(1, config.max_saved_boards + 1):
            saved_card = saved_by_slot.get(slot)
            if saved_card:
                board_cards.append(saved_card)
                continue
                board_cards.append(
                {
                    "id": None,
                    "title": get_loteria_board_label(slot),
                    "board_slot": slot,
                    "cells": [],
                    "board_size": config.board_size,
                    "marked_count": 0,
                    "is_complete": False,
                    "is_saved": False,
                    "is_starter": False,
                }
            )
    for card in board_cards:
        card.setdefault("is_starter", False)
    return board_cards


def _get_request_guild_membership(user):
    """Return the current user's guild membership when present."""
    try:
        return user.guild_membership
    except Exception:
        return None


def _serialize_loteria_room_state(user, room, config):
    """Build a live-room snapshot for both HTML render and JSON polling."""
    species_map = get_loteria_species_map(config)
    called_set = set(room.called_species_ids)
    player_entries = list(
        room.entries.filter(user=user, is_npc=False)
        .select_related("board_template")
        .order_by("board_slot")
    )
    serialized_player_boards = []
    for entry in player_entries:
        board_payload = serialize_loteria_board(entry, species_map, called_set)
        serialized_player_boards.append(
            {
                **board_payload,
                "display_name": entry.display_name,
                "owner_name": entry.user.username,
                "board_label": board_payload["title"],
                "board_slot": entry.board_slot,
            }
        )

    human_entries = list(
        room.entries.filter(user__isnull=False, is_npc=False)
        .select_related("user", "board_template")
        .order_by("entered_at", "pk")
    )
    serialized_seat_entries = []
    for entry in human_entries:
        human_board = serialize_loteria_board(entry, species_map, called_set)
        serialized_seat_entries.append(
            {
                "display_name": entry.display_name,
                "owner_name": entry.user.username,
                "board_label": human_board["title"],
                "board_size": human_board["board_size"],
                "marked_count": human_board["marked_count"],
                "is_current_user": entry.user_id == user.id,
            }
        )

    npc_entries = list(room.entries.filter(is_npc=True).order_by("entered_at", "pk"))
    serialized_npc_entries = []
    for entry in npc_entries:
        npc_board = serialize_loteria_board(entry, species_map, called_set)
        serialized_npc_entries.append(
            {
                "display_name": entry.display_name,
                "board_size": npc_board["board_size"],
                "marked_count": npc_board["marked_count"],
            }
        )

    latest_species = species_map.get(room.called_species_ids[-1]) if room.called_species_ids else None
    called_history_species = [species_map.get(species_id) for species_id in reversed(room.called_species_ids[-12:])]
    called_history = [
        {
            "name": pokemon.name,
            "image_url": _pokemon_image_url(pokemon),
        }
        for pokemon in called_history_species
        if pokemon is not None
    ]

    seconds_until_next = None
    next_tick_epoch_ms = None
    if room.next_tick_at:
        seconds_until_next = max(0, int((room.next_tick_at - timezone.now()).total_seconds()))
        next_tick_epoch_ms = int(room.next_tick_at.timestamp() * 1000)
    pause_remaining_seconds = room.pause_remaining_seconds
    pause_expires_epoch_ms = None
    if room.paused_at:
        elapsed_seconds = max(0, int((timezone.now() - room.paused_at).total_seconds()))
        pause_remaining_seconds = max(0, room.pause_remaining_seconds - elapsed_seconds)
        pause_expires_epoch_ms = int((room.paused_at + timedelta(seconds=room.pause_remaining_seconds)).timestamp() * 1000)

    return {
        "latest_called": latest_species,
        "latest_called_id": latest_species.id if latest_species else None,
        "latest_called_image_url": _pokemon_image_url(latest_species) if latest_species else "",
        "called_history": called_history,
        "player_boards": serialized_player_boards,
        "player_board_count": len(serialized_player_boards),
        "seat_entries": serialized_seat_entries,
        "human_player_count": len({entry.user_id for entry in human_entries if entry.user_id}),
        "npc_entries": serialized_npc_entries,
        "pattern_prizes": build_loteria_pattern_tracker(room, config, viewer_user=user),
        "seconds_until_next": seconds_until_next,
        "next_tick_epoch_ms": next_tick_epoch_ms,
        "server_now_ms": int(timezone.now().timestamp() * 1000),
        "called_count": len(room.called_species_ids),
        "is_paused": bool(room.paused_at),
        "pause_remaining_seconds": pause_remaining_seconds,
        "pause_expires_epoch_ms": pause_expires_epoch_ms,
    }


def _build_loteria_player_investment(user, room, config) -> dict:
    """Summarize the current user's spend and match bonus for one room."""
    player_board_count = room.entries.filter(user=user, is_npc=False).count()
    ryo_spent = 0
    candy_qty = 0
    candy_label = ""
    matched_ryo = 0
    if room.mode == LoteriaMode.PRIVATE:
        ryo_spent = (room.entry_fee_ryo or 0) * player_board_count
        matched_ryo = ryo_spent
    else:
        ryo_spent = room.entry_fee_ryo or config.entry_fee_for_npc_count(room.npc_count)
        candy_qty = player_board_count * config.entry_qty_per_board
        candy_label = config.entry_label
    spend_parts = []
    if ryo_spent > 0:
        spend_parts.append(f"{ryo_spent} Ryo")
    if candy_qty > 0 and candy_label:
        spend_parts.append(f"{candy_qty} {candy_label}")
    return {
        "board_count": player_board_count,
        "ryo_spent": ryo_spent,
        "candy_qty": candy_qty,
        "candy_label": candy_label,
        "matched_ryo": matched_ryo,
        "spend_display": " + ".join(spend_parts) if spend_parts else "No spend recorded",
        "spend_note": (
            f"Game matched +{matched_ryo} Ryo into the pot."
            if matched_ryo > 0
            else (f"Includes {candy_qty} {candy_label} and the quick-play room fee." if candy_qty > 0 and candy_label else "Includes the quick-play room fee.")
        ),
    }


class LoteriaHubView(LoginRequiredMixin, TemplateView):
    """Generation room hub for Pokemon Loteria."""

    template_name = "game/loteria_hub.html"

    def dispatch(self, request, *args, **kwargs):
        self.deck_config = get_loteria_deck_config("kanto")
        ensure_default_loteria_board(request.user, self.deck_config)
        self.open_room = get_user_open_loteria_room(request.user, self.deck_config)
        self.recent_finished_room = get_user_recent_finished_loteria_room(request.user, self.deck_config)
        if request.method == "GET" and request.user.is_authenticated:
            from apps.users.guide_service import maybe_advance_from_url
            maybe_advance_from_url(request.user, "game:loteria_game")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        guild_membership = _get_request_guild_membership(self.request.user)
        starter_board = get_user_loteria_starter_board(self.request.user, self.deck_config)
        starter_board_card = None
        if starter_board:
            starter_board_card = serialize_loteria_board(starter_board, get_loteria_species_map(self.deck_config), set())
            starter_board_card["template"] = starter_board
            starter_board_card["is_saved"] = True
            starter_board_card["is_starter"] = True
        board_cards = _build_loteria_board_cards(
            self.request.user,
            self.deck_config,
            include_empty_slots=True,
        )
        first_open_board = next((board for board in board_cards if not board["is_saved"]), None)
        recent_player_wins = list(self.recent_finished_room.entries.filter(user=self.request.user, is_winner=True).order_by("board_slot")) if self.recent_finished_room else []
        npc_options = []
        for npc_count in get_allowed_loteria_npc_counts(self.deck_config):
            npc_options.append(
                {
                    "npc_count": npc_count,
                    "base_prize": self.deck_config.prize_for_npc_count(npc_count),
                    "entry_fee_ryo": self.deck_config.entry_fee_for_npc_count(npc_count),
                    "entry_label": f"{npc_count} NPC",
                }
            )
        context.update(
            {
                "deck": self.deck_config,
                "candy_inventory": get_candy_inventory(self.request.user),
                "open_room": self.open_room,
                "recent_finished_room": self.recent_finished_room,
                "starter_board": starter_board_card,
                "board_cards": board_cards,
                "saved_board_count": sum(1 for board in board_cards if board["is_saved"]),
                "board_builder_slot": first_open_board["board_slot"] if first_open_board else 1,
                "recent_player_wins": recent_player_wins,
                "npc_options": npc_options,
                "my_guild_membership": guild_membership,
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action", "")
        if action == "create_private_room":
            guild_only = request.POST.get("guild_only") == "1"
            try:
                room = create_private_loteria_room(request.user, self.deck_config, guild_only=guild_only)
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                table_label = "guild-only" if room.guild_id else "private"
                messages.success(request, f"{self.deck_config.title} {table_label} room opened. Share code {room.room_code}.")
                return redirect("game:loteria_lobby", room_id=room.pk)
        if action == "join_private_room":
            try:
                room = join_private_loteria_room(request.user, self.deck_config, request.POST.get("room_code", ""))
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, f"Joined private room {room.room_code}.")
                return redirect("game:loteria_lobby", room_id=room.pk)
        if action == "create_room":
            try:
                npc_count = int(request.POST.get("npc_count", "0"))
            except ValueError:
                messages.error(request, "Choose a valid NPC count before creating a room.")
                return redirect("game:loteria_game")
            try:
                room = create_quick_loteria_room(request.user, self.deck_config, npc_count)
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, f"{self.deck_config.title} room created against {npc_count} NPCs.")
                return redirect("game:loteria_lobby", room_id=room.pk)
        messages.error(request, "Unknown Loteria action.")
        return redirect("game:loteria_game")


class LoteriaRoomJoinView(LoginRequiredMixin, View):
    """Join or reopen a private/guild room directly from another surface."""

    def post(self, request, room_id: int):
        deck_config = get_loteria_deck_config("kanto")
        ensure_default_loteria_board(request.user, deck_config)
        room = get_object_or_404(
            LoteriaRoom.objects.select_related("created_by", "guild"),
            pk=room_id,
            deck_key=deck_config.key,
        )
        if room.mode != LoteriaMode.PRIVATE:
            messages.error(request, "Only private and guild Loteria rooms can be joined this way.")
            return redirect("game:loteria_game")

        already_in_room = room.created_by_id == request.user.id or room.participants.filter(user=request.user).exists()
        if not already_in_room:
            try:
                room = join_private_loteria_room(request.user, deck_config, room.room_code or "")
            except ValueError as exc:
                messages.error(request, str(exc))
                return redirect("game:loteria_game")
            messages.success(request, f"Joined {room.title}.")

        if room.status == LoteriaStatus.ACTIVE:
            return redirect("game:loteria_room", room_id=room.pk)
        if room.status == LoteriaStatus.FINISHED:
            return redirect("game:loteria_results", room_id=room.pk)
        return redirect("game:loteria_lobby", room_id=room.pk)


class LoteriaBoardBuilderView(LoginRequiredMixin, TemplateView):
    """Saved board builder for one Loteria generation deck."""

    template_name = "game/loteria_board_builder.html"

    def dispatch(self, request, *args, **kwargs):
        self.deck_config = get_loteria_deck_config("kanto")
        self.board_slot = int(kwargs["board_slot"])
        ensure_default_loteria_board(request.user, self.deck_config)
        if self.board_slot < 1 or self.board_slot > self.deck_config.max_saved_boards:
            messages.info(request, "The starter board is a locked lucky board and cannot be edited.")
            return redirect("game:loteria_game")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        species_map = get_loteria_species_map(self.deck_config)
        board_templates = get_user_loteria_boards(self.request.user, self.deck_config)
        template = next((board for board in board_templates if board.board_slot == self.board_slot), None)
        owned_species = [
            {
                "id": pokemon.id,
                "name": pokemon.name,
                "dex": pokemon.pokedex_number,
                "image_url": _pokemon_image_url(pokemon),
            }
            for pokemon in get_user_owned_loteria_species(self.request.user, self.deck_config)
        ]
        selected_species = []
        if template:
            for species_id in template.species_ids:
                pokemon = species_map.get(species_id)
                if pokemon:
                    selected_species.append(
                        {
                            "id": pokemon.id,
                            "name": pokemon.name,
                            "dex": pokemon.pokedex_number,
                            "image_url": _pokemon_image_url(pokemon),
                        }
                    )

        context.update(
            {
                "deck": self.deck_config,
                "candy_inventory": get_candy_inventory(self.request.user),
                "board_slot": self.board_slot,
                "existing_board": template,
                "saved_boards": board_templates,
                "owned_species": owned_species,
                "eligible_species_count": len(owned_species),
                "selected_species": selected_species,
                "can_build_extra": len(owned_species) >= self.deck_config.board_size,
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        title = f"Board {self.board_slot}"
        raw_species_ids = [value for value in request.POST.get("species_ids", "").split(",") if value.strip()]
        try:
            save_loteria_board_template(
                request.user,
                self.deck_config,
                board_slot=self.board_slot,
                title=title,
                species_ids=[int(species_id) for species_id in raw_species_ids],
            )
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("game:loteria_builder", board_slot=self.board_slot)

        messages.success(request, f"Board {self.board_slot} saved for {self.deck_config.title}.")
        return redirect("game:loteria_game")


class LoteriaRoomView(LoginRequiredMixin, TemplateView):
    """Live Kanto Loteria room."""

    template_name = "game/loteria_room.html"

    def dispatch(self, request, *args, **kwargs):
        self.deck_config = get_loteria_deck_config("kanto")
        ensure_default_loteria_board(request.user, self.deck_config)
        self.room = _get_accessible_loteria_room_or_404(request.user, kwargs["room_id"], self.deck_config)
        if self.room.status in [LoteriaStatus.DRAFT, LoteriaStatus.LOBBY]:
            return redirect("game:loteria_lobby", room_id=self.room.pk)
        self.room = advance_loteria_room(self.room, self.deck_config)
        if self.room.status == LoteriaStatus.FINISHED:
            return redirect("game:loteria_results", room_id=self.room.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        investment = _build_loteria_player_investment(self.request.user, self.room, self.deck_config)
        context.update(
            {
                "deck": self.deck_config,
                "candy_inventory": get_candy_inventory(self.request.user),
                "room": self.room,
                "room_state_url": reverse("game:loteria_room_state", kwargs={"room_id": self.room.pk}),
                "user_is_host": self.room.created_by_id == self.request.user.id,
                "room_mode_label": "Guild Table" if self.room.guild_id else ("Private Table" if self.room.mode == LoteriaMode.PRIVATE else "NPC Table"),
                "player_investment": investment,
            }
        )
        context.update(_serialize_loteria_room_state(self.request.user, self.room, self.deck_config))
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action", "")
        if action in {"pause_room", "resume_room"}:
            try:
                toggle_loteria_pause(request.user, self.room, pause=action == "pause_room")
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                if action == "pause_room":
                    messages.info(request, "Loteria table paused. The shared 10-minute break timer is running.")
                else:
                    messages.success(request, "Loteria table resumed.")
            return redirect("game:loteria_room", room_id=self.room.pk)
        if action == "abandon_room":
            try:
                abandon_loteria_room(request.user, self.room)
            except ValueError as exc:
                messages.error(request, str(exc))
                return redirect("game:loteria_room", room_id=self.room.pk)
            messages.info(request, "Loteria room abandoned.")
            return redirect("game:loteria_game")

        messages.error(request, "Unknown Loteria room action.")
        return redirect("game:loteria_room", room_id=self.room.pk)


class LoteriaRoomStateView(LoginRequiredMixin, View):
    """Return live room state without forcing a full page refresh."""

    def get(self, request, room_id: int):
        deck_config = get_loteria_deck_config("kanto")
        ensure_default_loteria_board(request.user, deck_config)
        room = _get_accessible_loteria_room_or_404(request.user, room_id, deck_config)
        if room.status in [LoteriaStatus.DRAFT, LoteriaStatus.LOBBY]:
            return JsonResponse({
                "redirect_url": reverse("game:loteria_lobby", kwargs={"room_id": room.pk}),
            })

        room = advance_loteria_room(room, deck_config)
        if room.status == LoteriaStatus.FINISHED:
            return JsonResponse({
                "redirect_url": reverse("game:loteria_results", kwargs={"room_id": room.pk}),
            })

        state = _serialize_loteria_room_state(request.user, room, deck_config)
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
            "latest_called": None,
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

        latest_called = state["latest_called"]
        if latest_called:
            payload["latest_called"] = {
                "id": latest_called.id,
                "name": latest_called.name,
                "pokedex_number": latest_called.pokedex_number,
                "image_url": state["latest_called_image_url"],
            }

        return JsonResponse(payload)


class LoteriaLobbyStateView(LoginRequiredMixin, View):
    """Return lightweight lobby status so players can jump into live play."""

    def get(self, request, room_id: int):
        deck_config = get_loteria_deck_config("kanto")
        ensure_default_loteria_board(request.user, deck_config)
        room = _get_accessible_loteria_room_or_404(request.user, room_id, deck_config)
        payload = {
            "room": {
                "status": room.status,
                "title": room.title,
            },
            "participant_ready_count": room.participants.filter(is_ready=True).count(),
            "participant_count": room.participants.count(),
        }
        if room.status == LoteriaStatus.ACTIVE:
            payload["live_url"] = reverse("game:loteria_room", kwargs={"room_id": room.pk})
        elif room.status == LoteriaStatus.FINISHED:
            payload["results_url"] = reverse("game:loteria_results", kwargs={"room_id": room.pk})
        return JsonResponse(payload)


class LoteriaLobbyView(LoginRequiredMixin, TemplateView):
    """Pre-game lobby for a player-owned Loteria room."""

    template_name = "game/loteria_lobby.html"

    def dispatch(self, request, *args, **kwargs):
        self.deck_config = get_loteria_deck_config("kanto")
        ensure_default_loteria_board(request.user, self.deck_config)
        self.room = _get_accessible_loteria_room_or_404(request.user, kwargs["room_id"], self.deck_config)
        if self.room.status == LoteriaStatus.ACTIVE:
            return redirect("game:loteria_room", room_id=self.room.pk)
        if self.room.status == LoteriaStatus.FINISHED:
            return redirect("game:loteria_results", room_id=self.room.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        board_cards = _build_loteria_board_cards(self.request.user, self.deck_config)
        current_participant = ensure_loteria_host_participant(self.room) if self.room.created_by_id == self.request.user.id else None
        if current_participant is None:
            current_participant = self.room.participants.filter(user=self.request.user).first()
        starter_board = get_user_loteria_starter_board(self.request.user, self.deck_config)
        starter_board_card = None
        if starter_board:
            starter_board_card = serialize_loteria_board(starter_board, get_loteria_species_map(self.deck_config), set())
            starter_board_card["template"] = starter_board
            starter_board_card["is_saved"] = True
            starter_board_card["is_starter"] = True
        selected_board_ids = set(self.room.entries.filter(user=self.request.user, board_template__isnull=False).values_list("board_template_id", flat=True))
        ordered_board_cards = []
        if starter_board_card:
            ordered_board_cards.append(starter_board_card)
        ordered_board_cards.extend(board_cards)
        if not selected_board_ids and ordered_board_cards:
            selected_board_ids = {ordered_board_cards[0]["id"]}
        for card in ordered_board_cards:
            card["is_selected"] = card["id"] in selected_board_ids

        participants = get_loteria_room_participants(self.room)
        participant_summaries = []
        for participant in participants:
            board_count = self.room.entries.filter(user=participant.user, is_npc=False).count()
            participant_summaries.append(
                {
                    "display_name": participant.user.username,
                    "username": participant.user.username,
                    "is_host": participant.is_host,
                    "is_ready": participant.is_ready,
                    "board_count": board_count,
                    "is_current_user": participant.user_id == self.request.user.id,
                }
            )
        total_selected_boards = sum(item["board_count"] for item in participant_summaries)
        all_ready = bool(participant_summaries) and all(item["is_ready"] and item["board_count"] > 0 for item in participant_summaries)

        context.update(
            {
                "deck": self.deck_config,
                "room": self.room,
                "candy_inventory": get_candy_inventory(self.request.user),
                "board_cards": ordered_board_cards,
                "starter_board_slot": get_loteria_starter_board_slot(self.deck_config),
                "npc_labels": LOTERIA_NPC_NAMES[: self.room.npc_count],
                "base_prize": self.deck_config.prize_for_npc_count(self.room.npc_count),
                "npc_entry_fee_ryo": self.deck_config.entry_fee_for_npc_count(self.room.npc_count),
                "per_board_bonus": self.deck_config.prize_boost_per_player_board,
                "user_is_host": self.room.created_by_id == self.request.user.id,
                "current_participant": current_participant,
                "participant_summaries": participant_summaries,
                "total_selected_boards": total_selected_boards,
                "all_players_ready": all_ready,
                "room_mode_label": "Guild Table" if self.room.guild_id else ("Private Table" if self.room.mode == LoteriaMode.PRIVATE else "Quick NPC Table"),
                "room_join_code": self.room.room_code or "",
                "room_status_url": reverse("game:loteria_lobby_state", kwargs={"room_id": self.room.pk}),
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action", "")
        if action == "abandon_room":
            try:
                abandon_loteria_room(request.user, self.room)
            except ValueError as exc:
                messages.error(request, str(exc))
                return redirect("game:loteria_lobby", room_id=self.room.pk)
            messages.info(request, "Loteria room abandoned.")
            return redirect("game:loteria_game")

        if action == "save_selection":
            board_ids = request.POST.getlist("board_ids")
            try:
                save_loteria_room_boards(request.user, self.room, self.deck_config, board_ids, mark_ready=True)
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, "Boards saved and your seat is ready.")
            return redirect("game:loteria_lobby", room_id=self.room.pk)

        if action == "set_not_ready":
            try:
                set_loteria_room_participant_ready(request.user, self.room, is_ready=False)
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.info(request, "Your seat is marked not ready.")
            return redirect("game:loteria_lobby", room_id=self.room.pk)

        if action == "start_room":
            try:
                if self.room.mode == LoteriaMode.PRIVATE:
                    start_loteria_room(request.user, self.room, self.deck_config)
                else:
                    start_loteria_room(request.user, self.room, self.deck_config, request.POST.getlist("board_ids"))
            except ValueError as exc:
                messages.error(request, str(exc))
                return redirect("game:loteria_lobby", room_id=self.room.pk)
            messages.success(request, "Loteria table launched. The first card lands in 15 seconds.")
            return redirect("game:loteria_room", room_id=self.room.pk)

        messages.error(request, "Unknown Loteria lobby action.")
        return redirect("game:loteria_lobby", room_id=self.room.pk)


class LoteriaResultsView(LoginRequiredMixin, TemplateView):
    """Finished-state results for a Loteria room."""

    template_name = "game/loteria_results.html"

    def dispatch(self, request, *args, **kwargs):
        self.deck_config = get_loteria_deck_config("kanto")
        self.room = _get_accessible_loteria_room_or_404(request.user, kwargs["room_id"], self.deck_config)
        if self.room.status in [LoteriaStatus.DRAFT, LoteriaStatus.LOBBY]:
            return redirect("game:loteria_lobby", room_id=self.room.pk)
        if self.room.status == LoteriaStatus.ACTIVE:
            return redirect("game:loteria_room", room_id=self.room.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        species_map = get_loteria_species_map(self.deck_config)
        called_set = set(self.room.called_species_ids)
        investment = _build_loteria_player_investment(self.request.user, self.room, self.deck_config)
        player_boards = [
            {
                **(board_payload := serialize_loteria_board(entry, species_map, called_set)),
                "display_name": entry.display_name,
                "owner_name": entry.user.username if entry.user_id else "",
                "board_label": board_payload["title"],
                "board_slot": entry.board_slot,
                "is_winner": entry.is_winner,
                "reward_ryo": entry.reward_ryo,
            }
            for entry in self.room.entries.filter(user=self.request.user).select_related("board_template").order_by("board_slot")
        ]
        if player_boards:
            best_marked = max(int(board["marked_count"]) for board in player_boards)
            buena_hit = any(bool(board["is_complete"]) for board in player_boards)
            record_arcade_daily_progress(
                self.request.user,
                loteria_room_id=self.room.pk,
                loteria_marked_count=best_marked,
                loteria_buena=buena_hit,
            )
        winners = self.room.entries.filter(is_winner=True).select_related("board_template", "user").order_by("entered_at", "pk")
        winning_boards = [
            {
                **(board_payload := serialize_loteria_board(entry, species_map, called_set)),
                "display_name": entry.display_name,
                "owner_name": entry.user.username if entry.user_id else entry.display_name,
                "board_label": board_payload["title"],
                "board_slot": entry.board_slot,
                "reward_ryo": entry.reward_ryo,
                "is_npc": entry.is_npc,
            }
            for entry in winners
        ]
        called_history = [species_map.get(species_id) for species_id in reversed(self.room.called_species_ids[-16:])]
        called_history = [pokemon for pokemon in called_history if pokemon is not None]
        pending_room_claims = list(get_user_pending_loteria_claims(self.request.user).filter(room=self.room))
        pending_room_total = sum(claim.reward_ryo for claim in pending_room_claims)
        context.update(
            {
                "deck": self.deck_config,
                "room": self.room,
                "called_history": called_history,
                "player_boards": player_boards,
                "winners": winners,
                "winning_boards": winning_boards,
                "pattern_prizes": build_loteria_pattern_tracker(self.room, self.deck_config, viewer_user=self.request.user),
                "candy_inventory": get_candy_inventory(self.request.user),
                "pending_room_claims": pending_room_claims,
                "pending_room_total": pending_room_total,
                "player_investment": investment,
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        next_url = reverse("game:loteria_results", kwargs={"room_id": self.room.pk})
        action = request.POST.get("action", "")
        if action == "claim_prize":
            try:
                claim_id = int(request.POST.get("claim_id", "0"))
                claim = claim_loteria_prize(request.user, claim_id, room=self.room)
            except (TypeError, ValueError) as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, f"{claim.pattern_label} collected for {claim.reward_ryo} Ryo.")
                _quest_service.on_loteria_played(request.user)
                from apps.users.achievement_service import AchievementService
                AchievementService().on_loteria_win(request.user, is_full_board=getattr(claim, "pattern_key", "") == "full_board")
            return redirect(next_url)
        if action == "claim_all_prizes":
            try:
                claim_count, total_ryo = claim_all_loteria_prizes(request.user, room=self.room)
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, f"Collected {claim_count} Loteria prize{'' if claim_count == 1 else 's'} for {total_ryo} Ryo.")
                _quest_service.on_loteria_played(request.user)
                from apps.users.achievement_service import AchievementService
                buena = any(bool(b.get("is_complete")) for b in (getattr(self, "_player_boards_cache", None) or []))
                AchievementService().on_loteria_win(request.user, is_full_board=buena)
            return redirect(next_url)
        messages.error(request, "Unknown Loteria results action.")
        return redirect(next_url)


class LoteriaPrizeClaimView(LoginRequiredMixin, View):
    """Claim one or many finished-room Loteria prizes from any surface."""

    def post(self, request):
        next_url = request.POST.get("next") or reverse("game:loteria_game")
        action = request.POST.get("action", "")
        if action == "claim_prize":
            try:
                claim_id = int(request.POST.get("claim_id", "0"))
                room_id = request.POST.get("room_id", "").strip()
                room = None
                if room_id:
                    room = LoteriaRoom.objects.filter(pk=int(room_id)).first()
                claim = claim_loteria_prize(request.user, claim_id, room=room)
            except (TypeError, ValueError) as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, f"{claim.pattern_label} collected for {claim.reward_ryo} Ryo.")
            return redirect(next_url)
        if action == "claim_all_prizes":
            room_id = request.POST.get("room_id", "").strip()
            room = None
            if room_id:
                try:
                    room = LoteriaRoom.objects.get(pk=int(room_id))
                except (LoteriaRoom.DoesNotExist, ValueError):
                    messages.error(request, "That Loteria room could not be found.")
                    return redirect(next_url)
                _get_accessible_loteria_room_or_404(request.user, room.pk, get_loteria_deck_config("kanto"))
            try:
                claim_count, total_ryo = claim_all_loteria_prizes(request.user, room=room)
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, f"Collected {claim_count} Loteria prize{'' if claim_count == 1 else 's'} for {total_ryo} Ryo.")
            return redirect(next_url)
        messages.error(request, "Unknown Loteria prize action.")
        return redirect(next_url)


class SilhouetteHubView(LoginRequiredMixin, TemplateView):
    """Tower selection hub for the silhouette arcade."""

    template_name = "game/silhouette_hub.html"

    def get(self, request, *args, **kwargs):
        from apps.users.guide_service import maybe_advance_from_url
        maybe_advance_from_url(request.user, "game:silhouette_hub")
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        candy_inventory = get_candy_inventory(self.request.user)
        run_state = get_silhouette_run_state(self.request.session)
        reveal_state = get_silhouette_reveal_state(self.request.session)
        current_key = None
        if reveal_state and reveal_state.get("tower_key"):
            current_key = reveal_state["tower_key"]
        elif run_state and run_state.get("tower_key"):
            current_key = run_state["tower_key"]

        tower_silhouettes = get_random_silhouette_species(len(get_silhouette_tower_catalog()))
        tower_cards = []
        for idx, tower in enumerate(get_silhouette_tower_catalog()):
            count = candy_inventory.get(tower.entry_candy_type, {}).get("count", 0)
            silhouette_species = tower_silhouettes[idx] if idx < len(tower_silhouettes) else None
            tower_cards.append(
                {
                    "config": tower,
                    "entry_count": count,
                    "can_enter": count >= tower.entry_qty,
                    "is_current": tower.key == current_key,
                    "silhouette_url": _pokemon_image_url(silhouette_species) if silhouette_species else "",
                }
            )

        active_tower = get_silhouette_tower_config(current_key) if current_key else None
        context.update(
            {
                "candy_inventory": candy_inventory,
                "tower_cards": tower_cards,
                "active_silhouette_tower": active_tower,
            }
        )
        return context


class SilhouetteTowerView(LoginRequiredMixin, TemplateView):
    """Single reusable silhouette tower screen."""

    template_name = "game/silhouette_tower.html"

    def dispatch(self, request, *args, **kwargs):
        self.tower_config = get_silhouette_tower_config(kwargs["tower_key"])
        if not self.tower_config.enabled:
            messages.info(request, f"{self.tower_config.title} is not open yet.")
            return redirect("game:home")
        self.species_map = get_tower_species_map(self.tower_config)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        if request.GET.get("advance") == "1":
            reveal_state = get_silhouette_reveal_state(request.session)
            tower_reveal = reveal_state if reveal_state and reveal_state.get("tower_key") == self.tower_config.key else None
            if tower_reveal and tower_reveal.get("status") == "correct" and tower_reveal.get("next_run_state"):
                try:
                    advance_silhouette_run(request.session, self.tower_config.key)
                except ValueError:
                    pass
            return redirect(reverse("game:silhouette_tower", kwargs={"tower_key": self.tower_config.key}))
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        run_state = get_silhouette_run_state(self.request.session)
        tower_run = run_state if run_state and run_state.get("tower_key") == self.tower_config.key else None
        reveal_state = get_silhouette_reveal_state(self.request.session)
        tower_reveal = reveal_state if reveal_state and reveal_state.get("tower_key") == self.tower_config.key else None
        candy_inventory = get_candy_inventory(self.request.user)

        question_card = None
        option_cards: list[dict] = []
        reveal_mode = False
        auto_advance = False
        answer_result = None
        floor_display = tower_run["current_floor"] if tower_run else 1
        cleared_count = len(tower_run["asked_dex_numbers"]) if tower_run else 0
        banked_ryo = tower_run["banked_ryo"] if tower_run else 0

        if tower_reveal:
            reveal_mode = True
            auto_advance = tower_reveal.get("status") == "correct" and bool(tower_reveal.get("next_run_state"))
            answer_result = tower_reveal
            floor_display = tower_reveal.get("floor_answered", 1)
            banked_ryo = tower_reveal.get("banked_ryo", 0)
            question_dex = tower_reveal.get("correct_dex")
            question_species = self.species_map.get(question_dex)
            if question_species:
                question_card = {
                    "dex": question_species.pokedex_number,
                    "name": question_species.name,
                    "image_url": _pokemon_image_url(question_species),
                    "reward": tower_reveal.get("reward", 0),
                }
            for dex in tower_reveal.get("option_dex_numbers", []):
                pokemon = self.species_map.get(dex)
                if pokemon is None:
                    continue
                option_cards.append(
                    {
                        "dex": pokemon.pokedex_number,
                        "name": pokemon.name,
                        "image_url": _pokemon_image_url(pokemon),
                        "is_correct": pokemon.pokedex_number == tower_reveal.get("correct_dex"),
                        "is_selected": pokemon.pokedex_number == tower_reveal.get("selected_dex"),
                    }
                )
            if tower_reveal.get("status") == "correct":
                cleared_count = max(0, floor_display)
            elif tower_reveal.get("status") == "cleared":
                cleared_count = self.tower_config.max_floors
            else:
                cleared_count = max(0, floor_display - 1)
        elif tower_run:
            question = tower_run.get("question") or {}
            question_dex = question.get("correct_dex")
            question_species = self.species_map.get(question_dex)
            if question_species:
                floor_index = int(tower_run["current_floor"]) - 1
                question_card = {
                    "dex": question_species.pokedex_number,
                    "name": question_species.name,
                    "image_url": _pokemon_image_url(question_species),
                    "reward": self.tower_config.floor_rewards[floor_index],
                }

            for dex in question.get("option_dex_numbers", []):
                pokemon = self.species_map.get(dex)
                if pokemon is None:
                    continue
                option_cards.append(
                    {
                        "dex": pokemon.pokedex_number,
                        "name": pokemon.name,
                        "image_url": _pokemon_image_url(pokemon),
                        "is_correct": False,
                        "is_selected": False,
                    }
                )

        context.update(
            {
                "tower": self.tower_config,
                "tower_run": tower_run,
                "tower_reveal": tower_reveal,
                "question_card": question_card,
                "option_cards": option_cards,
                "candy_inventory": candy_inventory,
                "species_count": self.tower_config.pool_size,
                "guess_background": f"images/games/guess_background_{((int(floor_display) - 1) % 6) + 1}.png" if (tower_run or tower_reveal) else "images/games/guess_background.png",
                "reveal_mode": reveal_mode,
                "auto_advance": auto_advance,
                "answer_result": answer_result,
                "floor_display": floor_display,
                "cleared_count": cleared_count,
                "banked_ryo_display": banked_ryo,
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action", "")
        run_state = get_silhouette_run_state(request.session)
        tower_run = run_state if run_state and run_state.get("tower_key") == self.tower_config.key else None
        reveal_state = get_silhouette_reveal_state(request.session)
        tower_reveal = reveal_state if reveal_state and reveal_state.get("tower_key") == self.tower_config.key else None
        return_url = reverse("game:silhouette_tower", kwargs={"tower_key": self.tower_config.key})

        if action == "start_run":
            try:
                start_silhouette_run(request.user, request.session, self.tower_config)
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(
                    request,
                    f"{self.tower_config.title} started. {self.tower_config.entry_qty} {self.tower_config.entry_label} spent.",
                )
            return redirect(return_url)

        if action == "cash_out":
            if not tower_run:
                messages.info(request, "There is no active tower run to cash out.")
                return redirect(return_url)
            payout = cash_out_silhouette_run(request.user, request.session, tower_run)
            current_floor = max(0, int(tower_run.get("current_floor", 1)))
            record_arcade_daily_progress(
                request.user,
                silhouette_run=True,
                silhouette_floor=current_floor,
                silhouette_cashout_3plus=current_floor >= 4,
            )
            messages.success(request, f"You cashed out {payout} Ryo from {self.tower_config.title}.")
            _quest_service.on_silhouette_played(request.user)
            return redirect(return_url)

        if action == "abandon":
            clear_silhouette_run_state(request.session)
            clear_silhouette_reveal_state(request.session)
            messages.info(request, "The current silhouette run was abandoned.")
            return redirect(return_url)

        if action == "advance":
            if not tower_reveal:
                return redirect(return_url)
            try:
                advance_silhouette_run(request.session, self.tower_config.key)
            except ValueError:
                pass
            return redirect(return_url)

        if action == "guess":
            if not tower_run or tower_reveal:
                messages.error(request, "Start a tower run before making a guess.")
                return redirect(return_url)
            try:
                selected_dex = int(request.POST.get("selected_dex", "0"))
            except ValueError:
                messages.error(request, "Choose one of the six options to answer.")
                return redirect(return_url)

            result = answer_silhouette_question(
                request.user,
                request.session,
                self.tower_config,
                tower_run,
                selected_dex,
            )
            correct_species = self.species_map.get(result["correct_dex"])
            correct_name = correct_species.name if correct_species else "that silhouette"

            if result["status"] == "cleared":
                record_arcade_daily_progress(
                    request.user,
                    silhouette_run=True,
                    silhouette_floor=int(tower_run.get("current_floor", 1)),
                )
                messages.success(request, f"Tower cleared! {correct_name} finished the climb. You earned {result['payout']} Ryo.")
                _quest_service.on_silhouette_played(request.user)
                from apps.users.achievement_service import AchievementService
                AchievementService().on_silhouette_cleared(request.user, self.tower_config.key)
            elif result["status"] == "wrong":
                record_arcade_daily_progress(
                    request.user,
                    silhouette_run=True,
                    silhouette_floor=int(tower_run.get("current_floor", 1)),
                )
                messages.error(request, f"Wrong. It was {correct_name}. You salvaged {result['payout']} Ryo from the run.")
                _quest_service.on_silhouette_played(request.user)
            return redirect(return_url)

        messages.error(request, "Unknown tower action.")
        return redirect(return_url)
