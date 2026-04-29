"""Views for the collection leaderboard surfaces."""

import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views.generic import TemplateView, View

from apps.stickers.collection_stats import build_user_leaderboard

logger = logging.getLogger(__name__)


class RankedHomeView(LoginRequiredMixin, View):
    """The ranked hub is hidden for now; send users to the leaderboard."""

    def get(self, request, *args, **kwargs):
        return redirect("ranked:leaderboard")


class QueueJoinView(LoginRequiredMixin, View):
    """Ranked queue is hidden for now."""

    def post(self, request, *args, **kwargs):
        return redirect("ranked:leaderboard")


class QueueLeaveView(LoginRequiredMixin, View):
    """Ranked queue is hidden for now."""

    def post(self, request, *args, **kwargs):
        return redirect("ranked:leaderboard")


class QueueStatusView(LoginRequiredMixin, View):
    """Ranked queue is hidden for now."""

    def get(self, request, *args, **kwargs):
        return redirect("ranked:leaderboard")


class LeaderboardView(LoginRequiredMixin, TemplateView):
    """Sticker-first personal leaderboard."""

    template_name = "ranked/leaderboard.html"
    _PAGE_SIZE = 100
    _VALID_TABS = frozenset({"score", "soulbound", "completion", "generations"})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tab = self.request.GET.get("tab", "score")
        if tab not in self._VALID_TABS:
            tab = "score"

        rows = build_user_leaderboard(limit=self._PAGE_SIZE)

        if tab == "soulbound":
            rows.sort(
                key=lambda row: (
                    -row["stats"].soul_bound_count,
                    -row["stats"].total_score,
                    row["user"].username.lower(),
                )
            )
        elif tab == "completion":
            rows.sort(
                key=lambda row: (
                    -(row["stats"].row_completions + row["stats"].column_completions),
                    -row["stats"].column_completions,
                    -row["stats"].row_completions,
                    -row["stats"].total_score,
                    row["user"].username.lower(),
                )
            )
        elif tab == "generations":
            rows.sort(
                key=lambda row: (
                    -row["stats"].generation_completions,
                    -row["stats"].total_score,
                    row["user"].username.lower(),
                )
            )

        context["tab"] = tab
        context["rows"] = rows
        return context
