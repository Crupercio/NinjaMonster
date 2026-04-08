"""Class-based views for the pokemon app."""
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from apps.users.services import award_ryo, sell_value_for_level

from .models import OwnedPokemon, Pokemon, PokemonType, Team, TeamSlot
from .services import claim_training, create_owned_pokemon, start_training, stop_training
from .type_chart import ALL_TYPES, TYPE_COLORS, build_chart_matrix, get_effectiveness

logger = logging.getLogger(__name__)


class PokedexView(ListView):
    """Display all Pokemon with optional type filtering."""

    model = Pokemon
    template_name = "pokemon/pokedex.html"
    context_object_name = "pokemon_list"
    paginate_by = 24

    def get_queryset(self):
        qs = Pokemon.objects.select_related("primary_type", "secondary_type").order_by(
            "pokedex_number", "name"
        )
        type_filter = self.request.GET.get("type", "").strip()
        if type_filter:
            qs = qs.by_type(type_filter)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["types"] = PokemonType.objects.order_by("name")
        context["selected_type"] = self.request.GET.get("type", "")
        return context


class PokemonDetailView(DetailView):
    """Show a single Pokemon with its stats, moves, and combo potential."""

    model = Pokemon
    template_name = "pokemon/pokemon_detail.html"
    context_object_name = "pokemon"

    _SLOT_LABELS: tuple[tuple[str, str], ...] = (
        ("standard", "Basic Technique"),
        ("chase", "Chase Technique"),
        ("special", "Secret Technique"),
        ("support", "Support Technique"),
        ("passive", "Ninja Trait"),
    )

    def get_queryset(self):
        return Pokemon.objects.select_related(
            "primary_type", "secondary_type"
        ).prefetch_related(
            "move_pool__move__move_type",
            "move_pool__move__applies_status",
            "move_pool__move__trigger_status",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pool_entries = list(self.object.move_pool.all())

        # Group by slot_type preserving display order.
        by_slot: dict[str, list] = {slot: [] for slot, _ in self._SLOT_LABELS}
        combo_moves: list = []
        for entry in pool_entries:
            by_slot.setdefault(entry.slot_type, []).append(entry.move)
            if entry.move.applies_status or entry.move.trigger_status:
                combo_moves.append(entry.move)

        context["move_pool_by_slot"] = [
            (label, by_slot[slot]) for slot, label in self._SLOT_LABELS
        ]
        context["combo_moves"] = combo_moves
        context["is_battle_ready"] = self.object.is_battle_ready
        return context


class MyPokemonView(LoginRequiredMixin, TemplateView):
    """Show the logged-in trainer's full Pokemon roster with level, EXP, and training toggle."""

    template_name = "pokemon/my_pokemon.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["owned_pokemon"] = (
            OwnedPokemon.objects.filter(owner=self.request.user)
            .select_related("species__primary_type", "species__secondary_type")
            .order_by("species__pokedex_number", "species__name")
        )
        return context

    def post(self, request, *args, **kwargs):
        """Handle training form submissions: start, cancel, or claim."""
        owned_id = request.POST.get("owned_id")
        action = request.POST.get("action")  # "start" | "cancel" | "claim"

        try:
            owned = OwnedPokemon.objects.select_related("species").get(
                pk=owned_id, owner=request.user
            )
        except OwnedPokemon.DoesNotExist:
            return self.render_to_response(
                self.get_context_data(error="Pokemon not found.")
            )

        error = None
        if action == "start":
            try:
                duration = int(request.POST.get("duration", 30))
                start_training(owned, duration_minutes=duration)
            except ValueError as exc:
                error = str(exc)
        elif action == "cancel":
            stop_training(owned)
        elif action == "claim":
            try:
                claim_training(owned)
            except ValueError as exc:
                error = str(exc)

        if error:
            return self.render_to_response(self.get_context_data(error=error))
        return redirect("pokemon:my_pokemon")


def _build_combo_preview(owned_pokemon_list: list) -> list[dict]:
    """
    Analyse a list of OwnedPokemon and return all combo chain links present.

    Each link dict:
      {
        "from_name": str,          # attacker species name
        "from_move": str,          # move that applies the status
        "status_name": str,        # the status being applied
        "to_name": str,            # triggered pokemon species name
        "to_move": str,            # chase move that fires
        "amp": str,                # e.g. "×1.10"
      }

    Only OwnedPokemon with all four move slots assigned are considered
    (they must be battle-ready).
    """
    from apps.game.services import COMBO_AMP

    # Gather pokemon that have a chase move with trigger_status
    links: list[dict] = []

    for op in owned_pokemon_list:
        # Skip pokemon without all required moves
        if not (op.move_standard and op.move_chase and op.move_special and op.move_support):
            continue

        # Does this pokemon's standard/special/support move apply a status?
        for applier_move in (op.move_standard, op.move_special, op.move_support):
            if applier_move is None or applier_move.applies_status_id is None:
                continue
            applied_status = applier_move.applies_status

            # Find other team members whose chase move triggers on that status
            for other_op in owned_pokemon_list:
                if other_op.pk == op.pk:
                    continue
                if not (other_op.move_chase and other_op.move_chase.trigger_status_id is not None):
                    continue
                if other_op.move_chase.trigger_status_id != applied_status.pk:
                    continue

                # Link 2 is always ×1.10 (the first triggered link)
                amp = f"×{COMBO_AMP[1]:.2f}"

                links.append({
                    "from_name": op.species.name,
                    "from_move": str(applier_move),
                    "status_name": applied_status.name,
                    "to_name": other_op.species.name,
                    "to_move": str(other_op.move_chase),
                    "amp": amp,
                })

    return links


class TeamView(LoginRequiredMixin, TemplateView):
    """Show the trainer's persistent 6-slot team with assign/remove controls."""

    template_name = "pokemon/team.html"

    def get_context_data(self, **kwargs: object) -> dict:
        context = super().get_context_data(**kwargs)
        team = Team.get_team(self.request.user)
        team_slots = list(
            team.slots.select_related(
                "pokemon__species__primary_type",
                "pokemon__species__secondary_type",
                "pokemon__move_standard__applies_status",
                "pokemon__move_chase__trigger_status",
                "pokemon__move_special__applies_status",
                "pokemon__move_support__applies_status",
            )
        )
        slots_by_position = {s.position: s for s in team_slots}
        context["team"] = team
        context["slots"] = [
            {"position": i, "slot": slots_by_position.get(i)}
            for i in range(1, 7)
        ]

        # Combo chain preview — only for filled slots
        owned_pokemon = [s.pokemon for s in team_slots if s.pokemon is not None]
        context["combo_links"] = _build_combo_preview(owned_pokemon)
        return context


class TeamSlotPickerView(LoginRequiredMixin, TemplateView):
    """
    GET  /team/slot/<position>/  — show Pokemon picker for that slot.
    POST /team/slot/<position>/  — assign or remove Pokemon from that slot.
    """

    template_name = "pokemon/team_slot_picker.html"

    def _get_team_and_position(self) -> tuple["Team", int]:
        position = int(self.kwargs["position"])
        if not 1 <= position <= 6:
            raise Http404("Invalid slot position.")
        return Team.get_team(self.request.user), position

    def get_context_data(self, **kwargs: object) -> dict:
        context = super().get_context_data(**kwargs)
        team, position = self._get_team_and_position()
        assigned_ids = set(team.slots.values_list("pokemon_id", flat=True))
        current_slot = team.slots.filter(position=position).first()
        current_pokemon_id = current_slot.pokemon_id if current_slot else None
        available = list(
            OwnedPokemon.objects.filter(owner=self.request.user).select_related(
                "species__primary_type", "species__secondary_type"
            )
        )
        for op in available:
            op.is_current = op.pk == current_pokemon_id
            op.is_assigned = op.pk in assigned_ids and not op.is_current
        context["team"] = team
        context["position"] = position
        context["current_slot"] = current_slot
        context["available_pokemon"] = available
        return context

    def post(self, request, *args: object, **kwargs: object):
        team, position = self._get_team_and_position()
        action = request.POST.get("action")

        if action == "remove":
            team.slots.filter(position=position).delete()
            return redirect("pokemon:team")

        owned_id = request.POST.get("owned_id")
        if owned_id:
            try:
                owned = OwnedPokemon.objects.get(pk=owned_id, owner=request.user)
            except OwnedPokemon.DoesNotExist:
                return redirect("pokemon:team")
            # If this Pokemon is already in another slot, move it
            team.slots.filter(pokemon=owned).delete()
            TeamSlot.objects.update_or_create(
                team=team,
                position=position,
                defaults={"pokemon": owned},
            )

        return redirect("pokemon:team")


class SellPokemonView(LoginRequiredMixin, View):
    """POST /pokemon/my/<pk>/sell/ — sell an owned Pokémon for Ryo."""

    def post(self, request, pk: int):
        try:
            owned = OwnedPokemon.objects.select_related("species").get(
                pk=pk, owner=request.user
            )
        except OwnedPokemon.DoesNotExist:
            return redirect("pokemon:my_pokemon")

        if owned.is_training:
            return redirect("/pokemon/my/?error=Cannot+sell+a+Pokemon+that+is+training.")

        # Prevent selling a Pokemon assigned to the persistent team
        team = Team.get_team(request.user)
        if team.slots.filter(pokemon=owned).exists():
            return redirect(
                f"/pokemon/my/?error=Remove+{owned.species.name}+from+your+team+first."
            )

        value = sell_value_for_level(owned.level)
        name = owned.species.name
        owned.delete()
        award_ryo(request.user, value)
        logger.info(
            "User '%s' sold %s for %d Ryo.", request.user, name, value
        )
        return redirect(f"/pokemon/my/?sold={name}&ryo={value}")


class CatchPokemonView(LoginRequiredMixin, View):
    """POST /pokemon/<pk>/catch/ — add a wild Pokémon to the trainer's roster."""

    def post(self, request, pk: int):
        species = get_object_or_404(Pokemon, pk=pk)
        owned = create_owned_pokemon(owner=request.user, species=species)
        logger.info(
            "User '%s' caught %s (owned_pk=%s).",
            request.user,
            species.name,
            owned.pk,
        )
        return redirect("pokemon:owned_detail", pk=owned.pk)


class OwnedPokemonDetailView(LoginRequiredMixin, DetailView):
    """Show a trainer's owned Pokemon with level-scaled stats and assigned moves."""

    model = OwnedPokemon
    template_name = "pokemon/owned_pokemon_detail.html"
    context_object_name = "owned"

    def get_queryset(self):
        return OwnedPokemon.objects.filter(owner=self.request.user).select_related(
            "species__primary_type",
            "species__secondary_type",
            "move_standard__move_type",
            "move_chase__move_type",
            "move_special__move_type",
            "move_support__move_type",
            "move_passive__move_type",
            "move_standard__applies_status",
            "move_chase__applies_status",
            "move_special__applies_status",
            "move_support__applies_status",
            "move_passive__applies_status",
        )

    def get_context_data(self, **kwargs: object) -> dict:
        context = super().get_context_data(**kwargs)
        op = self.object
        sp = op.species
        lv = op.level
        context["stats"] = [
            ("HP", sp.calculate_max_hp(lv), sp.base_hp),
            ("Attack", sp.calculate_stat(sp.base_attack, lv), sp.base_attack),
            ("Defense", sp.calculate_stat(sp.base_defense, lv), sp.base_defense),
            ("Sp. Atk", sp.calculate_stat(sp.base_sp_attack, lv), sp.base_sp_attack),
            ("Sp. Def", sp.calculate_stat(sp.base_sp_defense, lv), sp.base_sp_defense),
            ("Speed", sp.calculate_stat(sp.base_speed, lv), sp.base_speed),
        ]
        context["move_slots"] = [
            ("Basic Technique", "standard", op.move_standard),
            ("Chase Technique", "chase", op.move_chase),
            ("Secret Technique", "special", op.move_special),
            ("Support Technique", "support", op.move_support),
            ("Ninja Trait", "passive", op.move_passive),
        ]
        return context


class TypeChartView(TemplateView):
    """
    Full 18×18 type effectiveness chart, accessible from the Pokedex and Team Builder.

    GET /pokemon/types/
    GET /pokemon/types/?focus=Fire  — pre-highlight a specific type column/row
    """

    template_name = "pokemon/type_chart.html"

    def get_context_data(self, **kwargs: object) -> dict:
        context = super().get_context_data(**kwargs)
        context["chart"] = build_chart_matrix()
        context["all_types"] = ALL_TYPES
        context["type_colors"] = TYPE_COLORS
        focus = self.request.GET.get("focus", "").strip().title()
        context["focus_type"] = focus if focus in ALL_TYPES else ""

        # Per-type detail for the focused type (strengths / weaknesses / immunities)
        if context["focus_type"]:
            ft = context["focus_type"]
            context["focus_detail"] = {
                "super_effective_vs": [d for d in ALL_TYPES if get_effectiveness(ft, d) == 2.0],
                "not_very_vs":        [d for d in ALL_TYPES if get_effectiveness(ft, d) == 0.5],
                "immune_vs":          [d for d in ALL_TYPES if get_effectiveness(ft, d) == 0.0],
                "weak_to":            [a for a in ALL_TYPES if get_effectiveness(a, ft) == 2.0],
                "resists":            [a for a in ALL_TYPES if get_effectiveness(a, ft) == 0.5],
                "immune_to":          [a for a in ALL_TYPES if get_effectiveness(a, ft) == 0.0],
            }
        return context
