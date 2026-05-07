"""Class-based views for the sticker collection app."""
import logging
from urllib.parse import urlencode
from collections import defaultdict

from django.db.models import Count
from django.core.paginator import Paginator
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import DetailView, ListView, TemplateView

from apps.pokemon.models import Pokemon

from .models import (
    CRAFT_COSTS,
    CRAFT_VARIANT_GROUPS,
    CRAFT_VARIANT_MULTIPLIERS,
    GEN_PACK_GEN_NUMBER,
    PackType,
    Sticker,
    StickerPack,
    StickerRarity,
    StickerVariant,
    TradeOffer,
    craft_cost_for,
)
from .models import REGION_LABELS, REGION_RANGES, StickerRarity
from .services import (
    PACK_PRICE_RYO,
    GEN_PACK_PRICE_RYO,
    POKEMON_COMPLETION_SLOTS,
    AlbumService,
    SceneAlbumService,
    StickerService,
    TradeService,
    _COMPLETION_RARITIES,
    _COMPLETION_VARIANTS,
    pack_price_for_type,
)

_album_service = AlbumService()
_scene_service = SceneAlbumService()

logger = logging.getLogger(__name__)

_sticker_service = StickerService()

PLACEMENT_VIEW_CHOICES: tuple[tuple[str, str], ...] = (
    ("placeable", "Ready to Place"),
    ("missing", "Missing Slots"),
    ("all", "All Slots"),
)

from apps.stickers.models import _pack_img  # noqa: E402
REGION_BUNDLE_IMAGE_PATHS = {
    PackType.GEN1: _pack_img("kanto_bundle_pack"),
    PackType.GEN2: _pack_img("johto_bundle_pack"),
    PackType.GEN3: _pack_img("hoenn_bundle_pack"),
    PackType.GEN4: _pack_img("sinnoh_bundle_pack"),
    PackType.GEN5: _pack_img("unova_bundle_pack"),
    PackType.GEN6: _pack_img("kalos_bundle_pack"),
    PackType.GEN7: _pack_img("alola_bundle_pack"),
    PackType.GEN8: _pack_img("galar_bundle_pack"),
}
_trade_service = TradeService()


def _build_redirect_url(
    view_name: str,
    *,
    kwargs: dict | None = None,
    params: dict | None = None,
    anchor: str | None = None,
) -> str:
    url = reverse(view_name, kwargs=kwargs or {})
    clean_params = {
        key: value for key, value in (params or {}).items()
        if value not in (None, "", [])
    }
    if clean_params:
        url = f"{url}?{urlencode(clean_params)}"
    if anchor:
        url = f"{url}#{anchor}"
    return url


def _filter_placement_slots(slots: list[dict], view_mode: str) -> list[dict]:
    if view_mode == "all":
        return slots
    if view_mode == "missing":
        return [slot for slot in slots if not slot["is_placed"]]
    return [slot for slot in slots if slot["is_placeable"]]


def _region_for_dex(dex_number: int | None) -> str | None:
    if dex_number is None:
        return None
    for region_name, (low, high) in REGION_RANGES.items():
        if low <= dex_number <= high:
            return region_name
    return None


def _build_placement_ready_stash(user, *, selected_region: str, selected_rarity: str) -> tuple[list[dict], int]:
    rarity_labels = {value: label for value, label in StickerRarity.choices}
    rarity_order = list(StickerRarity.values)
    region_order = list(REGION_LABELS.keys())
    candidate_pairs: set[tuple[str, str]] = set()
    loose_rows = (
        Sticker.objects.filter(
            owner=user,
            is_album_placed=False,
            is_trading=False,
            guild_album_entry__isnull=True,
            variant__in=_COMPLETION_VARIANTS,
        )
        .values("pokemon__pokedex_number", "rarity")
        .annotate(copies=Count("id"))
    )
    for row in loose_rows:
        dex = row["pokemon__pokedex_number"]
        if dex is None:
            continue
        region_name = _region_for_dex(int(dex))
        if region_name is None:
            continue
        candidate_pairs.add((region_name, row["rarity"]))

    stash_cards = []
    for region_name, rarity_value in candidate_pairs:
        placement_data = _album_service.get_placement_slots(user, region_name, rarity_value)
        count = placement_data["slot_totals"]["placeable"]
        if count <= 0:
            continue
        stash_cards.append(
            {
                "region": region_name,
                "region_label": REGION_LABELS.get(region_name, region_name.title()),
                "rarity": rarity_value,
                "rarity_label": rarity_labels.get(rarity_value, rarity_value.replace("_", " ").title()),
                "count": count,
                "is_selected": region_name == selected_region and rarity_value == selected_rarity,
            }
        )

    stash_cards.sort(
        key=lambda item: (
            -item["count"],
            region_order.index(item["region"]) if item["region"] in region_order else 999,
            rarity_order.index(item["rarity"]) if item["rarity"] in rarity_order else 999,
        )
    )
    return stash_cards, sum(item["count"] for item in stash_cards)


class AlbumView(LoginRequiredMixin, TemplateView):
    """
    Displays the player's full sticker album.

    - All Pokemon grouped by type with completion % per type
    - Locked silhouettes for uncollected Pokemon
    - Pokedex completion % at the top
    - Showcase section with up to 6 pinned stickers
    """

    template_name = "stickers/album.html"

    def get(self, request, *args, **kwargs):
        from apps.users.guide_service import maybe_advance_from_url
        maybe_advance_from_url(request.user, "stickers:album")
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        album_data = _sticker_service.get_album(self.request.user)
        context.update(album_data)

        # All Pokemon grouped by primary type for the album grid
        all_pokemon = list(
            Pokemon.objects.select_related("primary_type", "secondary_type")
            .prefetch_related("stickers")
            .order_by("pokedex_number", "name")
        )
        owned_pokemon_ids = set(
            Sticker.objects.filter(owner=self.request.user).values_list("pokemon_id", flat=True)
        )
        context["all_pokemon"] = all_pokemon
        context["owned_pokemon_ids"] = owned_pokemon_ids
        context["unopened_packs"] = StickerPack.objects.filter(
            owner=self.request.user, opened=False
        ).count()
        completion = _sticker_service.get_completion_rewards_for_album(self.request.user)
        context.update(completion)
        context["pokemon_completion_slots"] = POKEMON_COMPLETION_SLOTS
        return context


class PokemonAlbumDetailView(LoginRequiredMixin, TemplateView):
    """
    Per-Pokemon album page — 7×6 rarity/variant grid showing owned vs missing slots.

    GET /stickers/album/<pokemon_pk>/
    """

    template_name = "stickers/pokemon_album.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pokemon = get_object_or_404(Pokemon, pk=kwargs["pokemon_pk"])
        user = self.request.user

        # Build a set of (rarity, variant) tuples the player owns for this pokemon
        owned_slots: set[tuple[str, str]] = set(
            Sticker.objects.filter(owner=user, pokemon=pokemon)
            .values_list("rarity", "variant")
            .distinct()
        )

        # Count copies per slot (for duplicate display)
        from django.db.models import Count as _Count
        copy_counts: dict[tuple[str, str], int] = {
            (row["rarity"], row["variant"]): row["count"]
            for row in Sticker.objects.filter(owner=user, pokemon=pokemon)
            .values("rarity", "variant")
            .annotate(count=_Count("id"))
        }

        # Build the grid: list[dict] ordered rarity-major, variant-minor
        grid = []
        for rarity in _COMPLETION_RARITIES:
            for variant in _COMPLETION_VARIANTS:
                slot = (rarity, variant)
                grid.append({
                    "rarity": rarity,
                    "rarity_label": StickerRarity(rarity).label,
                    "variant": variant,
                    "variant_label": StickerVariant(variant).label,
                    "owned": slot in owned_slots,
                    "copies": copy_counts.get(slot, 0),
                })

        # Completion check
        is_complete = _sticker_service.check_pokemon_completion(user, pokemon)
        slots_owned = len(owned_slots & {(r, v) for r in _COMPLETION_RARITIES for v in _COMPLETION_VARIANTS})

        context["pokemon"] = pokemon
        context["grid"] = grid
        context["is_complete"] = is_complete
        context["slots_owned"] = slots_owned
        context["slots_total"] = POKEMON_COMPLETION_SLOTS
        context["rarities"] = _COMPLETION_RARITIES
        context["variants"] = _COMPLETION_VARIANTS
        return context


class MyPacksView(LoginRequiredMixin, TemplateView):
    """Lists all unopened packs owned by the user. Redirects directly if only one."""

    template_name = "stickers/my_packs.html"

    def get(self, request, *args, **kwargs):
        from apps.users.guide_service import maybe_advance_from_url
        maybe_advance_from_url(request.user, "stickers:my_packs")
        packs = list(
            StickerPack.objects.filter(owner=request.user, opened=False).order_by("created_at")
        )
        if len(packs) == 1:
            return redirect("stickers:pack_open", pk=packs[0].pk)
        context = self.get_context_data(**kwargs)
        context["packs"] = packs
        return self.render_to_response(context)


class PackOpenView(LoginRequiredMixin, TemplateView):
    """Pack opening — reveals 5 stickers with their details."""

    template_name = "stickers/pack_open.html"

    def get(self, request, *args, **kwargs):
        pack = get_object_or_404(StickerPack, pk=kwargs["pk"], owner=request.user)
        context = self.get_context_data(**kwargs)
        context["pack"] = pack
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        pack = get_object_or_404(StickerPack, pk=kwargs["pk"], owner=request.user)
        try:
            stickers = _sticker_service.open_pack(request.user, pack)
        except ValueError as exc:
            return redirect("stickers:album")

        from apps.users.guide_service import maybe_advance_from_url
        maybe_advance_from_url(request.user, "stickers:pack_open")

        context = self.get_context_data(**kwargs)
        context["pack"] = pack
        context["revealed_stickers"] = stickers
        context["auto_placed_count"] = sum(1 for sticker in stickers if sticker.is_album_placed)
        return self.render_to_response(context)


class TradeListView(LoginRequiredMixin, ListView):
    """Browse open trade offers on the trade board."""

    template_name = "stickers/trade_list.html"
    context_object_name = "offers"
    paginate_by = 20

    def get_queryset(self):
        return _trade_service.get_open_offers().select_related(
            "offered_sticker__pokemon__primary_type",
            "offered_by",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["my_offers"] = TradeOffer.objects.filter(
            offered_by=self.request.user,
            status=TradeOffer.Status.PENDING,
        ).select_related("offered_sticker__pokemon")
        return context


class TradeCreateView(LoginRequiredMixin, TemplateView):
    """Create a new trade offer."""

    template_name = "stickers/trade_create.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["my_stickers"] = Sticker.objects.filter(
            owner=self.request.user, is_trading=False, guild_album_entry__isnull=True
        ).select_related("pokemon__primary_type")
        context["all_pokemon"] = Pokemon.objects.order_by("name")
        return context

    def post(self, request, *args, **kwargs):
        sticker_id = request.POST.get("sticker_id")
        requested_pokemon_id = request.POST.get("requested_pokemon_id")
        looking_for_note = request.POST.get("looking_for_note", "")

        sticker = get_object_or_404(Sticker, pk=sticker_id, owner=request.user)
        requested_pokemon = None
        if requested_pokemon_id:
            requested_pokemon = get_object_or_404(Pokemon, pk=requested_pokemon_id)

        try:
            _trade_service.create_trade_offer(
                sender=request.user,
                sticker=sticker,
                requested_pokemon=requested_pokemon,
                looking_for_note=looking_for_note,
            )
        except ValueError as exc:
            context = self.get_context_data(error=str(exc), **kwargs)
            return self.render_to_response(context)

        return redirect("stickers:trade_list")


class TradeDetailView(LoginRequiredMixin, DetailView):
    """View a specific trade offer and optionally accept it."""

    model = TradeOffer
    template_name = "stickers/trade_detail.html"
    context_object_name = "offer"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Show stickers the current user could offer in exchange
        context["my_stickers"] = Sticker.objects.filter(
            owner=self.request.user, is_trading=False, guild_album_entry__isnull=True
        ).select_related("pokemon")
        return context

    def post(self, request, *args, **kwargs):
        offer = self.get_object()
        action = request.POST.get("action")

        if action == "accept":
            accepting_sticker_id = request.POST.get("accepting_sticker_id")
            accepting_sticker = get_object_or_404(
                Sticker, pk=accepting_sticker_id, owner=request.user
            )
            try:
                _trade_service.accept_trade(request.user, offer, accepting_sticker)
            except ValueError as exc:
                context = self.get_context_data(offer=offer, error=str(exc))
                return self.render_to_response(context)

        elif action == "reject":
            try:
                _trade_service.reject_trade(request.user, offer)
            except ValueError as exc:
                pass

        elif action == "cancel":
            try:
                _trade_service.cancel_trade(request.user, offer)
            except ValueError as exc:
                pass

        return redirect("stickers:trade_list")


class BuyPackView(LoginRequiredMixin, TemplateView):
    """Buy a sticker pack with Ryo."""

    template_name = "stickers/buy_pack.html"

    def get(self, request, *args, **kwargs):
        from apps.users.guide_service import maybe_advance_from_url
        maybe_advance_from_url(request.user, "stickers:buy_pack")
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["pack_price"] = PACK_PRICE_RYO
        context["gen_pack_price"] = GEN_PACK_PRICE_RYO
        context["pack_price_10"] = PACK_PRICE_RYO * 10
        context["can_afford"] = self.request.user.ryo >= PACK_PRICE_RYO
        context["can_afford_10"] = self.request.user.ryo >= PACK_PRICE_RYO * 10
        context["pack_types"] = [
            {
                "value": pt.value,
                "label": pt.label,
                "price": pack_price_for_type(pt.value),
                "can_afford": self.request.user.ryo >= pack_price_for_type(pt.value),
                "image_path": StickerPack(pack_type=pt.value).image_path,
                "sticker_count": StickerPack(pack_type=pt.value).sticker_count,
            }
            for pt in PackType
            if pt not in (PackType.BUNDLE,)  # bundle is granted, not bought
        ]
        context["region_products"] = [
            {
                **pt,
                "bundle_price": pt["price"] * 10,
                "bundle_can_afford": self.request.user.ryo >= pt["price"] * 10,
                "bundle_image_path": REGION_BUNDLE_IMAGE_PATHS.get(
                    pt["value"],
                    StickerPack(pack_type=PackType.BUNDLE).image_path,
                ),
                "bundle_sticker_count": pt["sticker_count"] * 10,
                "bundle_name": f"{pt['label']} Bundle",
            }
            for pt in context["pack_types"]
            if pt["value"] != PackType.STANDARD
        ]
        context["gen_pack_numbers"] = GEN_PACK_GEN_NUMBER
        return context

    def post(self, request, *args, **kwargs):
        pack_type = request.POST.get("pack_type", PackType.STANDARD)
        if pack_type not in PackType.values or pack_type == PackType.BUNDLE:
            pack_type = PackType.STANDARD
        try:
            pack = _sticker_service.buy_pack(request.user, pack_type=pack_type)
        except ValueError as exc:
            context = self.get_context_data(error=str(exc), **kwargs)
            return self.render_to_response(context)
        return redirect("stickers:pack_open", pk=pack.pk)


class BuyMultiPackView(LoginRequiredMixin, TemplateView):
    """Buy 10 sticker packs at once and open them all immediately."""

    template_name = "stickers/multi_pack_open.html"

    def post(self, request, *args, **kwargs):
        pack_type = request.POST.get("pack_type", PackType.STANDARD)
        if pack_type not in PackType.values or pack_type == PackType.BUNDLE:
            pack_type = PackType.STANDARD
        unit_price = pack_price_for_type(pack_type)
        total_cost = unit_price * 10
        if request.user.ryo < total_cost:
            return redirect("stickers:buy_pack")
        try:
            all_stickers = []
            preview_pack = StickerPack(pack_type=pack_type)
            previously_owned_keys = set(
                Sticker.objects.filter(owner=request.user)
                .values_list("pokemon_id", "rarity", "variant")
                .distinct()
            )
            for _ in range(10):
                pack = _sticker_service.buy_pack(request.user, pack_type=pack_type)
                stickers = _sticker_service.open_pack(request.user, pack)
                all_stickers.extend(stickers)
        except ValueError as exc:
            return redirect("stickers:buy_pack")
        for sticker in all_stickers:
            sticker.was_owned_before_bundle = (
                sticker.pokemon_id,
                sticker.rarity,
                sticker.variant,
            ) in previously_owned_keys
        context = self.get_context_data(**kwargs)
        context["all_stickers"] = all_stickers
        context["pack_count"] = 10
        context["cards_per_pack"] = preview_pack.sticker_count
        context["bundle_title"] = f"{preview_pack.display_name} Bundle"
        context["bundle_total_price"] = total_cost
        context["auto_placed_count"] = sum(1 for sticker in all_stickers if sticker.is_album_placed)
        return self.render_to_response(context)


class DustWorkshopView(LoginRequiredMixin, TemplateView):
    """
    Unified dust economy hub — three tabs:
      • Convert Duplicates  (POST action=convert)
      • Craft a Sticker     (POST action=craft)
      • Forge a Badge       (Phase 3 — display only for now)
    """

    template_name = "stickers/workshop.html"

    def _selected_craft_pokemon_id(self) -> int | None:
        raw_value = self.request.GET.get("pokemon")
        if not raw_value:
            return None
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            return None

    def _selected_craft_rarity(self) -> str:
        rarity = self.request.GET.get("rarity", StickerRarity.COMMON)
        return rarity if rarity in StickerRarity.values else StickerRarity.COMMON

    def _selected_craft_variant(self) -> str:
        variant = self.request.GET.get("variant", StickerVariant.BASE)
        return variant if variant in StickerVariant.values else StickerVariant.BASE

    def get_context_data(self, **kwargs):
        from .models import BADGE_CRAFT_REQUIREMENTS, BadgeTier

        context = super().get_context_data(**kwargs)
        context["sticker_dust"] = self.request.user.sticker_dust
        craft_prefilled = any(
            self.request.GET.get(param)
            for param in ("pokemon", "rarity", "variant")
        )
        active_tab = self.request.GET.get("tab", "craft" if craft_prefilled else "convert")
        context["active_tab"] = active_tab

        # Convert tab
        if active_tab == "convert":
            context.update(_sticker_service.get_convertible_duplicate_groups(self.request.user))
        else:
            context.update({
                "duplicate_groups": [],
                "convertible_group_count": 0,
                "convertible_copy_count": 0,
                "convertible_dust_total": 0,
            })

        # Craft tab — skip expensive queries when not needed
        if active_tab == "craft":
            pokemon_list = list(
                Pokemon.objects.only("id", "name", "pokedex_number")
                .order_by("pokedex_number", "name")
            )
            selected_pokemon_id = self._selected_craft_pokemon_id()
            if selected_pokemon_id and any(pokemon.pk == selected_pokemon_id for pokemon in pokemon_list):
                selected_pokemon = next(pokemon for pokemon in pokemon_list if pokemon.pk == selected_pokemon_id)
            else:
                selected_pokemon = pokemon_list[0] if pokemon_list else None

            selected_rarity = self._selected_craft_rarity()
            selected_variant = self._selected_craft_variant()
            if selected_variant == StickerVariant.ANIME and selected_rarity != StickerRarity.SECRET_RARE:
                selected_variant = StickerVariant.BASE

            owned_slot_keys = {
                f"{pokemon_id}|{rarity}|{variant}"
                for pokemon_id, rarity, variant in Sticker.objects.filter(
                    owner=self.request.user
                ).order_by().values_list("pokemon_id", "rarity", "variant").distinct()
            }
            placed_slot_keys = {
                f"{pokemon_id}|{rarity}|{variant}"
                for pokemon_id, rarity, variant in Sticker.objects.filter(
                    owner=self.request.user,
                    is_album_placed=True,
                ).order_by().values_list("pokemon_id", "rarity", "variant").distinct()
            }

            context["pokemon_list"] = pokemon_list
            context["pokemon_picker_data"] = [
                {
                    "id": pokemon.pk,
                    "name": pokemon.name,
                    "dex": pokemon.pokedex_number or 0,
                }
                for pokemon in pokemon_list
            ]
            context["craft_selected_pokemon"] = selected_pokemon
            context["craft_selected_rarity"] = selected_rarity
            context["craft_selected_variant"] = selected_variant
            context["craft_selected_cost"] = craft_cost_for(selected_rarity, selected_variant)
            context["craft_missing_only"] = self.request.GET.get("missing_only") == "1"
            context["craft_owned_slot_keys"] = sorted(owned_slot_keys)
            context["craft_placed_slot_keys"] = sorted(placed_slot_keys)
            context["craft_costs"] = CRAFT_COSTS
            context["craft_variant_multipliers"] = CRAFT_VARIANT_MULTIPLIERS
            context["craft_rarity_choices"] = StickerRarity.choices
            context["craft_variant_groups"] = [
                {
                    "label": group_label,
                    "variants": [
                        {
                            "value": variant,
                            "label": StickerVariant(variant).label,
                            "multiplier": CRAFT_VARIANT_MULTIPLIERS[variant],
                        }
                        for variant in variants
                    ],
                }
                for group_label, variants in CRAFT_VARIANT_GROUPS
            ]
        else:
            selected_rarity = self._selected_craft_rarity()
            selected_variant = self._selected_craft_variant()
            context["pokemon_list"] = []
            context["pokemon_picker_data"] = []
            context["craft_selected_pokemon"] = None
            context["craft_selected_rarity"] = selected_rarity
            context["craft_selected_variant"] = selected_variant
            context["craft_selected_cost"] = craft_cost_for(selected_rarity, selected_variant)
            context["craft_missing_only"] = False
            context["craft_owned_slot_keys"] = []
            context["craft_placed_slot_keys"] = []
            context["craft_costs"] = CRAFT_COSTS
            context["craft_variant_multipliers"] = CRAFT_VARIANT_MULTIPLIERS
            context["craft_rarity_choices"] = StickerRarity.choices
            context["craft_variant_groups"] = []

        # Badge Forge tab (Phase 3 — display only)
        context["badge_requirements"] = BADGE_CRAFT_REQUIREMENTS
        context["badge_tiers"] = BadgeTier.choices

        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")

        if action == "convert":
            sticker_id = request.POST.get("sticker_id")
            sticker = get_object_or_404(Sticker, pk=sticker_id, owner=request.user)
            try:
                _sticker_service.convert_duplicate(request.user, sticker)
            except ValueError as exc:
                context = self.get_context_data(error=str(exc), **kwargs)
                return self.render_to_response(context)
            return redirect("/stickers/workshop/?tab=convert")

        if action == "convert_all":
            pokemon_id = request.POST.get("pokemon_id")
            rarity = request.POST.get("rarity")
            variant = request.POST.get("variant")
            try:
                _sticker_service.convert_all_duplicates(
                    request.user,
                    int(pokemon_id),
                    rarity,
                    variant,
                )
            except (TypeError, ValueError) as exc:
                context = self.get_context_data(error=str(exc), **kwargs)
                return self.render_to_response(context)
            return redirect("/stickers/workshop/?tab=convert")

        if action == "craft":
            pokemon_id = request.POST.get("pokemon_id")
            variant = request.POST.get("variant")
            rarity = request.POST.get("rarity")
            missing_only = request.POST.get("missing_only")
            pokemon = get_object_or_404(Pokemon, pk=pokemon_id)
            try:
                _sticker_service.craft_sticker(request.user, pokemon, variant, rarity)
            except ValueError as exc:
                context = self.get_context_data(error=str(exc), **kwargs)
                context["active_tab"] = "craft"
                context["craft_selected_pokemon"] = pokemon
                context["craft_selected_rarity"] = rarity
                context["craft_selected_variant"] = variant
                context["craft_selected_cost"] = craft_cost_for(rarity, variant) if (
                    rarity in StickerRarity.values and variant in StickerVariant.values
                ) else None
                context["craft_missing_only"] = missing_only == "1"
                return self.render_to_response(context)
            params = {
                "tab": "craft",
                "pokemon": pokemon_id,
                "rarity": rarity,
                "variant": variant,
            }
            if missing_only == "1":
                params["missing_only"] = "1"
            return redirect(f"/stickers/workshop/?{urlencode(params)}")

        return redirect("/stickers/workshop/")


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Regional Album views
# ---------------------------------------------------------------------------

class RegionalAlbumIndexView(LoginRequiredMixin, TemplateView):
    """
    Hub page showing all 9 regions with per-rarity completion stats.

    GET /stickers/album/regional/
    """

    template_name = "stickers/regional_album_index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["regions"] = _album_service.get_region_index(self.request.user)
        context["rarity_choices"] = StickerRarity.choices
        context["region_labels"] = REGION_LABELS
        return context


class RegionalAlbumDetailView(LoginRequiredMixin, TemplateView):
    """
    One (region × rarity) album page — grid of Pokémon slots.

    GET /stickers/album/regional/<region>/<rarity>/
    """

    template_name = "stickers/regional_album_detail.html"

    def get(self, request, *args, **kwargs):
        region = kwargs["region"]
        rarity = kwargs["rarity"]
        if region not in REGION_RANGES or rarity not in StickerRarity.values:
            from django.http import Http404
            raise Http404("Invalid region or rarity")
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        region = self.kwargs["region"]
        rarity = self.kwargs["rarity"]
        page_data = _album_service.get_page_detail(self.request.user, region, rarity)
        context.update(page_data)
        context["all_rarities"] = StickerRarity.choices
        context["region_labels"] = REGION_LABELS

        # Adjacent rarity navigation
        rarity_values = list(StickerRarity.values)
        idx = rarity_values.index(rarity)
        context["prev_rarity"] = rarity_values[idx - 1] if idx > 0 else None
        context["next_rarity"] = rarity_values[idx + 1] if idx < len(rarity_values) - 1 else None

        # Pagination — group slots by pokemon, 15 per page (last page absorbs orphan of 1)
        PAGE_SIZE = 15
        from itertools import groupby
        all_slots = page_data["slots"]
        # Group into per-pokemon slot lists preserving order
        pokemon_slot_groups: list[list] = []
        for _, grp in groupby(all_slots, key=lambda s: s["pokemon"].pk):
            pokemon_slot_groups.append(list(grp))

        total_pokemon = len(pokemon_slot_groups)
        total_pages = max(1, (total_pokemon + PAGE_SIZE - 1) // PAGE_SIZE)

        try:
            current_page = int(self.request.GET.get("page", 1))
        except (ValueError, TypeError):
            current_page = 1
        current_page = max(1, min(current_page, total_pages))

        start = (current_page - 1) * PAGE_SIZE
        end = start + PAGE_SIZE
        # Absorb orphan: if only 1 pokemon would remain on the next page, include it here
        if end < total_pokemon and total_pokemon - end == 1:
            end += 1

        page_groups = pokemon_slot_groups[start:end]
        context["pokemon_slot_groups"] = page_groups
        context["current_page"] = current_page
        context["total_pages"] = total_pages
        context["has_prev_page"] = current_page > 1
        context["has_next_page"] = current_page < total_pages
        return context


class PlacementModeView(LoginRequiredMixin, TemplateView):
    """
    Compact album management page optimized for fast sticker placement.

    GET  /stickers/album/placement/
    POST /stickers/album/placement/   (bulk place / toggle auto-place)
    """

    template_name = "stickers/placement_mode.html"
    page_size = 72

    def _selected_region(self) -> str:
        region = self.request.GET.get("region", "kanto")
        return region if region in REGION_RANGES else "kanto"

    def _selected_rarity(self) -> str:
        rarity = self.request.GET.get("rarity", StickerRarity.COMMON)
        return rarity if rarity in StickerRarity.values else StickerRarity.COMMON

    def _selected_view(self) -> str:
        view_mode = self.request.GET.get("view", "placeable")
        valid_values = {value for value, _ in PLACEMENT_VIEW_CHOICES}
        return view_mode if view_mode in valid_values else "placeable"

    def _build_context(self, **kwargs):
        context = super().get_context_data(**kwargs)
        region = self._selected_region()
        rarity = self._selected_rarity()
        view_mode = self._selected_view()

        placement_data = _album_service.get_placement_slots(self.request.user, region, rarity)
        filtered_slots = _filter_placement_slots(placement_data["placement_slots"], view_mode)

        paginator = Paginator(filtered_slots, self.page_size)
        page_number = self.request.GET.get("page") or 1
        page_obj = paginator.get_page(page_number)

        context.update(placement_data)
        context["selected_region"] = region
        context["selected_rarity"] = rarity
        context["selected_view"] = view_mode
        context["view_choices"] = PLACEMENT_VIEW_CHOICES
        context["region_choices"] = [
            {"value": region_name, "label": label}
            for region_name, label in REGION_LABELS.items()
        ]
        context["rarity_choices"] = StickerRarity.choices
        context["page_obj"] = page_obj
        context["placement_slots_page"] = list(page_obj.object_list)
        context["page_range"] = paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=1)
        context["visible_placeable_count"] = sum(
            1 for slot in page_obj.object_list if slot["is_placeable"]
        )
        context["filtered_slot_count"] = len(filtered_slots)
        ready_stash_cards, ready_stash_total = _build_placement_ready_stash(
            self.request.user,
            selected_region=region,
            selected_rarity=rarity,
        )
        context["ready_stash_cards"] = ready_stash_cards
        context["ready_stash_total"] = ready_stash_total
        context["current_query"] = {
            "region": region,
            "rarity": rarity,
            "view": view_mode,
            "page": page_obj.number,
        }
        context["placed_count_notice"] = self.request.GET.get("placed_count")
        context["bulk_scope"] = self.request.GET.get("bulk_scope", "")
        context["settings_saved"] = self.request.GET.get("settings_saved") == "1"
        context["error_notice"] = self.request.GET.get("error", "")
        return context

    def get_context_data(self, **kwargs):
        return self._build_context(**kwargs)

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        region = request.POST.get("region", "kanto")
        rarity = request.POST.get("rarity", StickerRarity.COMMON)
        view_mode = request.POST.get("view", "placeable")
        page_number = request.POST.get("page", 1)
        base_params = {
            "region": region,
            "rarity": rarity,
            "view": view_mode,
            "page": page_number,
        }

        if action == "toggle_auto_place":
            request.user.auto_place_new_stickers = request.POST.get("auto_place_new_stickers") == "on"
            request.user.save(update_fields=["auto_place_new_stickers"])
            return HttpResponseRedirect(
                _build_redirect_url(
                    "stickers:placement_mode",
                    params={**base_params, "settings_saved": 1},
                )
            )

        if action in {"bulk_visible", "bulk_filtered"}:
            placement_data = _album_service.get_placement_slots(request.user, region, rarity)
            filtered_slots = _filter_placement_slots(placement_data["placement_slots"], view_mode)
            if action == "bulk_visible":
                paginator = Paginator(filtered_slots, self.page_size)
                slots_to_place = list(paginator.get_page(page_number).object_list)
            else:
                slots_to_place = filtered_slots

            sticker_ids = [
                slot["first_available_sticker_id"]
                for slot in slots_to_place
                if slot["is_placeable"] and slot["first_available_sticker_id"]
            ]
            placed_count = _album_service.place_many(request.user, sticker_ids)
            return HttpResponseRedirect(
                _build_redirect_url(
                    "stickers:placement_mode",
                    params={
                        **base_params,
                        "placed_count": placed_count,
                        "bulk_scope": "visible" if action == "bulk_visible" else "filtered",
                    },
                )
            )

        return HttpResponseRedirect(
            _build_redirect_url("stickers:placement_mode", params=base_params)
        )


class PlaceStickerView(LoginRequiredMixin, TemplateView):
    """
    POST /stickers/album/regional/place/

    Places a sticker into its regional album slot.
    Redirects back to the (region, rarity) detail page.
    """

    def post(self, request, *args, **kwargs):
        sticker_id = request.POST.get("sticker_id")
        region = request.POST.get("region")
        rarity = request.POST.get("rarity")
        redirect_to = request.POST.get("redirect_to", "regional")
        page_number = request.POST.get("page_number")
        page = request.POST.get("page")
        view_mode = request.POST.get("view")
        anchor = request.POST.get("anchor")

        if not sticker_id:
            return redirect("stickers:regional_album_index")

        try:
            _album_service.place_sticker(request.user, int(sticker_id))
        except ValueError as exc:
            if redirect_to == "placement":
                return HttpResponseRedirect(
                    _build_redirect_url(
                        "stickers:placement_mode",
                        params={
                            "region": region,
                            "rarity": rarity,
                            "view": view_mode,
                            "page": page,
                            "error": str(exc),
                        },
                        anchor=anchor,
                    )
                )
            # Re-render the detail page with the error
            page_data = _album_service.get_page_detail(request.user, region, rarity)
            return self.response_class(
                request=request,
                template=["stickers/regional_album_detail.html"],
                context={**page_data, "error": str(exc), "region_labels": REGION_LABELS,
                         "all_rarities": StickerRarity.choices},
            )

        if redirect_to == "scene" and page_number:
            return HttpResponseRedirect(
                _build_redirect_url(
                    "stickers:album_scene_page",
                    kwargs={"region": region, "page_number": int(page_number), "rarity": rarity},
                    anchor=anchor,
                )
            )
        if redirect_to == "placement":
            return HttpResponseRedirect(
                _build_redirect_url(
                    "stickers:placement_mode",
                    params={"region": region, "rarity": rarity, "view": view_mode, "page": page},
                    anchor=anchor,
                )
            )
        return HttpResponseRedirect(
            _build_redirect_url(
                "stickers:regional_album_detail",
                kwargs={"region": region, "rarity": rarity},
                params={"page": page},
                anchor=anchor,
            )
        )


class RemoveStickerView(LoginRequiredMixin, TemplateView):
    """
    POST /stickers/album/regional/remove/

    Removes a placed sticker from its album slot.
    """

    def post(self, request, *args, **kwargs):
        sticker_id = request.POST.get("sticker_id")
        region = request.POST.get("region")
        rarity = request.POST.get("rarity")

        if not sticker_id:
            return redirect("stickers:regional_album_index")

        try:
            _album_service.remove_sticker(request.user, int(sticker_id))
        except ValueError:
            pass

        return redirect("stickers:regional_album_detail", region=region, rarity=rarity)


class ClaimPageRewardView(LoginRequiredMixin, TemplateView):
    """
    POST /stickers/album/regional/claim/

    Claims the reward for a completed (region, rarity) page.
    """

    def post(self, request, *args, **kwargs):
        region = request.POST.get("region")
        rarity = request.POST.get("rarity")

        if not region or not rarity:
            return redirect("stickers:regional_album_index")

        try:
            reward = _album_service.claim_page_reward(request.user, region, rarity)
            # Pass reward summary via session for display after redirect
            request.session["last_page_reward"] = reward
        except ValueError:
            pass

        return redirect("stickers:regional_album_detail", region=region, rarity=rarity)


# ---------------------------------------------------------------------------
# Scene Album views (card-flip, per-location pages)
# ---------------------------------------------------------------------------

class AlbumPageIndexView(LoginRequiredMixin, TemplateView):
    """
    Page-picker for a region — shows all AlbumPage thumbnails with overall
    progress per page so the player can jump to a specific location.

    GET /stickers/album/scene/<region>/
    """

    template_name = "stickers/album_scene_index.html"

    def get(self, request, *args, **kwargs):
        region = kwargs["region"]
        if region not in REGION_RANGES:
            from django.http import Http404
            raise Http404("Unknown region")
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        region = self.kwargs["region"]
        pages_summary = _scene_service.get_all_pages_summary(self.request.user, region)
        context["region"] = region
        context["region_label"] = REGION_LABELS.get(region, region.title())
        context["pages_summary"] = pages_summary
        context["rarity_choices"] = StickerRarity.choices
        context["default_rarity"] = StickerRarity.COMMON
        return context


class AlbumScenePageView(LoginRequiredMixin, TemplateView):
    """
    One scene page at a given rarity — shows all Pokémon cards for the
    location; each card can be flipped (Alpine.js) to reveal 6 variant slots.

    GET /stickers/album/scene/<region>/<int:page_number>/<str:rarity>/
    """

    template_name = "stickers/album_scene_page.html"

    def get(self, request, *args, **kwargs):
        from django.http import Http404
        from .models import AlbumPage as _AlbumPage
        region = kwargs["region"]
        page_number = kwargs["page_number"]
        rarity = kwargs["rarity"]
        if region not in REGION_RANGES or rarity not in StickerRarity.values:
            raise Http404("Invalid region or rarity")
        self._album_page = get_object_or_404(_AlbumPage, region=region, page_number=page_number)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rarity = self.kwargs["rarity"]
        scene_data = _scene_service.get_scene_page(self.request.user, self._album_page, rarity)
        context.update(scene_data)
        context["region"] = self.kwargs["region"]
        context["region_label"] = REGION_LABELS.get(self.kwargs["region"], self.kwargs["region"].title())
        return context


class StickerDetailView(LoginRequiredMixin, TemplateView):
    """
    Full-size sticker viewer: displays a single (pokemon, rarity, variant) card
    with its frame, owned status, and copy count.

    GET /stickers/sticker/<int:pokemon_pk>/<str:rarity>/<str:variant>/
    """

    template_name = "stickers/sticker_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pokemon = get_object_or_404(Pokemon, pk=self.kwargs["pokemon_pk"])
        rarity = self.kwargs["rarity"]
        current_variant = self.kwargs["variant"]

        # Owned counts per variant at this rarity
        owned_counts: dict[str, int] = {
            row["variant"]: row["cnt"]
            for row in Sticker.objects.filter(
                owner=self.request.user, pokemon=pokemon, rarity=rarity
            ).values("variant").annotate(cnt=Count("id"))
        }

        owned_variants = [
            variant for variant in _COMPLETION_VARIANTS
            if owned_counts.get(variant, 0) > 0
        ]
        if not owned_variants:
            owned_variants = [current_variant]

        slides = [
            {
                "variant": variant,
                "variant_label": StickerVariant(variant).label,
                "owned": owned_counts.get(variant, 0) > 0,
                "copies": owned_counts.get(variant, 0),
            }
            for variant in owned_variants
        ]

        current_index = next((i for i, s in enumerate(slides) if s["variant"] == current_variant), 0)

        import json
        context["pokemon"] = pokemon
        context["rarity"] = rarity
        context["rarity_label"] = StickerRarity(rarity).label if rarity in StickerRarity.values else rarity.replace("_", " ").title()
        context["slides"] = slides
        context["current_index"] = current_index
        context["slides_json"] = json.dumps(slides)
        return context
