"""Views for the users app."""

import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import DetailView, FormView

from apps.stickers.collection_stats import build_personal_collection_stats

from .forms import RegistrationForm
from .services import DAILY_REWARD_RYO, buy_candy, can_claim_daily, claim_daily_reward, get_candy_inventory

User = get_user_model()

logger = logging.getLogger(__name__)


def landing(request):
    """Public landing page. Logged-in users are sent to their dashboard."""
    if request.user.is_authenticated:
        return redirect("dashboard")

    from apps.pokemon.models import Pokemon

    featured_names = ["Charizard", "Vaporeon", "Jolteon", "Venusaur", "Espeon", "Lapras"]
    qs = (
        Pokemon.objects.filter(name__in=featured_names)
        .select_related("primary_type", "secondary_type")
        .prefetch_related("moves__trigger_status", "moves__applies_status")
    )
    name_order = {name: i for i, name in enumerate(featured_names)}
    featured_pokemon = sorted(qs, key=lambda p: name_order.get(p.name, 99))

    return render(request, "landing/landing.html", {"featured_pokemon": featured_pokemon})


@login_required
def dashboard(request):
    """Logged-in home page for the current collector-first experience."""
    return redirect("game:home")


class RegisterView(FormView):
    """Registration view that creates a new user and redirects to login."""

    template_name = "registration/register.html"
    form_class = RegistrationForm

    def form_valid(self, form: RegistrationForm):
        user_model = get_user_model()

        user_model.objects.create_user(
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
    """Public amigo profile with collection, quest, and guild progress."""

    model = User
    template_name = "users/profile.html"
    context_object_name = "profile_user"
    slug_field = "username"
    slug_url_kwarg = "username"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile_user = self.object

        from apps.quests.models import QuestType, UserQuest
        from apps.stickers.models import Sticker, StickerRarity

        showcase = list(
            Sticker.objects.filter(owner=profile_user, is_showcase=True)
            .select_related("pokemon")
            .order_by("-rarity", "-date_caught")[:6]
        )
        sticker_qs = Sticker.objects.filter(owner=profile_user)
        rarity_counts = dict(
            sticker_qs.values_list("rarity").annotate(n=Count("id")).values_list("rarity", "n")
        )
        story_quests = list(
            UserQuest.objects.filter(
                user=profile_user,
                template__quest_type=QuestType.STORY,
                period_key="story",
            )
            .select_related("template")
            .order_by("template__order")
        )
        collection_stats = build_personal_collection_stats(profile_user)
        guild_membership = getattr(profile_user, "guild_membership", None)

        context.update(
            {
                "showcase_stickers": showcase,
                "stickers_total": sticker_qs.count(),
                "placed_stickers_total": sticker_qs.filter(is_album_placed=True).count(),
                "rarity_counts": rarity_counts,
                "StickerRarity": StickerRarity,
                "collection_stats": collection_stats,
                "badges": _compute_badges(profile_user, rarity_counts, collection_stats),
                "story_quests": story_quests,
                "story_completed_count": sum(1 for quest in story_quests if quest.completed),
                "story_total_count": len(story_quests),
                "guild_membership": guild_membership,
                "is_own_profile": self.request.user == profile_user,
            }
        )

        if self.request.user == profile_user:
            from .services import WEEKLY_LOGIN_STREAK
            from apps.game.fun import get_user_pending_loteria_claims

            streak = profile_user.daily_claim_streak
            days_until_bundle = WEEKLY_LOGIN_STREAK - (streak % WEEKLY_LOGIN_STREAK)
            if days_until_bundle == WEEKLY_LOGIN_STREAK:
                days_until_bundle = 0
            days_filled = WEEKLY_LOGIN_STREAK - days_until_bundle
            context["login_streak"] = streak
            context["days_until_bundle"] = days_until_bundle
            context["days_filled"] = days_filled
            context["weekly_streak"] = WEEKLY_LOGIN_STREAK
            context["can_claim_daily"] = can_claim_daily(profile_user)
            pending_loteria_claims = list(get_user_pending_loteria_claims(profile_user)[:8])
            context["pending_loteria_claims"] = pending_loteria_claims
            context["pending_loteria_total"] = sum(claim.reward_ryo for claim in pending_loteria_claims)

        return context


def _compute_badges(user: "User", rarity_counts: dict, collection_stats) -> list[dict]:
    """Return a profile badge list aligned with the sticker-first experience."""
    from apps.stickers.models import StickerRarity

    total_stickers = sum(rarity_counts.values())

    return [
        {
            "icon": "AL",
            "name": "Album Starter",
            "description": "Place your first soul-bound sticker.",
            "rarity": "Common",
            "earned": collection_stats.soul_bound_count >= 1,
        },
        {
            "icon": "RW",
            "name": "Row Builder",
            "description": "Complete your first album row.",
            "rarity": "Uncommon",
            "earned": collection_stats.row_completions >= 1,
        },
        {
            "icon": "CL",
            "name": "Column Keeper",
            "description": "Complete your first album column.",
            "rarity": "Rare",
            "earned": collection_stats.column_completions >= 1,
        },
        {
            "icon": "GN",
            "name": "Generation Keeper",
            "description": "Complete one full generation in the album.",
            "rarity": "Epic",
            "earned": collection_stats.generation_completions >= 1,
        },
        {
            "icon": "ST",
            "name": "Collector",
            "description": "Own 50 stickers.",
            "rarity": "Uncommon",
            "earned": total_stickers >= 50,
        },
        {
            "icon": "AR",
            "name": "Archivist",
            "description": "Own 200 stickers.",
            "rarity": "Rare",
            "earned": total_stickers >= 200,
        },
        {
            "icon": "SR",
            "name": "Secret Hunter",
            "description": "Own at least 1 Secret Rare sticker.",
            "rarity": "Epic",
            "earned": rarity_counts.get(StickerRarity.SECRET_RARE, 0) >= 1,
        },
        {
            "icon": "QD",
            "name": "Daily Devotion",
            "description": "Claim your daily reward 30 days in a row.",
            "rarity": "Rare",
            "earned": user.max_daily_claim_streak >= 30,
        },
        {
            "icon": "GD",
            "name": "Guildmate",
            "description": "Join a guild.",
            "rarity": "Uncommon",
            "earned": hasattr(user, "guild_membership"),
        },
        {
            "icon": "ST",
            "name": "Story Runner",
            "description": "Complete 5 story quests.",
            "rarity": "Rare",
            "earned": user.quests.filter(period_key="story", completed=True).count() >= 5,
        },
        {
            "icon": "RY",
            "name": "Ryo Reserve",
            "description": "Reach 5,000 Ryo.",
            "rarity": "Epic",
            "earned": user.ryo >= 5000,
        },
    ]


class DailyClaimView(LoginRequiredMixin, View):
    """GET shows claim status. POST attempts to claim the daily Ryo reward."""

    def get(self, request):
        user = request.user
        user.refresh_from_db(fields=["ryo", "last_daily_claim", "daily_claim_streak"])
        from .services import WEEKLY_LOGIN_STREAK

        streak = user.daily_claim_streak
        days_until_bundle = WEEKLY_LOGIN_STREAK - (streak % WEEKLY_LOGIN_STREAK)
        if days_until_bundle == WEEKLY_LOGIN_STREAK:
            days_until_bundle = 0
        return render(
            request,
            "users/daily_claim.html",
            {
                "can_claim": can_claim_daily(user),
                "daily_amount": DAILY_REWARD_RYO,
                "ryo": user.ryo,
                "last_claim": user.last_daily_claim,
                "streak": streak,
                "days_until_bundle": days_until_bundle,
                "weekly_streak": WEEKLY_LOGIN_STREAK,
            },
        )

    def post(self, request):
        user = request.user
        try:
            result = claim_daily_reward(user)
            msg = f"Daily reward claimed! +{result['ryo']} Ryo"
            if result["bundle_pack"]:
                msg += " + Bundle Pack (7-day streak bonus!)"
            messages.success(request, msg)
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("users:daily_claim")


class BuyCandyAPI(LoginRequiredMixin, View):
    """POST endpoint to purchase one candy with Ryo."""

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
        return JsonResponse(
            {
                "ryo": request.user.ryo,
                "candy_trail_mix": request.user.candy_trail_mix,
                "candy_sweet_berry": request.user.candy_sweet_berry,
                "candy_golden_apple": request.user.candy_golden_apple,
                "costs": {k: v["cost"] for k, v in inventory.items()},
            }
        )
