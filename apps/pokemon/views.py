"""Class-based views for the pokemon app."""
import json
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Min
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from apps.users.services import award_ryo, sell_value_for_level

from .models import Generation, OwnedPokemon, Pokemon, PokemonType, Team, TeamSlot
from .services import claim_training, create_owned_pokemon, start_training, stop_training
from .type_chart import ALL_TYPES, TYPE_COLORS, build_chart_matrix, get_effectiveness

logger = logging.getLogger(__name__)


class PokedexView(ListView):
    """Display all Pokemon. Filtering is handled client-side via Alpine.js."""

    model = Pokemon
    template_name = "pokemon/pokedex.html"
    context_object_name = "pokemon_list"
    # No server-side pagination — Alpine.js handles instant client-side filtering.

    def get_queryset(self):
        return (
            Pokemon.objects.select_related("primary_type", "secondary_type")
            .prefetch_related("generation_sources")
            .annotate(primary_gen=Min("generation_sources__number"))
            .order_by("pokedex_number", "name")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["types"] = PokemonType.objects.order_by("name")
        context["generations"] = Generation.objects.order_by("number")
        context["type_colors"] = TYPE_COLORS
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

        # Pairing hints -------------------------------------------------------
        # statuses this species can APPLY (via standard/mystery moves)
        applies_ids = {
            m.applies_status_id
            for m in combo_moves
            if m.applies_status_id and m.slot_type in ("standard", "mystery", "passive_1", "passive_2")
        }
        # statuses this species can CHASE (via chase moves)
        triggers_on_ids = {
            m.trigger_status_id
            for m in combo_moves
            if m.trigger_status_id and m.slot_type == "chase"
        }

        pairing_hints: list[dict] = []

        if applies_ids:
            # Find other species whose CHASE move triggers on a status we apply
            from apps.pokemon.models import SpeciesMovePool  # local import
            chase_partners = (
                SpeciesMovePool.objects
                .filter(slot_type="chase", move__trigger_status_id__in=applies_ids)
                .exclude(species=self.object)
                .select_related("species", "move__trigger_status")
                .distinct()
            )
            for entry in chase_partners[:6]:
                pairing_hints.append({
                    "role": "primer",
                    "partner": entry.species,
                    "detail": f"This Pokemon primes {entry.move.trigger_status.get_name_display()} \u2192 {entry.species.name} can chain",
                })

        if triggers_on_ids:
            # Find other species whose STANDARD move applies a status we chase
            from apps.pokemon.models import SpeciesMovePool  # local import (already imported above if applies_ids set)
            primer_partners = (
                SpeciesMovePool.objects
                .filter(slot_type__in=("standard", "mystery", "passive_1", "passive_2"), move__applies_status_id__in=triggers_on_ids)
                .exclude(species=self.object)
                .select_related("species", "move__applies_status")
                .distinct()
            )
            for entry in primer_partners[:6]:
                pairing_hints.append({
                    "role": "chaser",
                    "partner": entry.species,
                    "detail": f"{entry.species.name} applies {entry.move.applies_status.get_name_display()} \u2192 this Pokemon chains",
                })

        context["pairing_hints"] = pairing_hints

        # Expedition zones where this species can be encountered
        from apps.expedition.models import ZoneSpawnEntry
        context["spawn_zones"] = (
            ZoneSpawnEntry.objects
            .filter(species=self.object, zone__is_active=True)
            .select_related("zone")
            .order_by("zone__order")
        )
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
            "move_chase__trigger_status",
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
            ("Ninjutsu", sp.calculate_stat(sp.base_ninjutsu, lv), sp.base_ninjutsu),
            ("Sp. Def", sp.calculate_stat(sp.base_sp_defense, lv), sp.base_sp_defense),
            ("Initiative", sp.calculate_stat(sp.base_initiative, lv), sp.base_initiative),
        ]
        context["move_slots"] = [
            ("Basic Technique", "standard", op.move_standard),
            ("Chase Technique", "chase", op.move_chase),
            ("Mystery", "mystery", op.move_special),
            ("Passive 1", "passive_1", op.move_support),
            ("Passive 2", "passive_2", op.move_passive),
        ]

        # Combo synergy hints based on this pokemon's equipped moves
        from apps.pokemon.models import SpeciesMovePool  # local import

        # Statuses this pokemon APPLIES (standard / mystery moves with applies_status)
        applies_ids = {
            m.applies_status_id
            for m in (op.move_standard, op.move_special, op.move_support)
            if m is not None and m.applies_status_id
        }
        # Status this pokemon CHASES (chase move trigger_status)
        triggers_on_ids = {
            op.move_chase.trigger_status_id
        } if op.move_chase and op.move_chase.trigger_status_id else set()

        pairing_hints: list[dict] = []

        if applies_ids:
            chase_partners = (
                SpeciesMovePool.objects
                .filter(slot_type="chase", move__trigger_status_id__in=applies_ids)
                .exclude(species=sp)
                .select_related("species__primary_type", "move__trigger_status")
                .distinct()
            )
            for entry in chase_partners[:6]:
                pairing_hints.append({
                    "role": "primer",
                    "partner": entry.species,
                    "detail": f"Primes {entry.move.trigger_status.get_name_display()} \u2192 {entry.species.name} chains",
                })

        if triggers_on_ids:
            primer_partners = (
                SpeciesMovePool.objects
                .filter(
                    slot_type__in=("standard", "mystery", "passive_1", "passive_2"),
                    move__applies_status_id__in=triggers_on_ids,
                )
                .exclude(species=sp)
                .select_related("species__primary_type", "move__applies_status")
                .distinct()
            )
            for entry in primer_partners[:6]:
                pairing_hints.append({
                    "role": "chaser",
                    "partner": entry.species,
                    "detail": f"{entry.species.name} applies {entry.move.applies_status.get_name_display()} \u2192 you chain",
                })

        context["pairing_hints"] = pairing_hints
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


class ComboAtlasView(TemplateView):
    """Public page showing the full combo chain matrix — which moves/statuses link to which chasers."""

    template_name = "pokemon/combo_atlas.html"

    # All statuses that exist in the game but have no moves assigned yet
    _PLANNED_STATUSES: list[dict] = [
        # --- Missing chasers (primers exist, nothing to chase them) ---
        {"name": "Asleep",   "key": "asleep",   "gap": "chasers", "primers": 27, "chasers": 0,
         "note": "27 Pokémon can put targets to sleep but no chase moves trigger on it yet."},
        {"name": "Flinched", "key": "flinched", "gap": "chasers", "primers": 66, "chasers": 0,
         "note": "66 Pokémon cause flinch but no chase moves follow up on it yet."},
        {"name": "Seeded",   "key": "seeded",   "gap": "chasers", "primers": 53, "chasers": 0,
         "note": "53 Pokémon can seed targets but no chase moves trigger on it yet."},
        # --- Missing primers (chasers exist, nothing to start the chain) ---
        {"name": "Bound",    "key": "bound",    "gap": "primers", "primers": 0,  "chasers": 53,
         "note": "53 chase moves trigger on Bound but no standard moves apply it yet."},
        # --- Physical states (combo infrastructure exists, no moves assigned) ---
        {"name": "Airborne",  "key": "airborne",  "gap": "both", "primers": 0, "chasers": 0,
         "note": "Launch mechanic designed; no moves assign Airborne or chase it yet."},
        {"name": "Launched",  "key": "launched",  "gap": "both", "primers": 0, "chasers": 0,
         "note": "Juggle mechanic designed; no moves assign Launched or chase it yet."},
        {"name": "Knockback", "key": "knockback", "gap": "both", "primers": 0, "chasers": 0,
         "note": "Knockback mechanic designed; no moves assigned yet."},
        {"name": "Grounded",  "key": "grounded",  "gap": "both", "primers": 0, "chasers": 0,
         "note": "Ground-state chase mechanic designed; no moves assigned yet."},
        # --- Naruto statuses (no moves at all) ---
        {"name": "Ignited",      "key": "ignited",      "gap": "both", "primers": 0, "chasers": 0,
         "note": "Naruto-inspired DOT + heal-disable. No moves assign or chase it yet."},
        {"name": "Immobile",     "key": "immobile",     "gap": "both", "primers": 0, "chasers": 0,
         "note": "Full turn-loss effect. No moves assign or chase it yet."},
        {"name": "Chaos",        "key": "chaos",        "gap": "both", "primers": 0, "chasers": 0,
         "note": "Friendly-fire confusion variant. No moves assigned yet."},
        {"name": "Blinded",      "key": "blinded",      "gap": "both", "primers": 0, "chasers": 0,
         "note": "Blocks standard attacks. No moves assigned yet."},
        {"name": "Acupunctured", "key": "acupunctured", "gap": "both", "primers": 0, "chasers": 0,
         "note": "Blocks mystery moves. No moves assigned yet."},
        {"name": "Imprisoned",   "key": "imprisoned",   "gap": "both", "primers": 0, "chasers": 0,
         "note": "Punishes special move use. No moves assigned yet."},
        {"name": "Tagged",       "key": "tagged",       "gap": "both", "primers": 0, "chasers": 0,
         "note": "Defense -30%, enables special combo triggers. No moves assigned yet."},
        {"name": "Enfeebled",    "key": "enfeebled",    "gap": "both", "primers": 0, "chasers": 0,
         "note": "Attack + Sp.Atk halved. No moves assigned yet."},
        {"name": "Weakened",     "key": "weakened",     "gap": "both", "primers": 0, "chasers": 0,
         "note": "All damage output halved. No moves assigned yet."},
        {"name": "Corroded",     "key": "corroded",     "gap": "both", "primers": 0, "chasers": 0,
         "note": "Strips Sp.Defense, worsens each turn. No moves assigned yet."},
        {"name": "Interrupted",  "key": "interrupted",  "gap": "both", "primers": 0, "chasers": 0,
         "note": "Cancels current move, wastes the turn. No moves assigned yet."},
        # --- Other volatile statuses with no moves ---
        {"name": "Badly Poisoned", "key": "badly_poisoned", "gap": "both", "primers": 0, "chasers": 0,
         "note": "Escalating poison variant. No moves assigned yet."},
        {"name": "Infatuated",   "key": "infatuated",   "gap": "both", "primers": 0, "chasers": 0,
         "note": "No moves assign or chase it yet."},
        {"name": "Cursed",       "key": "cursed",       "gap": "both", "primers": 0, "chasers": 0,
         "note": "1/4 HP per turn. No moves assigned yet."},
        {"name": "Nightmare",    "key": "nightmare",    "gap": "both", "primers": 0, "chasers": 0,
         "note": "Damage while asleep. Requires Asleep first. No moves assigned yet."},
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.pokemon.models import SpeciesMovePool

        primer_entries = (
            SpeciesMovePool.objects
            .filter(move__applies_status__isnull=False, slot_type__in=("standard", "mystery", "passive_1", "passive_2"))
            .select_related("species__primary_type", "move__applies_status", "move__move_type")
            .order_by("move__applies_status__name", "species__name")
        )
        chaser_entries = (
            SpeciesMovePool.objects
            .filter(move__trigger_status__isnull=False, slot_type="chase")
            .select_related("species__primary_type", "move__trigger_status", "move__move_type")
            .order_by("move__trigger_status__name", "species__name")
        )

        status_map: dict[str, dict] = {}

        for entry in primer_entries:
            sname = entry.move.applies_status.get_name_display()
            skey = entry.move.applies_status.name
            bucket = status_map.setdefault(sname, {"key": skey, "primers": [], "chasers": []})
            bucket["primers"].append({
                "species": entry.species,
                "move_name": entry.move.themed_name or entry.move.name,
                "move_type": entry.move.move_type,
                "power": entry.move.power,
                "slot": entry.slot_type,
            })

        for entry in chaser_entries:
            sname = entry.move.trigger_status.get_name_display()
            skey = entry.move.trigger_status.name
            bucket = status_map.setdefault(sname, {"key": skey, "primers": [], "chasers": []})
            bucket["chasers"].append({
                "species": entry.species,
                "move_name": entry.move.themed_name or entry.move.name,
                "move_type": entry.move.move_type,
                "power": entry.move.power,
                "condition": entry.move.chase_condition or "",
            })

        combo_chains = [
            {
                "status": status,
                "key": data["key"],
                "primers": data["primers"],
                "chasers": data["chasers"],
                "complete": bool(data["primers"] and data["chasers"]),
            }
            for status, data in sorted(status_map.items())
            if data["primers"] and data["chasers"]
        ]

        context["combo_chains"] = combo_chains
        context["planned_statuses"] = self._PLANNED_STATUSES
        context["total_links"] = sum(
            len(c["primers"]) * len(c["chasers"]) for c in combo_chains
        )
        context["active_status_count"] = len(combo_chains)
        return context


class ComboSimulatorView(TemplateView):
    """Team combo simulator — pick up to 6 species, configure their movesets, see all chains."""

    template_name = "pokemon/combo_simulator.html"

    def get_context_data(self, **kwargs: object) -> dict:
        context = super().get_context_data(**kwargs)
        context["all_species"] = (
            Pokemon.objects
            .filter(pokedex_number__isnull=False)
            .order_by("pokedex_number")
            .values("id", "name", "pokedex_number")
        )
        return context


class ComboSimulatorMovesAPI(View):
    """JSON: return move options per slot for a given species pk."""

    def get(self, _request, pk: int) -> JsonResponse:
        from .models import MoveSlotType, SpeciesMovePool

        species = get_object_or_404(Pokemon, pk=pk)
        pool = (
            SpeciesMovePool.objects
            .filter(species=species)
            .select_related("move__move_type", "move__applies_status", "move__trigger_status")
            .order_by("slot_type", "move__name")
        )

        slots: dict[str, list] = {}
        for entry in pool:
            slot = entry.slot_type
            slots.setdefault(slot, []).append({
                "id": entry.move.id,
                "name": entry.move.themed_name or entry.move.name,
                "type": entry.move.move_type.name if entry.move.move_type else None,
                "power": entry.move.power,
                "applies_status": entry.move.applies_status.name if entry.move.applies_status_id else None,
                "applies_status_label": entry.move.applies_status.get_name_display() if entry.move.applies_status_id else None,
                "trigger_status": entry.move.trigger_status.name if entry.move.trigger_status_id else None,
                "trigger_status_label": entry.move.trigger_status.get_name_display() if entry.move.trigger_status_id else None,
                "chase_condition": entry.move.chase_condition or "",
            })

        return JsonResponse({
            "species_id": species.pk,
            "species_name": species.name,
            "pokedex_number": species.pokedex_number,
            "slots": slots,
        })


class ComboSimulatorChainsAPI(View):
    """JSON: given a configured team, return all primer→chaser pairs within that team."""

    def post(self, request) -> JsonResponse:
        try:
            body = json.loads(request.body)
            team: list[dict] = body.get("team", [])
        except (json.JSONDecodeError, AttributeError):
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        if not team:
            return JsonResponse({"chains": [], "total_links": 0})

        from .models import Move

        # Build per-member primer/chaser lists from their chosen moves
        # status_key → {primers: [...], chasers: [...]}
        status_map: dict[str, dict] = {}

        for member in team:
            species_name: str = member.get("species_name", "?")
            chosen_moves: dict[str, int] = member.get("moves", {})  # slot → move_id

            move_ids = [mid for mid in chosen_moves.values() if mid]
            if not move_ids:
                continue

            moves = Move.objects.filter(id__in=move_ids).select_related(
                "move_type", "applies_status", "trigger_status"
            )
            slot_by_move = {v: k for k, v in chosen_moves.items() if v}

            for move in moves:
                slot = slot_by_move.get(move.id, "")
                move_label = move.themed_name or move.name
                type_name = move.move_type.name if move.move_type else None

                if move.applies_status_id and slot != "chase":
                    skey = move.applies_status.name
                    slabel = move.applies_status.get_name_display()
                    bucket = status_map.setdefault(skey, {"label": slabel, "primers": [], "chasers": []})
                    bucket["primers"].append({
                        "species": species_name,
                        "move": move_label,
                        "type": type_name,
                        "power": move.power,
                        "slot": slot,
                    })

                if move.trigger_status_id and slot == "chase":
                    skey = move.trigger_status.name
                    slabel = move.trigger_status.get_name_display()
                    bucket = status_map.setdefault(skey, {"label": slabel, "primers": [], "chasers": []})
                    bucket["chasers"].append({
                        "species": species_name,
                        "move": move_label,
                        "type": type_name,
                        "power": move.power,
                        "condition": move.chase_condition or "",
                    })

        chains = [
            {
                "status": data["label"],
                "status_key": skey,
                "primers": data["primers"],
                "chasers": data["chasers"],
            }
            for skey, data in sorted(status_map.items(), key=lambda x: x[1]["label"])
            if data["primers"] and data["chasers"]
        ]

        return JsonResponse({
            "chains": chains,
            "total_links": sum(len(c["primers"]) * len(c["chasers"]) for c in chains),
        })
