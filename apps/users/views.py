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
from .services import DAILY_REWARD_RYO, buy_candy, can_claim_daily, claim_arcade_daily_challenge, claim_daily_reward, get_candy_inventory

User = get_user_model()

logger = logging.getLogger(__name__)


def landing(request):
    """Public landing page. Logged-in users are sent to their dashboard."""
    if request.user.is_authenticated:
        return redirect("dashboard")

    from apps.pokemon.models import Pokemon
    from apps.stickers.models import StickerRarity, StickerVariant

    featured_showcase = [
        {
            "pokemon_name": "Charizard",
            "rarity": StickerRarity.FULL_ART,
            "variant": StickerVariant.BATTLE_SCENE,
            "fit": "fit-small",
            "caption": "A big showcase pull that feels like a boss clear for your album.",
        },
        {
            "pokemon_name": "Vaporeon",
            "rarity": StickerRarity.PRISMATIC,
            "variant": StickerVariant.GLITTER,
            "fit": "fit-tall",
            "caption": "A trade-friendly foil chase built for collectors who like flashier pages.",
        },
        {
            "pokemon_name": "Jolteon",
            "rarity": StickerRarity.RARE,
            "variant": StickerVariant.SHINY,
            "fit": "fit-compact",
            "caption": "A clean mid-tier hit that keeps album progress feeling rewarding.",
        },
        {
            "pokemon_name": "Venusaur",
            "rarity": StickerRarity.COMMON,
            "variant": StickerVariant.BASE,
            "fit": "fit-wide",
            "caption": "The kind of staple card that quietly fills real album rows fast.",
        },
        {
            "pokemon_name": "Espeon",
            "rarity": StickerRarity.EPIC,
            "variant": StickerVariant.WATERCOLOR,
            "fit": "fit-tall",
            "caption": "A premium variant that starts turning a collection into a curated shelf.",
        },
    ]
    album_preview = [
        {
            "pokemon_name": "Bulbasaur",
            "rarity": StickerRarity.COMMON,
            "fit": "fit-wide",
            "slots": [
                {"variant": StickerVariant.BASE, "collected": True},
                {"variant": StickerVariant.SHINY, "collected": True},
                {"variant": StickerVariant.WATERCOLOR, "collected": False},
                {"variant": StickerVariant.CARTOON, "collected": False},
            ],
        },
        {
            "pokemon_name": "Eevee",
            "rarity": StickerRarity.RARE,
            "fit": "fit-compact",
            "slots": [
                {"variant": StickerVariant.TV_90S, "collected": True},
                {"variant": StickerVariant.COLOR_SWAP, "collected": True},
                {"variant": StickerVariant.SKETCH, "collected": False},
                {"variant": StickerVariant.BURN_SCROLL, "collected": False},
            ],
        },
        {
            "pokemon_name": "Lapras",
            "rarity": StickerRarity.PRISMATIC,
            "fit": "fit-wide",
            "slots": [
                {"variant": StickerVariant.GLITTER, "collected": True},
                {"variant": StickerVariant.CHROME, "collected": False},
                {"variant": StickerVariant.NEON_GLOW, "collected": True},
                {"variant": StickerVariant.BATTLE_SCENE, "collected": False},
            ],
        },
    ]
    rarity_showcase = [
        {
            "rarity": "common",
            "label": "Common",
            "pokemon_name": "Bulbasaur",
            "fit": "fit-wide",
            "description": "Your everyday album backbone and the easiest way to start filling rows.",
            "craft_cost": 10,
            "badge": "Base pull",
            "variant": StickerVariant.BASE,
        },
        {
            "rarity": "uncommon",
            "label": "Uncommon",
            "pokemon_name": "Togepi",
            "fit": "fit-compact",
            "description": "A brighter pull tier that starts making duplicate conversion feel worthwhile.",
            "craft_cost": 25,
            "badge": "Spark pull",
            "variant": StickerVariant.SHINY,
        },
        {
            "rarity": "rare",
            "label": "Rare",
            "pokemon_name": "Gardevoir",
            "fit": "fit-tall",
            "description": "A satisfying hit tier for collectors chasing cleaner album progress and better showcase cards.",
            "craft_cost": 75,
            "badge": "Solid hit",
            "variant": StickerVariant.SKETCH,
        },
        {
            "rarity": "epic",
            "label": "Epic",
            "pokemon_name": "Lucario",
            "fit": "fit-tall",
            "description": "A premium pull tier that starts to feel like a real collector event when it lands.",
            "craft_cost": 150,
            "badge": "Showpiece",
            "variant": StickerVariant.BATTLE_SCENE,
        },
        {
            "rarity": "prismatic",
            "label": "Prismatic",
            "pokemon_name": "Milotic",
            "fit": "fit-tall",
            "description": "The foil-style chase tier for players who want sharper album highlights and flashier trades.",
            "craft_cost": 300,
            "badge": "Foil chase",
            "variant": StickerVariant.GLITTER,
        },
        {
            "rarity": "full_art",
            "label": "Full Art",
            "pokemon_name": "Rayquaza",
            "fit": "fit-small",
            "description": "A centerpiece card tier built to stand out in showcases, guild goals, and collector flex slots.",
            "craft_cost": 500,
            "badge": "Centerpiece",
            "variant": StickerVariant.COLOR_SWAP,
        },
        {
            "rarity": "secret_rare",
            "label": "Secret Rare",
            "pokemon_name": "Mewtwo",
            "fit": "fit-tall",
            "description": "The ultra-chase finish that turns a normal pack opening into a memorable collector moment.",
            "craft_cost": 1000,
            "badge": "Ultra chase",
            "variant": StickerVariant.CHROME,
        },
    ]
    required_names = {
        *[entry["pokemon_name"] for entry in featured_showcase],
        *[entry["pokemon_name"] for entry in album_preview],
        *[entry["pokemon_name"] for entry in rarity_showcase],
    }
    qs = (
        Pokemon.objects.filter(
            name__in=required_names
        )
        .select_related("primary_type", "secondary_type")
        .prefetch_related("moves__trigger_status", "moves__applies_status")
    )
    pokemon_by_name = {pokemon.name: pokemon for pokemon in qs}
    rarity_labels = {value: label for value, label in StickerRarity.choices}

    rarity_showcase_cards = []
    fallback_pool = iter(Pokemon.objects.order_by("pokedex_number")[:40])
    for entry in rarity_showcase:
        pokemon = pokemon_by_name.get(entry["pokemon_name"])
        if pokemon is None:
            pokemon = next(fallback_pool, None)
        if pokemon is None:
            continue
        rarity_showcase_cards.append(
            {
                **entry,
                "pokemon": pokemon,
                "variant_label": StickerVariant(entry["variant"]).label,
            }
        )

    featured_showcase_cards = []
    for entry in featured_showcase:
        pokemon = pokemon_by_name.get(entry["pokemon_name"])
        if pokemon is None:
            continue
        featured_showcase_cards.append(
            {
                **entry,
                "pokemon": pokemon,
                "rarity_label": rarity_labels[entry["rarity"]],
                "variant_label": StickerVariant(entry["variant"]).label,
            }
        )

    album_preview_rows = []
    for row in album_preview:
        pokemon = pokemon_by_name.get(row["pokemon_name"])
        if pokemon is None:
            continue
        album_preview_rows.append(
            {
                "pokemon": pokemon,
                "rarity": row["rarity"],
                "rarity_label": rarity_labels[row["rarity"]],
                "slots": [
                    {
                        **slot,
                        "variant_label": StickerVariant(slot["variant"]).label,
                    }
                    for slot in row["slots"]
                ],
            }
        )

    return render(
        request,
        "landing/landing.html",
        {
            "featured_showcase_cards": featured_showcase_cards,
            "album_preview_rows": album_preview_rows,
            "rarity_showcase_cards": rarity_showcase_cards,
            "pokedex_total": Pokemon.objects.count(),
        },
    )


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
        return redirect("account_login")

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


class ArcadeDailyChallengeProgressAPI(LoginRequiredMixin, View):
    """GET — return current arcade daily challenge state as JSON."""

    def get(self, request):
        from apps.game.fun import build_fun_hub_daily_challenge
        challenge = build_fun_hub_daily_challenge(request.user)
        return JsonResponse(challenge)


class ArcadeDailyChallengeClaim(LoginRequiredMixin, View):
    """POST — claim the arcade daily challenge Ryo reward."""

    def post(self, request):
        import json
        from apps.game.fun import build_fun_hub_daily_challenge

        challenge = build_fun_hub_daily_challenge(request.user)
        if not challenge["is_complete"]:
            return JsonResponse({"error": "Complete all tasks first."}, status=400)

        try:
            reward_ryo = int(challenge["reward"].replace("+", "").replace(" Ryo", "").strip())
        except (ValueError, AttributeError):
            reward_ryo = 0

        try:
            result = claim_arcade_daily_challenge(request.user, reward_ryo)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        return JsonResponse({"ryo": result["ryo"], "reward_ryo": reward_ryo})


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
