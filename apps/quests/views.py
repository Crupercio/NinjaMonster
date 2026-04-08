"""Views for the quest & mission system."""
import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import TemplateView

from .models import UserQuest
from .services import QuestService

logger = logging.getLogger(__name__)

_quest_service = QuestService()


class QuestListView(LoginRequiredMixin, TemplateView):
    """Daily / weekly / story quest tracker."""

    template_name = "quests/quest_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        quests = _quest_service.get_quests_for_display(self.request.user)
        context.update(quests)
        return context


class QuestClaimView(LoginRequiredMixin, View):
    """POST /quests/<pk>/claim/ — claim the reward for a completed quest."""

    def post(self, request, pk: int):
        uq = get_object_or_404(UserQuest, pk=pk, user=request.user)
        try:
            summary = _quest_service.claim_reward(request.user, uq)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("quests:quest_list")

        parts = []
        if "ryo" in summary:
            parts.append(f"+{summary['ryo']} Ryo")
        if "sticker_dust" in summary:
            parts.append(f"+{summary['sticker_dust']} Dust")
        if "sticker_pack" in summary:
            parts.append("+1 Sticker Pack")

        reward_text = ", ".join(parts) or "reward granted"
        messages.success(request, f"Reward claimed: {reward_text}!")
        return redirect("quests:quest_list")
