"""
P3-1 + P3-2 — Ranked season system and matchmaking queue tests.

Covers:
- Win awards +20 rank points; loss deducts 10 (floored at tier minimum)
- Win streak ≥3 adds +5 bonus points per win
- Win streak resets to 0 on a loss
- Tier promoted when rank_points cross threshold
- Loser cannot drop below current tier floor
- No active season → record_win returns no-op
- join_queue creates a MatchmakingEntry
- join_queue is idempotent (no duplicate waiting entries)
- leave_queue cancels the waiting entry
- Two queued players are matched → battle created, entries marked matched
- No match within tolerance → entry stays waiting
- QueueJoinView redirects to team_select when matched immediately
- Ranked page renders for authenticated user
"""
import allure
import pytest
from datetime import date, timedelta
from django.test import Client
from django.urls import reverse

from apps.ranked.models import (
    MatchmakingEntry,
    MatchmakingStatus,
    RankedProfile,
    RankedSeason,
    RankedTier,
    TIER_FLOORS,
)
from apps.ranked.services import MatchmakingService, RankedSeasonService

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.user_factory import UserFactory


def _make_season(**kwargs) -> RankedSeason:
    defaults = {
        "number": 1,
        "name": "Season of Kizuna",
        "start_date": date.today(),
        "end_date": date.today() + timedelta(days=90),
        "is_active": True,
    }
    defaults.update(kwargs)
    return RankedSeason.objects.create(**defaults)


def _client(user) -> Client:
    user.set_password("pw")
    user.save(update_fields=["password"])
    c = Client()
    c.force_login(user)
    return c


@allure.epic("Ranked")
@allure.feature("Season & Points")
@pytest.mark.django_db
class TestRankedPointSystem(BaseTest):

    @allure.story("Win awards +20 rank points")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_win_awards_base_points(self):
        season = _make_season()
        winner = UserFactory()
        loser = UserFactory()
        svc = RankedSeasonService()

        profile, pts = svc.record_win(winner, loser)

        assert pts == 20
        assert profile.rank_points == 20
        assert profile.season_wins == 1

    @allure.story("Loss deducts 10 rank points")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_loss_deducts_points(self):
        season = _make_season()
        winner = UserFactory()
        loser = UserFactory()
        svc = RankedSeasonService()

        # Give loser some points first
        loser_profile = svc.get_or_create_profile(loser, season)
        loser_profile.rank_points = 50
        loser_profile.save(update_fields=["rank_points"])

        svc.record_win(winner, loser)

        loser_profile.refresh_from_db()
        assert loser_profile.rank_points == 40
        assert loser_profile.season_losses == 1

    @allure.story("Loss cannot drop below current tier floor")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_loss_floored_at_tier_minimum(self):
        season = _make_season()
        winner = UserFactory()
        loser = UserFactory()
        svc = RankedSeasonService()

        # Loser is at exactly Bronze floor (0 pts)
        loser_profile = svc.get_or_create_profile(loser, season)
        assert loser_profile.rank_points == 0

        svc.record_win(winner, loser)

        loser_profile.refresh_from_db()
        assert loser_profile.rank_points == 0  # floored, not negative

    @allure.story("Win streak ≥3 awards +5 bonus per win")
    @allure.severity(allure.severity_level.NORMAL)
    def test_win_streak_bonus(self):
        season = _make_season()
        winner = UserFactory()
        svc = RankedSeasonService()

        # Build up a 3-win streak
        profile = svc.get_or_create_profile(winner, season)
        profile.win_streak = 2
        profile.rank_points = 40
        profile.save(update_fields=["win_streak", "rank_points"])

        loser = UserFactory()
        _, pts = svc.record_win(winner, loser)

        assert pts == 25  # 20 base + 5 streak bonus
        profile.refresh_from_db()
        assert profile.win_streak == 3

    @allure.story("Win streak resets to 0 on a loss")
    @allure.severity(allure.severity_level.NORMAL)
    def test_win_streak_resets_on_loss(self):
        season = _make_season()
        winner = UserFactory()
        loser = UserFactory()
        svc = RankedSeasonService()

        loser_profile = svc.get_or_create_profile(loser, season)
        loser_profile.win_streak = 5
        loser_profile.rank_points = 100
        loser_profile.save(update_fields=["win_streak", "rank_points"])

        svc.record_win(winner, loser)

        loser_profile.refresh_from_db()
        assert loser_profile.win_streak == 0

    @allure.story("Tier promoted when points cross threshold")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_tier_promotion(self):
        season = _make_season()
        winner = UserFactory()
        svc = RankedSeasonService()

        profile = svc.get_or_create_profile(winner, season)
        profile.rank_points = 290  # 10 below Silver floor (300)
        profile.tier = RankedTier.BRONZE
        profile.save(update_fields=["rank_points", "tier"])

        loser = UserFactory()
        svc.record_win(winner, loser)  # +20 → 310

        profile.refresh_from_db()
        assert profile.rank_points == 310
        assert profile.tier == RankedTier.SILVER

    @allure.story("No active season → record_win is a no-op")
    @allure.severity(allure.severity_level.NORMAL)
    def test_no_season_no_op(self):
        # No season created
        winner = UserFactory()
        loser = UserFactory()
        svc = RankedSeasonService()

        result_profile, pts = svc.record_win(winner, loser)

        assert result_profile is None
        assert pts == 0
        assert RankedProfile.objects.count() == 0


@allure.epic("Ranked")
@allure.feature("Matchmaking Queue")
@pytest.mark.django_db
class TestMatchmakingQueue(BaseTest):

    @allure.story("join_queue creates a MatchmakingEntry")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_join_queue_creates_entry(self):
        _make_season()
        user = UserFactory()
        svc = MatchmakingService()

        entry = svc.join_queue(user)

        assert entry.user == user
        assert entry.status == MatchmakingStatus.WAITING

    @allure.story("join_queue is idempotent — no duplicate waiting entries")
    @allure.severity(allure.severity_level.NORMAL)
    def test_join_queue_idempotent(self):
        _make_season()
        user = UserFactory()
        svc = MatchmakingService()

        e1 = svc.join_queue(user)
        e2 = svc.join_queue(user)

        assert e1.pk == e2.pk
        assert MatchmakingEntry.objects.filter(user=user, status=MatchmakingStatus.WAITING).count() == 1

    @allure.story("leave_queue cancels the waiting entry")
    @allure.severity(allure.severity_level.NORMAL)
    def test_leave_queue_cancels_entry(self):
        _make_season()
        user = UserFactory()
        svc = MatchmakingService()

        svc.join_queue(user)
        svc.leave_queue(user)

        assert MatchmakingEntry.objects.filter(user=user, status=MatchmakingStatus.WAITING).count() == 0
        assert MatchmakingEntry.objects.filter(user=user, status=MatchmakingStatus.CANCELLED).count() == 1

    @allure.story("Two queued players are matched → battle created")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_two_players_matched(self):
        _make_season()
        p1 = UserFactory()
        p2 = UserFactory()
        svc = MatchmakingService()

        # p2 enters first
        e2 = svc.join_queue(p2)
        assert e2.status == MatchmakingStatus.WAITING  # no one to match yet

        # p1 enters and should match with p2
        e1 = svc.join_queue(p1)

        e1.refresh_from_db()
        e2.refresh_from_db()
        assert e1.status == MatchmakingStatus.MATCHED
        assert e2.status == MatchmakingStatus.MATCHED
        assert e1.battle_id is not None
        assert e1.battle_id == e2.battle_id

    @allure.story("Players beyond tolerance stay unmatched")
    @allure.severity(allure.severity_level.NORMAL)
    def test_no_match_outside_tolerance(self):
        season = _make_season()
        p1 = UserFactory()
        p2 = UserFactory()
        svc = MatchmakingService()
        ranked_svc = RankedSeasonService()

        # Give p2 rank points far above tolerance
        p2_profile = ranked_svc.get_or_create_profile(p2, season)
        p2_profile.rank_points = 2000
        p2_profile.save(update_fields=["rank_points"])

        e2 = svc.join_queue(p2)
        # p1 has 0 pts; p2 has 2000; tolerance is 500 → no match
        e1 = svc.join_queue(p1)

        e1.refresh_from_db()
        e2.refresh_from_db()
        assert e1.status == MatchmakingStatus.WAITING
        assert e2.status == MatchmakingStatus.WAITING

    @allure.story("Ranked home page renders for logged-in user")
    @allure.severity(allure.severity_level.NORMAL)
    def test_ranked_home_renders(self):
        _make_season()
        user = UserFactory()
        c = _client(user)

        response = c.get(reverse("ranked:home"))

        assert response.status_code == 200
        assert b"Ranked PvP" in response.content

    @allure.story("QueueJoinView redirects to team_select when matched immediately")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_queue_join_view_redirects_on_match(self):
        _make_season()
        p1 = UserFactory()
        p2 = UserFactory()
        svc = MatchmakingService()

        # p1 is already waiting
        svc.join_queue(p1)

        # p2 joins via the view — should match and redirect
        c2 = _client(p2)
        response = c2.post(reverse("ranked:queue_join"))

        # Should redirect to team_select (302)
        assert response.status_code == 302
        assert "team" in response["Location"] or "battle" in response["Location"]
