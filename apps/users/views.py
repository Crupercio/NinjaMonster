"""Views for the users app."""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import FormView

from .forms import RegistrationForm
from .services import DAILY_REWARD_RYO, can_claim_daily, claim_daily_reward

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
    """Logged-in trainer home page — reuses the existing game home template."""
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
