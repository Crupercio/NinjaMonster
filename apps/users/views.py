"""Views for the users app."""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.http import JsonResponse
from django.views import View
from django.views.generic import DetailView, FormView

from .forms import RegistrationForm
from .services import CANDY_COSTS, DAILY_REWARD_RYO, buy_candy, can_claim_daily, claim_daily_reward, get_candy_inventory

User = get_user_model()

logger = logging.getLogger(__name__)


def landing(request):
    """Public landing page. Logged-in users are sent to their dashboard."""
    if request.user.is_authenticated:
        return redirect("dashboard")

    from apps.pokemon.models import Pokemon

    featured_names = ["Charizard", "Vaporeon", "Jolteon", "Venusaur", "Espeon", "Lapras"]
    qs = (
        Pokemon.objects
        .filter(name__in=featured_names)
        .select_related("primary_type", "secondary_type")
        .prefetch_related("moves__trigger_status", "moves__applies_status")
    )
    name_order = {name: i for i, name in enumerate(featured_names)}
    featured_pokemon = sorted(qs, key=lambda p: name_order.get(p.name, 99))

    return render(request, "landing/landing.html", {"featured_pokemon": featured_pokemon})


@login_required
def dashboard(request):
    """Logged-in trainer home page. Redirects new trainers to the tutorial."""
    if not request.user.tutorial_complete:
        return redirect("game:tutorial")
    return render(request, "game/home.html", {"user": request.user})


class RegisterView(FormView):
    """Trainer registration — creates a new user and redirects to login."""

    template_name = "registration/register.html"
    form_class = RegistrationForm

    def form_valid(self, form: RegistrationForm):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        User.objects.create_user(
            username=form.cleaned_data["username"],
            email=form.cleaned_data["email"],
            password=form.cleaned_data["password"],
            display_name=form.cleaned_data["username"],
        )
        logger.info("New trainer registered: %s", form.cleaned_data["username"])
        messages.success(
            self.request,
            f"Account created! Welcome, {form.cleaned_data['username']}. Please log in.",
        )
        return redirect("login")

    def form_invalid(self, form: RegistrationForm):
        return self.render_to_response(self.get_context_data(form=form))


class TrainerProfileView(LoginRequiredMixin, DetailView):
    """
    Public trainer profile — stats, showcase stickers, achievement badges,
    and recent battles.  Accessible at /accounts/profile/<username>/.
    """

    model = User
    template_name = "users/profile.html"
    context_object_name = "profile_user"
    slug_field = "username"
    slug_url_kwarg = "username"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile_user = self.object

        # ── Showcase stickers (is_showcase=True, up to 6) ───────────────────
        from apps.stickers.models import Sticker, StickerRarity
        showcase = list(
            Sticker.objects.filter(owner=profile_user, is_showcase=True)
            .select_related("pokemon")
            .order_by("-rarity", "-date_caught")[:6]
        )
        context["showcase_stickers"] = showcase

        # ── Sticker collection stats ─────────────────────────────────────────
        sticker_qs = Sticker.objects.filter(owner=profile_user)
        context["stickers_total"] = sticker_qs.count()
        rarity_counts = dict(
            sticker_qs.values_list("rarity").annotate(n=Count("id")).values_list("rarity", "n")
        )
        context["rarity_counts"] = rarity_counts
        context["StickerRarity"] = StickerRarity

        # ── Achievement badges (GDD Section 14.4) ───────────────────────────
        context["badges"] = _compute_badges(profile_user, rarity_counts)

        # ── Recent battles (last 10) ─────────────────────────────────────────
        from apps.game.models import Battle
        recent_battles = list(
            Battle.objects.filter(
                Q(player_one=profile_user) | Q(player_two=profile_user)
            )
            .select_related("player_one", "player_two", "winner")
            .order_by("-created_at")[:10]
        )
        context["recent_battles"] = recent_battles

        # ── Completed story quests ───────────────────────────────────────────
        from apps.quests.models import QuestType, UserQuest
        context["story_quests"] = list(
            UserQuest.objects.filter(
                user=profile_user,
                template__quest_type=QuestType.STORY,
                period_key="story",
            ).select_related("template").order_by("template__order")
        )

        context["is_own_profile"] = self.request.user == profile_user
        return context


def _compute_badges(user: "User", rarity_counts: dict) -> list[dict]:
    """
    Return a list of badge dicts from GDD Section 14.4 (all 13 badges).

    Each dict: {icon, name, description, rarity, earned}
    """
    from apps.stickers.models import StickerRarity

    total_stickers = sum(rarity_counts.values())

    return [
        {
            "icon": "⚡",
            "name": "Chain Initiate",
            "description": "Achieve your first 2-link combo chain.",
            "rarity": "Common",
            "earned": user.longest_combo_chain >= 2,
        },
        {
            "icon": "🔥",
            "name": "Chain Warrior",
            "description": "Achieve a 5-link combo chain.",
            "rarity": "Uncommon",
            "earned": user.longest_combo_chain >= 5,
        },
        {
            "icon": "🌀",
            "name": "Chain Master",
            "description": "Achieve a 10-link combo chain.",
            "rarity": "Rare",
            "earned": user.longest_combo_chain >= 10,
        },
        {
            "icon": "🏆",
            "name": "First Victory",
            "description": "Win your first battle.",
            "rarity": "Common",
            "earned": user.battles_won >= 1,
        },
        {
            "icon": "💯",
            "name": "Centurion",
            "description": "Win 100 battles.",
            "rarity": "Rare",
            "earned": user.battles_won >= 100,
        },
        {
            "icon": "📖",
            "name": "Collector",
            "description": "Own 50 stickers.",
            "rarity": "Uncommon",
            "earned": total_stickers >= 50,
        },
        {
            "icon": "🌟",
            "name": "Archivist",
            "description": "Own 200 stickers.",
            "rarity": "Rare",
            "earned": total_stickers >= 200,
        },
        {
            "icon": "💎",
            "name": "Secret Hunter",
            "description": "Own at least 1 Secret Rare sticker.",
            "rarity": "Epic",
            "earned": rarity_counts.get(StickerRarity.SECRET_RARE, 0) >= 1,
        },
        {
            "icon": "🤝",
            "name": "Trader",
            "description": "Complete 10 trades with other trainers.",
            "rarity": "Uncommon",
            "earned": user.trades_completed >= 10,
        },
        {
            "icon": "☀️",
            "name": "Daily Devotion",
            "description": "Claim your daily reward 30 days in a row.",
            "rarity": "Rare",
            "earned": user.max_daily_claim_streak >= 30,
        },
        {
            "icon": "🎯",
            "name": "Perfect Victory",
            "description": "Win a battle with no Pokémon fainted on your team.",
            "rarity": "Uncommon",
            "earned": user.perfect_victories >= 1,
        },
        {
            "icon": "🤖",
            "name": "AI Breaker",
            "description": "Defeat the Hard AI opponent 10 times.",
            "rarity": "Rare",
            "earned": user.hard_ai_wins >= 10,
        },
        {
            "icon": "👑",
            "name": "Champion",
            "description": "Reach Diamond tier in PvP ranked play.",
            "rarity": "Epic",
            "earned": False,  # PvP ranked not yet implemented (GDD §15.3)
        },
    ]


class DailyClaimView(LoginRequiredMixin, View):
    """GET  /accounts/daily-claim/ — show claim status.
    POST /accounts/daily-claim/ — attempt to claim daily Ryo reward.
    """

    def get(self, request):
        user = request.user
        user.refresh_from_db(fields=["ryo", "last_daily_claim"])
        return render(
            request,
            "users/daily_claim.html",
            {
                "can_claim": can_claim_daily(user),
                "daily_amount": DAILY_REWARD_RYO,
                "ryo": user.ryo,
                "last_claim": user.last_daily_claim,
            },
        )

    def post(self, request):
        user = request.user
        try:
            amount = claim_daily_reward(user)
            messages.success(request, f"Daily reward claimed! +{amount} Ryo")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("users:daily_claim")


class BuyCandyAPI(LoginRequiredMixin, View):
    """POST /accounts/buy-candy/ — purchase one candy with Ryo."""

    def post(self, request):
        import json
        try:
            body = json.loads(request.body)
            candy_type = body.get("candy_type", "")
        except (ValueError, KeyError):
            return JsonResponse({"error": "Invalid request."}, status=400)

        try:
            buy_candy(request.user, candy_type)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        request.user.refresh_from_db()
        inventory = get_candy_inventory(request.user)
        return JsonResponse({
            "ryo": request.user.ryo,
            "candy_trail_mix": request.user.candy_trail_mix,
            "candy_sweet_berry": request.user.candy_sweet_berry,
            "candy_golden_apple": request.user.candy_golden_apple,
            "costs": {k: v["cost"] for k, v in inventory.items()},
        })
