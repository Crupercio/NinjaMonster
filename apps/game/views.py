"""Class-based views for the game app."""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import (
    DetailView,
    FormView,
    ListView,
    TemplateView,
    View,
)

from .tutorial_service import STARTER_INFO, STARTER_NAMES, TutorialService

from apps.pokemon.models import OwnedPokemon

from .ai import BattleAIService
from .models import Battle, BattleSlot, BattleStatus, BattleTeam
from .services import BattleService

logger = logging.getLogger(__name__)

_battle_service = BattleService()
_ai_service = BattleAIService()


class HomeView(LoginRequiredMixin, TemplateView):
    """Landing page — shows stats, active events, and battle start options."""

    template_name = "game/home.html"

    def get_context_data(self, **kwargs):
        from apps.events.services import SeasonalEventService
        context = super().get_context_data(**kwargs)
        context["active_events"] = list(SeasonalEventService().get_active_events())
        return context


class BattleListView(LoginRequiredMixin, ListView):
    """List of the current user's active and past battles."""

    model = Battle
    template_name = "game/battle_list.html"
    context_object_name = "battles"
    paginate_by = 20

    def get_queryset(self):
        return (
            Battle.objects.filter(player_one=self.request.user)
            | Battle.objects.filter(player_two=self.request.user)
        ).select_related("player_one", "player_two", "winner").order_by("-created_at")


class BattleCreateView(LoginRequiredMixin, TemplateView):
    """Form to start a new PvP battle."""

    template_name = "game/battle_create.html"

    def post(self, request, *args, **kwargs):
        battle = _battle_service.create_battle(player_one=request.user)
        return redirect("game:team_select", battle_id=battle.pk)


class AIBattleCreateView(LoginRequiredMixin, TemplateView):
    """Create an AI battle — auto-loads saved team; falls back to manual selection."""

    template_name = "game/ai_battle_create.html"

    def post(self, request, *args, **kwargs):
        difficulty = request.POST.get("difficulty", "medium")
        if difficulty not in ("easy", "medium", "hard"):
            difficulty = "medium"

        ai_user = _ai_service.get_or_create_ai_user()
        battle = _battle_service.create_battle(
            player_one=request.user,
            player_two=ai_user,
            is_ai_battle=True,
            ai_difficulty=difficulty,
        )

        ai_pokemon_ids = _ai_service.build_ai_team_pokemon_ids()
        _battle_service.set_team(battle, ai_user, ai_pokemon_ids)

        # Try to auto-load the player's saved team; only show team-select on failure.
        if _battle_service.try_auto_load_player_team(battle, request.user):
            try:
                _battle_service.start_battle(battle)
            except ValueError:
                pass
            return redirect("game:battle_detail", pk=battle.pk)

        return redirect("game:team_select", battle_id=battle.pk)


class TeamSelectView(LoginRequiredMixin, TemplateView):
    """Select 6 Pokemon from the trainer's owned roster — first 4 active, last 2 bench.

    On GET: attempts to auto-load the player's saved team. If successful and both
    teams are ready, starts the battle and redirects immediately — the manual
    selection form is never shown.
    """

    template_name = "game/team_select.html"

    def get(self, request, *args, **kwargs):
        battle = Battle.objects.filter(pk=kwargs["battle_id"]).first()
        if battle and battle.status == BattleStatus.SETUP:
            # Only attempt auto-load if the player hasn't already set their team.
            player_team_exists = battle.teams.filter(owner=request.user).exists()
            if not player_team_exists:
                if _battle_service.try_auto_load_player_team(battle, request.user):
                    if battle.teams.count() >= 2:
                        try:
                            _battle_service.start_battle(battle)
                        except ValueError:
                            pass
                    return redirect("game:battle_detail", pk=battle.pk)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["owned_pokemon"] = (
            OwnedPokemon.objects.filter(owner=self.request.user)
            .select_related("species__primary_type", "species__secondary_type")
            .prefetch_related("species__moves")
            .order_by("species__pokedex_number", "species__name")
        )
        context["battle_id"] = kwargs["battle_id"]
        context["battle"] = Battle.objects.filter(pk=kwargs["battle_id"]).first()
        return context

    def post(self, request, *args, **kwargs):
        battle = get_object_or_404(Battle, pk=kwargs["battle_id"])
        owned_ids_raw = request.POST.getlist("owned_ids")

        try:
            owned_ids = [int(oid) for oid in owned_ids_raw]
        except (ValueError, TypeError):
            return self.render_to_response(
                self.get_context_data(error="Invalid Pokemon selection.", **kwargs)
            )

        try:
            _battle_service.set_team_from_owned(battle, request.user, owned_ids)
        except ValueError as exc:
            return self.render_to_response(
                self.get_context_data(error=str(exc), **kwargs)
            )

        if battle.teams.count() >= 2:
            try:
                _battle_service.start_battle(battle)
            except ValueError:
                pass

        return redirect("game:battle_detail", pk=battle.pk)


class BattleView(LoginRequiredMixin, DetailView):
    """Main battle page — 4v4 grid field, HP bars, move buttons, clickable targeting."""

    model = Battle
    template_name = "game/battle_detail.html"
    context_object_name = "battle"

    def get_queryset(self):
        return Battle.objects.select_related(
            "player_one", "player_two", "winner"
        ).prefetch_related(
            "teams__slots__pokemon__primary_type",
            "teams__slots__pokemon__secondary_type",
            "teams__slots__pokemon__moves__applies_status",
            "teams__slots__pokemon__moves__trigger_status",
            "teams__slots__owned_pokemon__move_standard__applies_status",
            "teams__slots__owned_pokemon__move_standard__trigger_status",
            "teams__slots__owned_pokemon__move_chase__applies_status",
            "teams__slots__owned_pokemon__move_chase__trigger_status",
            "teams__slots__owned_pokemon__move_special__applies_status",
            "teams__slots__owned_pokemon__move_special__trigger_status",
            "teams__slots__owned_pokemon__move_support__applies_status",
            "teams__slots__owned_pokemon__move_support__trigger_status",
            "teams__slots__owned_pokemon__move_passive",
            "teams__slots__active_statuses__status",
            "teams__slots__move_cooldowns__move",
            "teams__slots__selected_move",
            "teams__slots__selected_target",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        battle = self.object

        state = _battle_service.get_battle_state(battle)
        context.update(state)

        for team in state["teams"]:
            if team.owner == self.request.user:
                context["player_team"] = team
            else:
                context["opponent_team"] = team

        context["is_ai_battle"] = battle.is_ai_battle
        context["ai_difficulty"] = battle.ai_difficulty
        context["combo_logs"] = list(
            battle.logs.filter(log_type="combo").order_by("-created_at")[:10]
        )

        # Build cooldown lookup: {slot_pk: {move_pk: remaining_rounds}}
        player_team = context.get("player_team")
        if player_team:
            cooldown_map: dict[int, dict[int, int]] = {}
            for slot in player_team.slots.all():
                cooldown_map[slot.pk] = {
                    cd.move_id: cd.remaining_rounds
                    for cd in slot.move_cooldowns.all()
                }
            context["cooldown_map"] = cooldown_map

            # Separate active and bench slots
            active_slots = [s for s in player_team.slots.all() if s.is_active]
            bench_slots = [s for s in player_team.slots.all() if not s.is_active]
            context["player_active_slots"] = active_slots
            context["player_bench_slots"] = bench_slots

        if context.get("opponent_team"):
            opp_active = [s for s in context["opponent_team"].slots.all() if s.is_active]
            opp_bench = [s for s in context["opponent_team"].slots.all() if not s.is_active]
            context["opponent_active_slots"] = opp_active
            context["opponent_bench_slots"] = opp_bench

        # Check if substitution is needed (active slot fainted, bench alive)
        context["substitution_needed"] = False
        if player_team and battle.status == BattleStatus.ACTIVE:
            fainted_active = [
                s for s in player_team.slots.all()
                if s.is_active and s.is_fainted
            ]
            bench_alive = [
                s for s in player_team.slots.all()
                if not s.is_active and not s.is_fainted
            ]
            if fainted_active and bench_alive:
                context["substitution_needed"] = True
                context["fainted_active_slots"] = fainted_active
                context["bench_alive_slots"] = bench_alive

        return context


class BattleActionView(LoginRequiredMixin, FormView):
    """Submit turn actions for the current round. Auto-generates AI actions if AI battle."""

    template_name = "game/battle_action.html"

    def get_success_url(self):
        return reverse_lazy("game:battle_detail", kwargs={"pk": self.kwargs["pk"]})

    def post(self, request, *args, **kwargs):
        battle = get_object_or_404(Battle, pk=kwargs["pk"], status=BattleStatus.ACTIVE)

        # Identify player's team
        player_team = battle.teams.filter(owner=request.user).first()
        if player_team is None:
            return redirect(self.get_success_url())

        # Parse per-slot submissions: move_{slot_pk}, target_{slot_pk}, switch_{slot_pk}
        submitted: dict[int, dict] = {}
        switches: dict[int, int] = {}
        for key, value in request.POST.items():
            if key.startswith("switch_"):
                try:
                    active_slot_id = int(key[7:])
                    switches[active_slot_id] = int(value)
                except (ValueError, TypeError):
                    pass
            elif key.startswith("move_"):
                try:
                    slot_id = int(key[5:])
                    submitted.setdefault(slot_id, {})["move_id"] = int(value)
                except (ValueError, TypeError):
                    pass
            elif key.startswith("target_"):
                try:
                    slot_id = int(key[7:])
                    submitted.setdefault(slot_id, {})["target_id"] = int(value)
                except (ValueError, TypeError):
                    pass

        # Process voluntary bench switches BEFORE round execution (GDD §5.6).
        # Switched slots pass their attack turn — exclude them from player_actions.
        switched_slot_ids: set[int] = set()
        for active_slot_id, bench_slot_id in switches.items():
            try:
                active_slot = BattleSlot.objects.get(pk=active_slot_id, team=player_team)
                bench_slot = BattleSlot.objects.get(pk=bench_slot_id, team=player_team)
                _battle_service.bench_switch(battle, player_team, active_slot, bench_slot)
                switched_slot_ids.add(active_slot_id)
            except BattleSlot.DoesNotExist:
                pass
            except ValueError as exc:
                logger.warning("Bench switch error in Battle #%d: %s", battle.pk, exc)

        # Remove switched slots from submitted so they don't contribute an action.
        for sid in switched_slot_ids:
            submitted.pop(sid, None)

        player_actions = _battle_service.prepare_player_actions(
            battle, player_team, submitted
        )

        if not player_actions:
            return redirect(self.get_success_url())

        if battle.is_ai_battle:
            opponent_actions = _ai_service.get_ai_actions(battle)
        else:
            opponent_actions = []

        try:
            _battle_service.execute_round(battle, player_actions, opponent_actions)
        except ValueError as exc:
            logger.warning("Round execution error in Battle #%d: %s", battle.pk, exc)

        battle.refresh_from_db()
        self._broadcast_battle_state(battle)

        return redirect(self.get_success_url())

    def _broadcast_battle_state(self, battle: Battle) -> None:
        """Send the updated battle state to the battle's channel group."""
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return

        state = _battle_service.get_battle_state(battle)
        teams_data = []
        for team in state["teams"]:
            slots_data = []
            for slot in team.slots.all():
                statuses = [
                    {"name": a.status.name, "display": a.status.get_name_display()}
                    for a in slot.active_statuses.select_related("status").all()
                ]
                cooldowns = {
                    cd.move_id: cd.remaining_rounds
                    for cd in slot.move_cooldowns.all()
                }
                slots_data.append({
                    "pk": slot.pk,
                    "pokemon_name": slot.pokemon.name,
                    "current_hp": slot.current_hp,
                    "max_hp": slot.max_hp,
                    "hp_percentage": slot.hp_percentage,
                    "is_fainted": slot.is_fainted,
                    "is_active": slot.is_active,
                    "grid_position": slot.grid_position,
                    "statuses": statuses,
                    "cooldowns": cooldowns,
                    "selected_move_id": slot.selected_move_id,
                    "selected_target_id": slot.selected_target_id,
                })
            teams_data.append({
                "pk": team.pk,
                "owner": str(team.owner),
                "slots": slots_data,
            })

        combo_logs = [
            {"message": log.message, "chain_total": log.chain_total}
            for log in battle.logs.filter(log_type="combo").order_by("-created_at")[:10]
        ]

        payload = {
            "battle_pk": battle.pk,
            "current_round": battle.current_round,
            "status": battle.status,
            "winner": str(battle.winner) if battle.winner else None,
            "max_combo_chain": battle.max_combo_chain,
            "teams": teams_data,
            "combo_logs": combo_logs,
        }

        group_name = f"battle_{battle.pk}"
        if battle.status == "finished":
            async_to_sync(channel_layer.group_send)(group_name, {
                "type": "battle_end",
                "winner": payload["winner"],
                "max_combo_chain": payload["max_combo_chain"],
            })
        else:
            async_to_sync(channel_layer.group_send)(group_name, {
                "type": "battle_update",
                "payload": payload,
            })


class SubstituteView(LoginRequiredMixin, View):
    """Swap a fainted active slot with an alive bench slot before the next round."""

    def post(self, request, *args, **kwargs):
        battle = get_object_or_404(Battle, pk=kwargs["pk"], status=BattleStatus.ACTIVE)
        player_team = get_object_or_404(BattleTeam, battle=battle, owner=request.user)

        try:
            fainted_slot_id = int(request.POST["fainted_slot_id"])
            bench_slot_id = int(request.POST["bench_slot_id"])
        except (KeyError, ValueError, TypeError):
            return redirect("game:battle_detail", pk=battle.pk)

        try:
            fainted_slot = BattleSlot.objects.get(pk=fainted_slot_id, team=player_team)
            bench_slot = BattleSlot.objects.get(pk=bench_slot_id, team=player_team)
        except BattleSlot.DoesNotExist:
            return redirect("game:battle_detail", pk=battle.pk)

        try:
            _battle_service.substitute_pokemon(battle, player_team, fainted_slot, bench_slot)
        except ValueError as exc:
            logger.warning("Substitution error in Battle #%d: %s", battle.pk, exc)

        return redirect("game:battle_detail", pk=battle.pk)


class BattleLogView(LoginRequiredMixin, DetailView):
    """Full battle log replay view."""

    model = Battle
    template_name = "game/battle_log.html"
    context_object_name = "battle"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["logs"] = self.object.logs.select_related().order_by("created_at")
        context["combo_logs"] = [
            log for log in context["logs"] if log.log_type == "combo"
        ]
        return context


# ── Tutorial views ───────────────────────────────────────────────────────────

class TutorialView(LoginRequiredMixin, View):
    """Entry point: skip to home if tutorial is already complete."""

    def get(self, request, *args, **kwargs):
        if request.user.tutorial_complete:
            return redirect("game:home")
        return redirect("game:tutorial_starter_select")


class TutorialStarterSelectView(LoginRequiredMixin, TemplateView):
    """Select one of the three starter Pokemon to begin the tutorial."""

    template_name = "game/tutorial_starter_select.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["starters"] = STARTER_INFO
        return context

    def post(self, request, *args, **kwargs):
        starter_name = request.POST.get("starter", "")
        if starter_name not in STARTER_NAMES:
            return self.render_to_response(
                self.get_context_data(error="Please select a valid starter.")
            )

        tutorial_svc = TutorialService()
        try:
            owned_pks = tutorial_svc.assign_starter_team(request.user, starter_name)
            battle = tutorial_svc.create_tutorial_battle(request.user, owned_pks)
        except ValueError as exc:
            return self.render_to_response(
                self.get_context_data(error=str(exc))
            )

        return redirect("game:battle_detail", pk=battle.pk)


# ── Spectator views ──────────────────────────────────────────────────────────

class ActiveBattleListView(LoginRequiredMixin, ListView):
    """List of all currently active battles available to spectate (GDD §20.15)."""

    model = Battle
    template_name = "game/spectate_list.html"
    context_object_name = "battles"
    paginate_by = 20

    def get_queryset(self):
        return (
            Battle.objects.filter(status=BattleStatus.ACTIVE, is_tutorial=False)
            .select_related("player_one", "player_two")
            .order_by("-current_round", "-created_at")
        )


class SpectatorView(LoginRequiredMixin, DetailView):
    """Read-only battle view for spectators (GDD §20.15)."""

    model = Battle
    template_name = "game/spectate.html"
    context_object_name = "battle"

    def get_queryset(self):
        return Battle.objects.filter(
            status=BattleStatus.ACTIVE
        ).select_related(
            "player_one", "player_two", "winner"
        ).prefetch_related(
            "teams__slots__pokemon__primary_type",
            "teams__slots__pokemon__secondary_type",
            "teams__slots__active_statuses__status",
            "teams__slots__move_cooldowns__move",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        battle = self.object
        state = _battle_service.get_battle_state(battle)
        context.update(state)

        for team in state["teams"]:
            if team.owner == battle.player_one:
                context["team_one"] = team
            else:
                context["team_two"] = team

        context["team_one_active"] = [
            s for s in context.get("team_one", battle.teams.first()).slots.all()
            if s.is_active
        ] if context.get("team_one") else []
        context["team_two_active"] = [
            s for s in context.get("team_two", battle.teams.last()).slots.all()
            if s.is_active
        ] if context.get("team_two") else []

        context["combo_logs"] = list(
            battle.logs.filter(log_type="combo").order_by("-created_at")[:10]
        )
        return context


class TutorialCompleteView(LoginRequiredMixin, TemplateView):
    """Celebration page shown after winning the tutorial battle."""

    template_name = "game/tutorial_complete.html"

    def get(self, request, *args, **kwargs):
        user = request.user
        if not user.tutorial_complete:
            user.tutorial_complete = True
            user.save(update_fields=["tutorial_complete"])
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["starter_name"] = self.request.user.tutorial_starter or "your starter"
        context["starter_info"] = STARTER_INFO.get(
            self.request.user.tutorial_starter or "", {}
        )
        return context
