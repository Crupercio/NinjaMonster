"""Views for the guild system."""

import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView, TemplateView

from apps.game.models import LoteriaMode, LoteriaRoom, LoteriaStatus

from .models import GUILD_CREATE_COST_RYO, Guild
from .services import GuildService

logger = logging.getLogger(__name__)
_guild_service = GuildService()


class GuildListView(LoginRequiredMixin, ListView):
    """Public list of guilds."""

    model = Guild
    template_name = "guilds/guild_list.html"
    context_object_name = "guilds"
    paginate_by = 20

    def get_queryset(self):
        return Guild.objects.prefetch_related("memberships").order_by("-level", "-xp", "-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["my_membership"] = _guild_service.get_membership(self.request.user)
        return context


class GuildDetailView(LoginRequiredMixin, TemplateView):
    """Guild detail with members, perks, and guild quest progress."""

    template_name = "guilds/guild_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        guild = get_object_or_404(Guild, pk=kwargs["pk"])
        memberships = guild.memberships.select_related("user").order_by("-contribution_points", "joined_at")
        my_membership = _guild_service.get_membership(self.request.user)
        stats = _guild_service.get_guild_stats(guild)
        guild_rooms = (
            guild.loteria_rooms.select_related("created_by").prefetch_related("participants")
            .filter(
                mode=LoteriaMode.PRIVATE,
                status__in=[LoteriaStatus.DRAFT, LoteriaStatus.LOBBY, LoteriaStatus.ACTIVE],
            )
            .order_by("status", "-created_at")
        )
        active_guild_rooms = []
        for room in guild_rooms:
            participant_count = room.participants.count()
            is_participant = room.created_by_id == self.request.user.id or room.participants.filter(user=self.request.user).exists()
            active_guild_rooms.append(
                {
                    "room": room,
                    "host_name": room.created_by.username,
                    "participant_count": participant_count,
                    "is_participant": is_participant,
                    "status_label": "Live" if room.status == LoteriaStatus.ACTIVE else "Lobby",
                    "open_url_name": "game:loteria_room" if room.status == LoteriaStatus.ACTIVE else "game:loteria_lobby",
                    "can_join": my_membership is not None and my_membership.guild_id == guild.pk and room.status != LoteriaStatus.ACTIVE,
                }
            )
        context.update(
            {
                "guild": guild,
                "memberships": memberships,
                "my_membership": my_membership,
                "in_this_guild": my_membership is not None and my_membership.guild_id == guild.pk,
                "stats": stats,
                "guild_quests": _guild_service.get_guild_quests(self.request.user, guild),
                "guild_loteria_rooms": active_guild_rooms,
            }
        )
        return context


class GuildAlbumView(LoginRequiredMixin, TemplateView):
    """Guild album and donation page."""

    template_name = "guilds/guild_album.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        guild = get_object_or_404(Guild, pk=kwargs["pk"])
        my_membership = _guild_service.get_membership(self.request.user)
        stats = _guild_service.get_guild_stats(guild)
        context.update(
            {
                "guild": guild,
                "my_membership": my_membership,
                "in_this_guild": my_membership is not None and my_membership.guild_id == guild.pk,
                "stats": stats,
                "album_entries": _guild_service.get_guild_album_entries(guild),
                "donation_stickers": _guild_service.get_available_guild_donation_stickers(self.request.user, guild),
                "guild_quests": _guild_service.get_guild_quests(self.request.user, guild),
            }
        )
        return context


class GuildCreateView(LoginRequiredMixin, TemplateView):
    """Guild create page."""

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
    """Join a guild."""

    def post(self, request, pk: int):
        guild = get_object_or_404(Guild, pk=pk)
        try:
            _guild_service.join_guild(request.user, guild)
            messages.success(request, f"You joined [{guild.tag}] {guild.name}!")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("guilds:detail", pk=pk)


class GuildLeaveView(LoginRequiredMixin, View):
    """Leave the current guild."""

    def post(self, request):
        try:
            _guild_service.leave_guild(request.user)
            messages.success(request, "You have left your guild.")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("guilds:list")


class GuildKickView(LoginRequiredMixin, View):
    """Kick a guild member."""

    def post(self, request, pk: int, user_pk: int):
        from django.contrib.auth import get_user_model

        user_model = get_user_model()
        target = get_object_or_404(user_model, pk=user_pk)
        try:
            _guild_service.kick_member(request.user, target)
            messages.success(request, f"{target} has been removed from the guild.")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("guilds:detail", pk=pk)


class GuildPromoteView(LoginRequiredMixin, View):
    """Promote a guild member."""

    def post(self, request, pk: int, user_pk: int):
        from django.contrib.auth import get_user_model

        user_model = get_user_model()
        target = get_object_or_404(user_model, pk=user_pk)
        try:
            _guild_service.promote_to_officer(request.user, target)
            messages.success(request, f"{target} is now an officer.")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("guilds:detail", pk=pk)


class GuildDemoteView(LoginRequiredMixin, View):
    """Demote a guild officer."""

    def post(self, request, pk: int, user_pk: int):
        from django.contrib.auth import get_user_model

        user_model = get_user_model()
        target = get_object_or_404(user_model, pk=user_pk)
        try:
            _guild_service.demote_to_member(request.user, target)
            messages.success(request, f"{target} has been demoted to member.")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("guilds:detail", pk=pk)


class GuildDonateStickerView(LoginRequiredMixin, View):
    """Donate a sticker into the guild album."""

    def post(self, request, pk: int):
        guild = get_object_or_404(Guild, pk=pk)
        try:
            sticker_id = int(request.POST.get("sticker_id", "0"))
        except ValueError:
            messages.error(request, "Choose a valid sticker to donate.")
            return redirect("guilds:album", pk=pk)

        try:
            entry = _guild_service.donate_sticker(request.user, guild, sticker_id)
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request,
                f"{entry.sticker.pokemon.name} was donated to [{guild.tag}] and is now guild soul-bound.",
            )
        return redirect("guilds:album", pk=pk)


class GuildClaimQuestView(LoginRequiredMixin, View):
    """Claim a completed guild quest."""

    def post(self, request, pk: int):
        guild = get_object_or_404(Guild, pk=pk)
        quest_key = request.POST.get("quest_key", "")
        next_url = request.POST.get("next", "")
        try:
            reward = _guild_service.claim_guild_quest(request.user, guild, quest_key)
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request,
                f"Guild quest claimed: +{reward['ryo']} Ryo, +{reward['amigo_xp']} Amigo XP, +{reward['guild_xp']} guild XP.",
            )
        if next_url:
            return redirect(next_url)
        return redirect("guilds:detail", pk=pk)
