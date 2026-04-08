"""
P3-3 — Leaderboard tests (GDD §20.9).

Covers:
- wins tab: ordered by battles_won descending
- wins tab: AI trainer excluded from results
- wins tab: own row highlighted (username present in response)
- combo tab: ordered by longest_combo_chain descending
- combo tab: users with 0 chain excluded
- season tab: ordered by rank_points descending
- season tab: no season → empty state rendered
- invalid tab defaults to wins
- page requires login (redirect for anonymous)
- leaderboard link present in base nav
"""
import allure
import pytest
from datetime import date, timedelta
from django.test import Client
from django.urls import reverse

from apps.ranked.models import RankedProfile, RankedSeason, RankedTier
from apps.ranked.services import RankedSeasonService

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.user_factory import UserFactory


def _make_season() -> RankedSeason:
    return RankedSeason.objects.create(
        number=1,
        name="Season of Kizuna",
        start_date=date.today(),
        end_date=date.today() + timedelta(days=90),
        is_active=True,
    )


def _client(user) -> Client:
    user.set_password("pw")
    user.save(update_fields=["password"])
    c = Client()
    c.force_login(user)
    return c


@allure.epic("Ranked")
@allure.feature("Leaderboard")
@pytest.mark.django_db
class TestLeaderboardWinsTab(BaseTest):

    @allure.story("Wins tab renders and orders by battles_won descending")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_wins_tab_ordered_by_battles_won(self):
        u1 = UserFactory(battles_won=50)
        u2 = UserFactory(battles_won=10)
        u3 = UserFactory(battles_won=30)
        client = _client(u1)

        response = client.get(reverse("ranked:leaderboard") + "?tab=wins")

        assert response.status_code == 200
        content = response.content.decode()
        pos_u1 = content.find(u1.username)
        pos_u3 = content.find(u3.username)
        pos_u2 = content.find(u2.username)
        assert pos_u1 < pos_u3 < pos_u2

    @allure.story("Wins tab excludes AI trainer account")
    @allure.severity(allure.severity_level.NORMAL)
    def test_wins_tab_excludes_ai(self):
        ai = UserFactory(username="__ai_trainer__", battles_won=9999)
        user = UserFactory(battles_won=1)
        client = _client(user)

        response = client.get(reverse("ranked:leaderboard") + "?tab=wins")

        assert b"__ai_trainer__" not in response.content

    @allure.story("Wins tab shows (you) label on own row")
    @allure.severity(allure.severity_level.NORMAL)
    def test_wins_tab_own_row_marked(self):
        user = UserFactory(battles_won=5)
        client = _client(user)

        response = client.get(reverse("ranked:leaderboard") + "?tab=wins")

        assert b"(you)" in response.content


@allure.epic("Ranked")
@allure.feature("Leaderboard")
@pytest.mark.django_db
class TestLeaderboardComboTab(BaseTest):

    @allure.story("Combo tab ordered by longest_combo_chain descending")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_combo_tab_ordered(self):
        u1 = UserFactory(longest_combo_chain=10)
        u2 = UserFactory(longest_combo_chain=3)
        u3 = UserFactory(longest_combo_chain=7)
        client = _client(u1)

        response = client.get(reverse("ranked:leaderboard") + "?tab=combo")

        assert response.status_code == 200
        content = response.content.decode()
        pos_u1 = content.find(u1.username)
        pos_u3 = content.find(u3.username)
        pos_u2 = content.find(u2.username)
        assert pos_u1 < pos_u3 < pos_u2

    @allure.story("Combo tab excludes users with zero chain")
    @allure.severity(allure.severity_level.NORMAL)
    def test_combo_tab_excludes_zero_chain(self):
        zero_user = UserFactory(longest_combo_chain=0)
        other = UserFactory(longest_combo_chain=5)
        client = _client(other)

        response = client.get(reverse("ranked:leaderboard") + "?tab=combo")

        assert zero_user.username.encode() not in response.content


@allure.epic("Ranked")
@allure.feature("Leaderboard")
@pytest.mark.django_db
class TestLeaderboardSeasonTab(BaseTest):

    @allure.story("Season tab ordered by rank_points descending")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_season_tab_ordered(self):
        season = _make_season()
        svc = RankedSeasonService()

        u1 = UserFactory()
        u2 = UserFactory()
        u3 = UserFactory()

        p1 = svc.get_or_create_profile(u1, season)
        p1.rank_points = 500; p1.save(update_fields=["rank_points"])
        p2 = svc.get_or_create_profile(u2, season)
        p2.rank_points = 100; p2.save(update_fields=["rank_points"])
        p3 = svc.get_or_create_profile(u3, season)
        p3.rank_points = 300; p3.save(update_fields=["rank_points"])

        client = _client(u1)
        response = client.get(reverse("ranked:leaderboard") + "?tab=season")

        assert response.status_code == 200
        content = response.content.decode()
        pos_u1 = content.find(u1.username)
        pos_u3 = content.find(u3.username)
        pos_u2 = content.find(u2.username)
        assert pos_u1 < pos_u3 < pos_u2

    @allure.story("Season tab with no active season shows empty state")
    @allure.severity(allure.severity_level.NORMAL)
    def test_season_tab_no_season_empty_state(self):
        user = UserFactory()
        client = _client(user)

        response = client.get(reverse("ranked:leaderboard") + "?tab=season")

        assert response.status_code == 200
        assert b"No ranked season" in response.content


@allure.epic("Ranked")
@allure.feature("Leaderboard")
@pytest.mark.django_db
class TestLeaderboardGeneral(BaseTest):

    @allure.story("Invalid tab defaults to wins tab")
    @allure.severity(allure.severity_level.MINOR)
    def test_invalid_tab_defaults_to_wins(self):
        user = UserFactory()
        client = _client(user)

        response = client.get(reverse("ranked:leaderboard") + "?tab=garbage")

        assert response.status_code == 200
        assert response.context["tab"] == "wins"

    @allure.story("Anonymous user is redirected to login")
    @allure.severity(allure.severity_level.NORMAL)
    def test_anonymous_redirected(self):
        response = Client().get(reverse("ranked:leaderboard"))

        assert response.status_code == 302
        assert "/accounts/login" in response["Location"]

    @allure.story("Leaderboard nav link present in authenticated response")
    @allure.severity(allure.severity_level.MINOR)
    def test_leaderboard_nav_link_present(self):
        user = UserFactory()
        client = _client(user)

        # Any authenticated page should contain the Leaderboard nav link
        response = client.get(reverse("ranked:leaderboard") + "?tab=wins")

        assert b"Leaderboard" in response.content
