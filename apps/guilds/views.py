"""Views for the guild system."""
import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView, TemplateView

from .models import GUILD_CREATE_COST_RYO, Guild
from .services import GuildService

logger = logging.getLogger(__name__)
_guild_service = GuildService()


class GuildListView(LoginRequiredMixin, ListView):
    """GET /guilds/ — public list of all guilds ordered by member count."""

    model = Guild
    template_name = "guilds/guild_list.html"
    context_object_name = "guilds"
    paginate_by = 20

    def get_queryset(self):
        return Guild.objects.prefetch_related("memberships").order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["my_membership"] = _guild_service.get_membership(self.request.user)
        return context


class GuildDetailView(LoginRequiredMixin, TemplateView):
    """GET /guilds/<pk>/ — guild detail with members and stats."""

    template_name = "guilds/guild_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        guild = get_object_or_404(Guild, pk=kwargs["pk"])
        memberships = guild.memberships.select_related("user").order_by("joined_at")
        my_membership = _guild_service.get_membership(self.request.user)
        stats = _guild_service.get_guild_stats(guild)
        context.update({
            "guild": guild,
            "memberships": memberships,
            "my_membership": my_membership,
            "in_this_guild": my_membership is not None and my_membership.guild_id == guild.pk,
            "stats": stats,
        })
        return context


class GuildCreateView(LoginRequiredMixin, TemplateView):
    """GET/POST /guilds/create/"""

    template_name = "guilds/guild_create.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["create_cost"] = GUILD_CREATE_COST_RYO
        return context

    def post(self, request):
        name = request.POST.get("name", "").strip()
        tag = request.POST.get("tag", "").strip().upper()
        description = request.POST.get("description", "").strip()
        if not name or not tag:
            messages.error(request, "Name and tag are required.")
            return redirect("guilds:create")
        try:
            guild = _guild_service.create_guild(request.user, name, tag, description)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("guilds:create")
        messages.success(request, f"Guild [{guild.tag}] {guild.name} created!")
        return redirect("guilds:detail", pk=guild.pk)


class GuildJoinView(LoginRequiredMixin, View):
    """POST /guilds/<pk>/join/"""

    def post(self, request, pk: int):
        guild = get_object_or_404(Guild, pk=pk)
        try:
            _guild_service.join_guild(request.user, guild)
            messages.success(request, f"You joined [{guild.tag}] {guild.name}!")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("guilds:detail", pk=pk)


class GuildLeaveView(LoginRequiredMixin, View):
    """POST /guilds/leave/"""

    def post(self, request):
        try:
            _guild_service.leave_guild(request.user)
            messages.success(request, "You have left your guild.")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("guilds:list")


class GuildKickView(LoginRequiredMixin, View):
    """POST /guilds/<pk>/kick/<user_pk>/"""

    def post(self, request, pk: int, user_pk: int):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        target = get_object_or_404(User, pk=user_pk)
        try:
            _guild_service.kick_member(request.user, target)
            messages.success(request, f"{target} has been removed from the guild.")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("guilds:detail", pk=pk)


class GuildPromoteView(LoginRequiredMixin, View):
    """POST /guilds/<pk>/promote/<user_pk>/"""

    def post(self, request, pk: int, user_pk: int):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        target = get_object_or_404(User, pk=user_pk)
        try:
            _guild_service.promote_to_officer(request.user, target)
            messages.success(request, f"{target} is now an officer.")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("guilds:detail", pk=pk)


class GuildDemoteView(LoginRequiredMixin, View):
    """POST /guilds/<pk>/demote/<user_pk>/"""

    def post(self, request, pk: int, user_pk: int):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        target = get_object_or_404(User, pk=user_pk)
        try:
            _guild_service.demote_to_member(request.user, target)
            messages.success(request, f"{target} has been demoted to member.")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("guilds:detail", pk=pk)
