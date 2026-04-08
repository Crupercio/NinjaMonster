"""Views for the ranked PvP matchmaking, season system, and leaderboard."""
import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views.generic import TemplateView, View

from .models import MatchmakingStatus
from .services import MatchmakingService, RankedSeasonService

User = get_user_model()

logger = logging.getLogger(__name__)

_ranked_svc = RankedSeasonService()
_matchmaking_svc = MatchmakingService()


class RankedHomeView(LoginRequiredMixin, TemplateView):
    """Ranked hub: current tier, season info, and queue entry."""

    template_name = "ranked/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        season = _ranked_svc.get_active_season()
        context["season"] = season

        if season:
            profile = _ranked_svc.get_or_create_profile(user, season)
            context["profile"] = profile
        else:
            context["profile"] = None

        # Current queue status for this player.
        entry = _matchmaking_svc.get_latest_entry(user)
        context["queue_entry"] = entry
        context["in_queue"] = entry is not None and entry.status == MatchmakingStatus.WAITING

        # Waiting players count (excludes self).
        from .models import MatchmakingEntry
        context["queue_size"] = (
            MatchmakingEntry.objects.filter(status=MatchmakingStatus.WAITING)
            .exclude(user=user)
            .count()
        )

        return context


class QueueJoinView(LoginRequiredMixin, View):
    """POST — join the matchmaking queue."""

    def post(self, request, *args, **kwargs):
        entry = _matchmaking_svc.join_queue(request.user)

        if entry.status == MatchmakingStatus.MATCHED and entry.battle_id:
            # Immediately redirect to the matched battle.
            return redirect("game:team_select", battle_id=entry.battle_id)

        return redirect("ranked:home")


class QueueLeaveView(LoginRequiredMixin, View):
    """POST — leave the matchmaking queue."""

    def post(self, request, *args, **kwargs):
        _matchmaking_svc.leave_queue(request.user)
        return redirect("ranked:home")


class QueueStatusView(LoginRequiredMixin, View):
    """
    GET — HTMX polling endpoint.

    Returns an HTML fragment or a redirect trigger so the client can
    navigate to the battle page once matched.
    """

    def get(self, request, *args, **kwargs):
        entry = _matchmaking_svc.get_latest_entry(request.user)

        if entry is None or entry.status == MatchmakingStatus.CANCELLED:
            return HttpResponse(
                '<span style="color:#9ca3af;">Not in queue.</span>',
                content_type="text/html",
            )

        if entry.status == MatchmakingStatus.MATCHED and entry.battle_id:
            # Signal the client to navigate away.
            response = HttpResponse(status=200)
            response["HX-Redirect"] = f"/battle/{entry.battle_id}/team/"
            return response

        # Still waiting — return fragment with queue status.
        from .models import MatchmakingEntry
        position = (
            MatchmakingEntry.objects.filter(
                status=MatchmakingStatus.WAITING,
                entered_at__lte=entry.entered_at,
            ).count()
        )
        html = (
            f'<span style="color:#fcd34d;">Searching for opponent… '
            f'(#{position} in queue)</span>'
        )
        return HttpResponse(html, content_type="text/html")


class LeaderboardView(LoginRequiredMixin, TemplateView):
    """
    Global leaderboard — three tabs (GDD §20.9):
      wins  — all-time battles_won
      combo — all-time longest_combo_chain
      season — current season rank points
    """

    template_name = "ranked/leaderboard.html"
    _PAGE_SIZE = 100

    _VALID_TABS = frozenset({"wins", "combo", "season"})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tab = self.request.GET.get("tab", "wins")
        if tab not in self._VALID_TABS:
            tab = "wins"
        context["tab"] = tab

        ai_username = "__ai_trainer__"

        if tab == "wins":
            context["rows"] = (
                User.objects.exclude(username=ai_username)
                .order_by("-battles_won", "-longest_combo_chain")
                .values("username", "battles_won", "battles_played", "longest_combo_chain")
                [: self._PAGE_SIZE]
            )
        elif tab == "combo":
            context["rows"] = (
                User.objects.exclude(username=ai_username)
                .filter(longest_combo_chain__gt=0)
                .order_by("-longest_combo_chain", "-battles_won")
                .values("username", "longest_combo_chain", "battles_won")
                [: self._PAGE_SIZE]
            )
        else:  # season
            season = _ranked_svc.get_active_season()
            context["season"] = season
            if season:
                from .models import RankedProfile
                context["rows"] = (
                    RankedProfile.objects.filter(season=season)
                    .select_related("user")
                    .order_by("-rank_points")
                    [: self._PAGE_SIZE]
                )
            else:
                context["rows"] = []

        return context
