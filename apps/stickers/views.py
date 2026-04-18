"""Class-based views for the sticker collection app."""
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import DetailView, ListView, TemplateView

from apps.pokemon.models import Pokemon

from .models import Sticker, StickerPack, StickerRarity, StickerVariant, TradeOffer
from .models import REGION_LABELS, REGION_RANGES, StickerRarity
from .services import (
    PACK_PRICE_RYO,
    POKEMON_COMPLETION_SLOTS,
    AlbumService,
    SceneAlbumService,
    StickerService,
    TradeService,
    _COMPLETION_RARITIES,
    _COMPLETION_VARIANTS,
)

_album_service = AlbumService()
_scene_service = SceneAlbumService()

logger = logging.getLogger(__name__)

_sticker_service = StickerService()
_trade_service = TradeService()


class AlbumView(LoginRequiredMixin, TemplateView):
    """
    Displays the player's full sticker album.

    - All Pokemon grouped by type with completion % per type
    - Locked silhouettes for uncollected Pokemon
    - Pokedex completion % at the top
    - Showcase section with up to 6 pinned stickers
    """

    template_name = "stickers/album.html"

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

        context = self.get_context_data(**kwargs)
        context["pack"] = pack
        context["revealed_stickers"] = stickers
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
            owner=self.request.user, is_trading=False
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
            owner=self.request.user, is_trading=False
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["pack_price"] = PACK_PRICE_RYO
        context["pack_price_10"] = PACK_PRICE_RYO * 10
        context["can_afford"] = self.request.user.ryo >= PACK_PRICE_RYO
        context["can_afford_10"] = self.request.user.ryo >= PACK_PRICE_RYO * 10
        return context

    def post(self, request, *args, **kwargs):
        try:
            pack = _sticker_service.buy_pack(request.user)
        except ValueError as exc:
            context = self.get_context_data(error=str(exc), **kwargs)
            return self.render_to_response(context)
        return redirect("stickers:pack_open", pk=pack.pk)


class BuyMultiPackView(LoginRequiredMixin, TemplateView):
    """Buy 10 sticker packs at once and open them all immediately."""

    template_name = "stickers/multi_pack_open.html"

    def post(self, request, *args, **kwargs):
        total_cost = PACK_PRICE_RYO * 10
        if request.user.ryo < total_cost:
            return redirect("stickers:buy_pack")
        try:
            all_stickers = []
            for _ in range(10):
                pack = _sticker_service.buy_pack(request.user)
                stickers = _sticker_service.open_pack(request.user, pack)
                all_stickers.extend(stickers)
        except ValueError as exc:
            return redirect("stickers:buy_pack")
        context = self.get_context_data(**kwargs)
        context["all_stickers"] = all_stickers
        context["pack_count"] = 10
        return self.render_to_response(context)


class DustWorkshopView(LoginRequiredMixin, TemplateView):
    """
    Unified dust economy hub — three tabs:
      • Convert Duplicates  (POST action=convert)
      • Craft a Sticker     (POST action=craft)
      • Forge a Badge       (Phase 3 — display only for now)
    """

    template_name = "stickers/workshop.html"

    def get_context_data(self, **kwargs):
        from django.db.models import Count, Min

        from .models import BADGE_CRAFT_REQUIREMENTS, CRAFT_COSTS, BadgeTier, StickerVariant

        context = super().get_context_data(**kwargs)
        context["sticker_dust"] = self.request.user.sticker_dust

        # Convert tab
        context["duplicates"] = (
            Sticker.objects.filter(owner=self.request.user, is_trading=False)
            .values("pokemon", "pokemon__name", "rarity", "variant")
            .annotate(count=Count("id"), id=Min("id"))
            .filter(count__gt=1)
        )

        # Craft tab
        context["pokemon_list"] = Pokemon.objects.select_related("primary_type").order_by("name")
        context["craft_costs"] = CRAFT_COSTS
        context["variants"] = StickerVariant.choices

        # Badge Forge tab (Phase 3 — display only)
        context["badge_requirements"] = BADGE_CRAFT_REQUIREMENTS
        context["badge_tiers"] = BadgeTier.choices

        # Active tab (passed as query param after redirect)
        context["active_tab"] = self.request.GET.get("tab", "convert")

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

        if action == "craft":
            pokemon_id = request.POST.get("pokemon_id")
            variant = request.POST.get("variant")
            rarity = request.POST.get("rarity")
            pokemon = get_object_or_404(Pokemon, pk=pokemon_id)
            try:
                _sticker_service.craft_sticker(request.user, pokemon, variant, rarity)
            except ValueError as exc:
                context = self.get_context_data(error=str(exc), **kwargs)
                return self.render_to_response(context)
            return redirect("/stickers/workshop/?tab=craft")

        return redirect("/stickers/workshop/")


# ---------------------------------------------------------------------------
# Sticker Generator (AI preview via Pollinations.ai)
# ---------------------------------------------------------------------------

class StickerGeneratorView(LoginRequiredMixin, TemplateView):
    """
    Interactive AI sticker preview tool.

    Uses Pollinations.ai as a free image source — URLs are built client-side
    in Alpine.js. No API key, no backend call, no cost.
    Prompts are tuned to the Naruto-online / chakra-ninja theme of the game.
    """

    template_name = "stickers/sticker_generator.html"

    def get_context_data(self, **kwargs):
        from apps.pokemon.models import ChakraElement

        context = super().get_context_data(**kwargs)
        context["pokemon_list"] = (
            Pokemon.objects.select_related("primary_type__chakra_element")
            .filter(pokedex_number__isnull=False)
            .order_by("pokedex_number")
            .values("pk", "name", "pokedex_number", "primary_type__name", "primary_type__chakra_element__name")
        )
        context["variants"] = StickerVariant.choices
        context["rarities"] = StickerRarity.choices
        context["chakra_elements"] = ChakraElement.Name.choices
        return context


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
        return context


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

        if not sticker_id:
            return redirect("stickers:regional_album_index")

        try:
            _album_service.place_sticker(request.user, int(sticker_id))
        except ValueError as exc:
            # Re-render the detail page with the error
            page_data = _album_service.get_page_detail(request.user, region, rarity)
            return self.response_class(
                request=request,
                template=["stickers/regional_album_detail.html"],
                context={**page_data, "error": str(exc), "region_labels": REGION_LABELS,
                         "all_rarities": StickerRarity.choices},
            )

        if redirect_to == "scene" and page_number:
            return redirect("stickers:album_scene_page", region=region,
                            page_number=int(page_number), rarity=rarity)
        return redirect("stickers:regional_album_detail", region=region, rarity=rarity)


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
