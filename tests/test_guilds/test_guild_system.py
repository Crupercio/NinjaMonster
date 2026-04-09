"""
P4-5 — Guild/Clan System tests.

Covers:
- GuildService.create_guild() success + deducts Ryo
- GuildService.create_guild() raises when already in a guild
- GuildService.create_guild() raises on insufficient Ryo
- GuildService.create_guild() raises on duplicate guild name
- GuildService.create_guild() raises on duplicate tag
- GuildService.join_guild() success
- GuildService.join_guild() raises when already in a guild
- GuildService.join_guild() raises when guild is closed
- GuildService.leave_guild() member leaves successfully
- GuildService.leave_guild() owner-last-member disbands guild
- GuildService.leave_guild() owner with members raises
- GuildService.kick_member() officer kicks regular member
- GuildService.kick_member() officer cannot kick another officer
- GuildService.promote_to_officer() + demote_to_member()
- GuildService.get_guild_stats() aggregates correctly
- Guild list page renders
- Guild detail page renders with stats and members
- Guild create page (GET) renders form
"""
import allure
import pytest
from django.test import Client
from django.urls import reverse

from apps.guilds.models import Guild, GuildMembership, GuildRole
from apps.guilds.services import GuildService

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.guild_factory import GuildFactory, GuildMembershipFactory
from tests.framework.factories.user_factory import UserFactory


def _client(user) -> Client:
    user.set_password("pw")
    user.save(update_fields=["password"])
    c = Client()
    c.force_login(user)
    return c


@allure.epic("Guilds")
@allure.feature("Guild Creation")
@pytest.mark.django_db
class TestGuildCreation(BaseTest):

    @allure.story("create_guild success deducts Ryo and creates membership")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_create_guild_success(self):
        svc = GuildService()
        user = UserFactory(ryo=2000)
        guild = svc.create_guild(user, "Iron Fist", "IF")
        user.refresh_from_db()
        assert guild.pk is not None
        assert guild.tag == "IF"
        assert user.ryo == 1000
        assert GuildMembership.objects.filter(user=user, guild=guild, role=GuildRole.OWNER).exists()

    @allure.story("create_guild raises when user already in a guild")
    @allure.severity(allure.severity_level.NORMAL)
    def test_create_guild_raises_when_already_in_guild(self):
        svc = GuildService()
        user = UserFactory(ryo=5000)
        guild = GuildFactory()
        GuildMembershipFactory(user=user, guild=guild)
        with pytest.raises(ValueError, match="leave your current guild"):
            svc.create_guild(user, "New Guild", "NG")

    @allure.story("create_guild raises when insufficient Ryo")
    @allure.severity(allure.severity_level.NORMAL)
    def test_create_guild_raises_on_insufficient_ryo(self):
        svc = GuildService()
        user = UserFactory(ryo=500)
        with pytest.raises(Exception):
            svc.create_guild(user, "Broke Guild", "BG")

    @allure.story("create_guild raises on duplicate guild name")
    @allure.severity(allure.severity_level.NORMAL)
    def test_create_guild_raises_on_duplicate_name(self):
        svc = GuildService()
        GuildFactory(name="Shadow Order", tag="SHDO")
        user = UserFactory(ryo=5000)
        with pytest.raises(ValueError, match="already exists"):
            svc.create_guild(user, "Shadow Order", "NEW1")

    @allure.story("create_guild raises on duplicate tag")
    @allure.severity(allure.severity_level.NORMAL)
    def test_create_guild_raises_on_duplicate_tag(self):
        svc = GuildService()
        GuildFactory(name="Existing Guild", tag="DUPE")
        user = UserFactory(ryo=5000)
        with pytest.raises(ValueError, match="already taken"):
            svc.create_guild(user, "Different Name", "DUPE")


@allure.epic("Guilds")
@allure.feature("Join and Leave Guild")
@pytest.mark.django_db
class TestJoinLeaveGuild(BaseTest):

    @allure.story("join_guild success adds member membership")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_join_guild_success(self):
        svc = GuildService()
        guild = GuildFactory(is_recruiting=True)
        # need owner membership so member_count works
        owner = UserFactory()
        GuildMembershipFactory(user=owner, guild=guild, role=GuildRole.OWNER)
        user = UserFactory()
        membership = svc.join_guild(user, guild)
        assert membership.role == GuildRole.MEMBER
        assert membership.guild == guild

    @allure.story("join_guild raises when already in a guild")
    @allure.severity(allure.severity_level.NORMAL)
    def test_join_guild_raises_when_already_member(self):
        svc = GuildService()
        guild1 = GuildFactory()
        guild2 = GuildFactory()
        user = UserFactory()
        GuildMembershipFactory(user=user, guild=guild1)
        with pytest.raises(ValueError, match="leave your current guild"):
            svc.join_guild(user, guild2)

    @allure.story("join_guild raises when guild is not recruiting")
    @allure.severity(allure.severity_level.NORMAL)
    def test_join_guild_raises_when_closed(self):
        svc = GuildService()
        guild = GuildFactory(is_recruiting=False)
        user = UserFactory()
        with pytest.raises(ValueError, match="not currently recruiting"):
            svc.join_guild(user, guild)

    @allure.story("leave_guild removes member from guild")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_leave_guild_member_success(self):
        svc = GuildService()
        guild = GuildFactory()
        owner = UserFactory()
        GuildMembershipFactory(user=owner, guild=guild, role=GuildRole.OWNER)
        user = UserFactory()
        GuildMembershipFactory(user=user, guild=guild, role=GuildRole.MEMBER)
        svc.leave_guild(user)
        assert not GuildMembership.objects.filter(user=user).exists()
        assert Guild.objects.filter(pk=guild.pk).exists()

    @allure.story("leave_guild owner as last member disbands guild")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_leave_guild_owner_last_member_disbands(self):
        svc = GuildService()
        guild = GuildFactory()
        owner = UserFactory()
        GuildMembershipFactory(user=owner, guild=guild, role=GuildRole.OWNER)
        guild_pk = guild.pk
        svc.leave_guild(owner)
        assert not Guild.objects.filter(pk=guild_pk).exists()

    @allure.story("leave_guild owner with other members raises")
    @allure.severity(allure.severity_level.NORMAL)
    def test_leave_guild_owner_with_members_raises(self):
        svc = GuildService()
        guild = GuildFactory()
        owner = UserFactory()
        GuildMembershipFactory(user=owner, guild=guild, role=GuildRole.OWNER)
        member = UserFactory()
        GuildMembershipFactory(user=member, guild=guild, role=GuildRole.MEMBER)
        with pytest.raises(ValueError, match="Transfer ownership"):
            svc.leave_guild(owner)


@allure.epic("Guilds")
@allure.feature("Guild Moderation")
@pytest.mark.django_db
class TestGuildModeration(BaseTest):

    @allure.story("officer can kick a regular member")
    @allure.severity(allure.severity_level.NORMAL)
    def test_officer_kicks_member(self):
        svc = GuildService()
        guild = GuildFactory()
        owner = UserFactory()
        GuildMembershipFactory(user=owner, guild=guild, role=GuildRole.OWNER)
        officer = UserFactory()
        GuildMembershipFactory(user=officer, guild=guild, role=GuildRole.OFFICER)
        target = UserFactory()
        GuildMembershipFactory(user=target, guild=guild, role=GuildRole.MEMBER)
        svc.kick_member(officer, target)
        assert not GuildMembership.objects.filter(user=target).exists()

    @allure.story("officer cannot kick another officer")
    @allure.severity(allure.severity_level.NORMAL)
    def test_officer_cannot_kick_officer(self):
        svc = GuildService()
        guild = GuildFactory()
        owner = UserFactory()
        GuildMembershipFactory(user=owner, guild=guild, role=GuildRole.OWNER)
        officer1 = UserFactory()
        GuildMembershipFactory(user=officer1, guild=guild, role=GuildRole.OFFICER)
        officer2 = UserFactory()
        GuildMembershipFactory(user=officer2, guild=guild, role=GuildRole.OFFICER)
        with pytest.raises(ValueError, match="Officers can only kick regular members"):
            svc.kick_member(officer1, officer2)

    @allure.story("owner can promote member to officer and demote back")
    @allure.severity(allure.severity_level.NORMAL)
    def test_promote_and_demote(self):
        svc = GuildService()
        guild = GuildFactory()
        owner = UserFactory()
        GuildMembershipFactory(user=owner, guild=guild, role=GuildRole.OWNER)
        member = UserFactory()
        m = GuildMembershipFactory(user=member, guild=guild, role=GuildRole.MEMBER)

        svc.promote_to_officer(owner, member)
        m.refresh_from_db()
        assert m.role == GuildRole.OFFICER

        svc.demote_to_member(owner, member)
        m.refresh_from_db()
        assert m.role == GuildRole.MEMBER


@allure.epic("Guilds")
@allure.feature("Guild Stats")
@pytest.mark.django_db
class TestGuildStats(BaseTest):

    @allure.story("get_guild_stats aggregates member wins and battles")
    @allure.severity(allure.severity_level.NORMAL)
    def test_get_guild_stats(self):
        svc = GuildService()
        guild = GuildFactory()
        u1 = UserFactory(battles_won=5, battles_played=10, longest_combo_chain=4)
        u2 = UserFactory(battles_won=3, battles_played=8, longest_combo_chain=6)
        GuildMembershipFactory(user=u1, guild=guild, role=GuildRole.OWNER)
        GuildMembershipFactory(user=u2, guild=guild, role=GuildRole.MEMBER)

        stats = svc.get_guild_stats(guild)
        assert stats["total_wins"] == 8
        assert stats["total_battles"] == 18
        assert stats["avg_longest_combo"] == 5.0


@allure.epic("Guilds")
@allure.feature("Guild Pages")
@pytest.mark.django_db
class TestGuildPages(BaseTest):

    @allure.story("guild list page renders 200 for authenticated user")
    @allure.severity(allure.severity_level.NORMAL)
    def test_guild_list_page_renders(self):
        user = UserFactory()
        c = _client(user)
        GuildFactory(name="Visible Guild", tag="VIS1")
        resp = c.get(reverse("guilds:list"))
        assert resp.status_code == 200
        assert b"Visible Guild" in resp.content

    @allure.story("guild detail page renders with member list")
    @allure.severity(allure.severity_level.NORMAL)
    def test_guild_detail_page_renders(self):
        owner = UserFactory()
        guild = GuildFactory(name="Detail Guild", tag="DTL1")
        GuildMembershipFactory(user=owner, guild=guild, role=GuildRole.OWNER)
        c = _client(owner)
        resp = c.get(reverse("guilds:detail", args=[guild.pk]))
        assert resp.status_code == 200
        assert b"Detail Guild" in resp.content
        assert b"DTL1" in resp.content

    @allure.story("guild create page renders form with Ryo cost")
    @allure.severity(allure.severity_level.NORMAL)
    def test_guild_create_page_renders(self):
        user = UserFactory(ryo=5000)
        c = _client(user)
        resp = c.get(reverse("guilds:create"))
        assert resp.status_code == 200
        assert b"1000" in resp.content
