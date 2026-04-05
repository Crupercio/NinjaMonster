"""Class-based views for the sticker collection app."""
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import DetailView, ListView, TemplateView

from apps.pokemon.models import Pokemon

from .models import Sticker, StickerPack, TradeOffer
from .services import PACK_PRICE_RYO, StickerService, TradeService

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
        return context


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
        context["can_afford"] = self.request.user.ryo >= PACK_PRICE_RYO
        return context

    def post(self, request, *args, **kwargs):
        try:
            pack = _sticker_service.buy_pack(request.user)
        except ValueError as exc:
            context = self.get_context_data(error=str(exc), **kwargs)
            return self.render_to_response(context)
        return redirect("stickers:pack_open", pk=pack.pk)


class DustConvertView(LoginRequiredMixin, TemplateView):
    """Convert duplicate stickers to sticker dust."""

    template_name = "stickers/dust_convert.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.db.models import Count

        # Show stickers where owner has more than one copy of the same combination
        context["duplicates"] = (
            Sticker.objects.filter(owner=self.request.user, is_trading=False)
            .values("pokemon", "rarity", "variant")
            .annotate(count=Count("id"))
            .filter(count__gt=1)
            .select_related()
        )
        context["sticker_dust"] = self.request.user.sticker_dust
        return context

    def post(self, request, *args, **kwargs):
        sticker_id = request.POST.get("sticker_id")
        sticker = get_object_or_404(Sticker, pk=sticker_id, owner=request.user)
        try:
            dust = _sticker_service.convert_duplicate(request.user, sticker)
        except ValueError as exc:
            context = self.get_context_data(error=str(exc), **kwargs)
            return self.render_to_response(context)
        return redirect("stickers:album")


class CraftView(LoginRequiredMixin, TemplateView):
    """Spend sticker dust to craft a specific sticker."""

    template_name = "stickers/craft.html"

    def get_context_data(self, **kwargs):
        from .models import CRAFT_COSTS, StickerVariant

        context = super().get_context_data(**kwargs)
        context["pokemon_list"] = Pokemon.objects.select_related("primary_type").order_by("name")
        context["craft_costs"] = CRAFT_COSTS
        context["variants"] = StickerVariant.choices
        context["sticker_dust"] = self.request.user.sticker_dust
        return context

    def post(self, request, *args, **kwargs):
        pokemon_id = request.POST.get("pokemon_id")
        variant = request.POST.get("variant")
        rarity = request.POST.get("rarity")

        pokemon = get_object_or_404(Pokemon, pk=pokemon_id)
        try:
            _sticker_service.craft_sticker(request.user, pokemon, variant, rarity)
        except ValueError as exc:
            context = self.get_context_data(error=str(exc), **kwargs)
            return self.render_to_response(context)
        return redirect("stickers:album")
